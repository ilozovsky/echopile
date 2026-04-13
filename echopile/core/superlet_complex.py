# -*- coding: utf-8 -*-
#
# Time-frequency analysis with superlets
# Based on 'Time-frequency super-resolution with superlets'
# by Moca et al., 2021 https://doi.org/10.1038/s41467-020-20539-9
#
# Adapted from Gregor Monke's implementation https://github.com/tensionhead/Superlets
#
# The core Morlet superlet definition and the adaptive-order mapping are
# retained, but this file was revised for echopile.
# The main changes are a frequency-based public API, separate fixed and
# adaptive SLT entry points, additional argument validation, configurable
# wavelet-set construction, revised transform normalization and support
# handling, an FFT-cached convolution path, and optional phase-combination
# modes not present in the original file.
#

import numpy as np
from scipy.fft import fft, ifft, next_fast_len
from scipy.signal import fftconvolve

__all__ = ["slt", "adaptive_slt"]

def _validate_frequencies(frequencies):
    frequencies = np.asarray(frequencies, dtype=np.float64)
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("frequencies must be a non-empty 1D array")
    if np.any(np.diff(frequencies) <= 0):
        raise ValueError("frequencies must be strictly increasing")
    if np.any(frequencies <= 0):
        raise ValueError("frequencies must be strictly positive")

    return frequencies

def _validate_superlet_args(c_1, k_sd, support_sd, set_mode):
    if c_1 <= 0:
        raise ValueError("c_1 must be strictly positive")
    if k_sd <= 0:
        raise ValueError("k_sd must be strictly positive")
    if support_sd <= 0:
        raise ValueError("support_sd must be strictly positive")
    if set_mode not in {"multiplicative", "additive"}:
        raise ValueError(
            "set_mode must be either 'multiplicative' or 'additive'"
        )

def _build_wavelet_cycles(order_values, c_1, set_mode):
    order_values = np.asarray(order_values, dtype=np.float64)

    if set_mode == "multiplicative":
        return c_1 * order_values

    return c_1 + order_values - 1

def slt(
    signal,
    fs,
    frequencies,
    order,
    c_1=3,
    set_mode="multiplicative",
    k_sd=5.0,
    support_sd=6.0,
    use_fft_cache=True,
    phase_combination="standard",
):
    """
    Compute a fixed-order Superlet Transform (SLT) according to
    Moca et al. [1].

    A superlet is a set of Morlet wavelets with increasing numbers of
    cycles at the same central frequency. Wavelets with more cycles have
    narrower frequency responses, while wavelets with fewer cycles retain
    better time resolution. The SLT combines the individual wavelet
    responses by a geometric mean to obtain a sharper joint
    time-frequency representation.

    Parameters
    ----------
    signal : nD :class:`numpy.ndarray`
        Uniformly sampled time-series data.
        The first dimension is interpreted as time.
    fs : float
        Sampling rate in Hz.
    frequencies : 1D :class:`numpy.ndarray`
        Frequencies of interest in Hz.
    order : int
        Number of wavelets in the superlet.
    c_1 : float
        Number of cycles in the base Morlet wavelet.
    set_mode : {"multiplicative", "additive"}
        Rule used to increase the number of cycles across the wavelet set.
        If "multiplicative", c_i = i * c_1.
        If "additive", c_i = c_1 + i - 1.
    k_sd : float
        Gaussian width parameter of the Morlet wavelet.
        The default used in the paper is k_sd = 5.
    support_sd : float
        Numerical support of the sampled wavelet, expressed as the total
        convolution-window width in Gaussian standard deviations.
        The paper uses a practical window spanning 6 SDs.
    use_fft_cache : bool
        If True, reuse FFTs across wavelet convolutions to reduce repeated
        computation.
    phase_combination : {"standard", "unwrapped", "circular"}
        Rule used to combine phase across wavelet orders.
        "standard" follows the original complex-power formulation.
        "unwrapped" unwraps phase across orders before averaging.
        "circular" averages phase as unit vectors on the complex plane.

    Returns
    -------
    gmean_spec : :class:`numpy.ndarray`
        Complex time-frequency representation of the input data.
        Shape is `(len(frequencies),) + signal.shape`.

        For real-valued signals, a corresponding power estimate is
        2 * abs(response)**2.

    Notes
    -----
    .. [1] Moca, Vasile V., et al.
       "Time-frequency super-resolution with superlets."
       Nature Communications 12.1 (2021): 1-18.
    """

    frequencies = _validate_frequencies(frequencies)
    _validate_superlet_args(c_1, k_sd, support_sd, set_mode)
    if phase_combination not in {"standard", "unwrapped", "circular"}:
        raise ValueError(
            "phase_combination must be one of 'standard', 'unwrapped', "
            "or 'circular'"
        )

    if int(order) != order or order < 1:
        raise ValueError("order must be a positive integer")

    order = int(order)
    dt = 1 / fs
    scales = _scale_from_frequency(frequencies)
    fft_data_cache = {}

    order_values = np.arange(1, order + 1, dtype=np.int32)
    cycles_per_wavelet = _build_wavelet_cycles(order_values, c_1, set_mode)
    wavelet_set = [
        _MorletSL(cycles, k_sd=k_sd) for cycles in cycles_per_wavelet
    ]

    if phase_combination == "standard":
        combined_response = _cwt_sl(
            signal,
            wavelet_set[0],
            scales,
            dt,
            support_sd=support_sd,
            fft_data_cache=fft_data_cache,
            use_fft_cache=use_fft_cache,
        )
        combined_response = np.power(combined_response, 1 / order)

        for wavelet in wavelet_set[1:]:
            wavelet_response = _cwt_sl(
                signal,
                wavelet,
                scales,
                dt,
                support_sd=support_sd,
                fft_data_cache=fft_data_cache,
                use_fft_cache=use_fft_cache,
            )
            combined_response *= np.power(wavelet_response, 1 / order)

        return combined_response

    per_order_response = []
    for wavelet in wavelet_set:
        wavelet_response = _cwt_sl(
            signal,
            wavelet,
            scales,
            dt,
            support_sd=support_sd,
            fft_data_cache=fft_data_cache,
            use_fft_cache=use_fft_cache,
        )
        per_order_response.append(wavelet_response.astype(np.complex128))

    per_order_response = np.stack(per_order_response, axis=0)
    order_weights = np.full(
        (per_order_response.shape[0], per_order_response.shape[1]),
        1.0 / order,
        dtype=np.float64,
    )
    return _combine_weighted_components(
        per_order_response,
        order_weights,
        phase_combination,
    )

def adaptive_slt(
    signal,
    fs,
    frequencies,
    order_min=1,
    order_max=10,
    c_1=3,
    set_mode="multiplicative",
    k_sd=5.0,
    support_sd=6.0,
    use_fft_cache=True,
    phase_combination="standard",
):
    """
    Compute a fractional adaptive Superlet Transform (FASLT) according to
    Moca et al. [1].

    The superlet order varies linearly with frequency from `order_min`
    to `order_max`.

    Parameters
    ----------
    signal : nD :class:`numpy.ndarray`
        Uniformly sampled time-series data.
        The first dimension is interpreted as time.
    fs : float
        Sampling rate in Hz.
    frequencies : 1D :class:`numpy.ndarray`
        Frequencies of interest in Hz.
        Must be strictly increasing and contain at least two distinct
        values for the adaptive order mapping.
    order_min : float
        Minimum adaptive superlet order.
    order_max : float
        Maximum adaptive superlet order.
    c_1 : float
        Number of cycles in the base Morlet wavelet.
    set_mode : {"multiplicative", "additive"}
        Rule used to increase the number of cycles across the wavelet set.
        If "multiplicative", c_i = i * c_1.
        If "additive", c_i = c_1 + i - 1.
    k_sd : float
        Gaussian width parameter of the Morlet wavelet.
        The default used in the paper is k_sd = 5.
    support_sd : float
        Numerical support of the sampled wavelet, expressed as the total
        convolution-window width in Gaussian standard deviations.
        The paper uses a practical window spanning 6 SDs.
    use_fft_cache : bool
        If True, reuse FFTs across wavelet convolutions to reduce repeated
        computation.
    phase_combination : {"standard", "unwrapped", "circular"}
        Rule used to combine phase across wavelet orders.
        "standard" follows the original complex-power formulation.
        "unwrapped" unwraps phase across orders before averaging.
        "circular" averages phase as unit vectors on the complex plane.

    Returns
    -------
    gmean_spec : :class:`numpy.ndarray`
        Complex time-frequency representation of the input data.
        Shape is `(len(frequencies),) + signal.shape`.

        For real-valued signals, a corresponding power estimate is
        2 * abs(response)**2.

    Notes
    -----
    .. [1] Moca, Vasile V., et al.
       "Time-frequency super-resolution with superlets."
       Nature Communications 12.1 (2021): 1-18.
    """

    frequencies = _validate_frequencies(frequencies)
    _validate_superlet_args(c_1, k_sd, support_sd, set_mode)
    if phase_combination not in {"standard", "unwrapped", "circular"}:
        raise ValueError(
            "phase_combination must be one of 'standard', 'unwrapped', "
            "or 'circular'"
        )

    if order_min < 1:
        raise ValueError("order_min must be at least 1")
    if order_max < order_min:
        raise ValueError(
            "order_max must be greater than or equal to order_min"
        )

    dt = 1 / fs
    scales = _scale_from_frequency(frequencies)
    fft_data_cache = {}

    frequencies_from_scale = 1 / (2 * np.pi * scales)
    adaptive_order = _compute_adaptive_order(
        frequencies_from_scale,
        order_min,
        order_max,
    )

    max_order = int(np.ceil(np.max(adaptive_order)))
    order_values = np.arange(1, max_order + 1, dtype=np.int32)
    cycles_per_wavelet = _build_wavelet_cycles(order_values, c_1, set_mode)
    wavelet_set = [
        _MorletSL(cycles, k_sd=k_sd) for cycles in cycles_per_wavelet
    ]

    if phase_combination == "standard":
        scale_exponents = 1 / adaptive_order
        combined_response = _cwt_sl(
            signal,
            wavelet_set[0],
            scales,
            dt,
            support_sd=support_sd,
            fft_data_cache=fft_data_cache,
            use_fft_cache=use_fft_cache,
        )
        combined_response = np.power(combined_response.T, scale_exponents).T

        for order_index, wavelet in enumerate(wavelet_set[1:], start=1):
            scale_weight = (
                np.clip(adaptive_order - order_index, 0.0, 1.0)
                * scale_exponents
            )
            if not np.any(scale_weight > 0):
                continue

            active_scales = scale_weight > 0
            wavelet_response = _cwt_sl(
                signal,
                wavelet,
                scales[active_scales],
                dt,
                support_sd=support_sd,
                fft_data_cache=fft_data_cache,
                use_fft_cache=use_fft_cache,
            )
            combined_response[active_scales] *= np.power(
                wavelet_response.T,
                scale_weight[active_scales],
            ).T

        return combined_response

    scale_exponents = 1 / adaptive_order
    order_weights = np.zeros((len(wavelet_set), len(scales)), dtype=np.float64)
    order_weights[0] = scale_exponents

    per_order_response = []
    first_response = _cwt_sl(
        signal,
        wavelet_set[0],
        scales,
        dt,
        support_sd=support_sd,
        fft_data_cache=fft_data_cache,
        use_fft_cache=use_fft_cache,
    )
    per_order_response.append(first_response.astype(np.complex128))

    for order_index, wavelet in enumerate(wavelet_set[1:], start=1):
        order_weights[order_index] = np.clip(
            adaptive_order - order_index,
            0.0,
            1.0,
        ) * scale_exponents
        wavelet_response = _cwt_sl(
            signal,
            wavelet,
            scales,
            dt,
            support_sd=support_sd,
            fft_data_cache=fft_data_cache,
            use_fft_cache=use_fft_cache,
        )
        per_order_response.append(wavelet_response.astype(np.complex128))

    per_order_response = np.stack(per_order_response, axis=0)
    return _combine_weighted_components(
        per_order_response,
        order_weights,
        phase_combination,
    )

class _MorletSL:
    def __init__(self, c_i=3, k_sd=5):

        """The Morlet formulation according to
        Moca et al. shifts the admissability criterion from
        the central frequency to the number of cycles c_i
        within the Gaussian envelope which has a constant
        standard deviation of k_sd.
        """

        self.c_i = c_i
        self.k_sd = k_sd

    def __call__(self, *args, **kwargs):
        return self.time(*args, **kwargs)

    def time(self, t, s=1.0):

        """
        Complext Morlet wavelet in the SL formulation.

        Parameters
        ----------
        t : float
            Time. If s is not specified, this can be used as the
            non-dimensional time t/s.
        s : float
            Scaling factor. Default is 1.

        Returns
        -------
        out : complex
            Value of the Morlet wavelet at the given time
        """

        ts = t / s
        # scaled time spread parameter
        # also includes scale normalisation!
        b_c = self.k_sd / (s * self.c_i * (2 * np.pi) ** 1.5)

        output = b_c * np.exp(1j * ts)
        output *= np.exp(-0.5 * (self.k_sd * ts / (2 * np.pi * self.c_i)) ** 2)

        return output

def _scale_from_frequency(frequency):
    """
    Convert frequencies in Hz to the superlet Morlet scale convention.

    Note that for the SL Morlet the relationship between scale and frequency
    simply is s(f) = 1/(2*pi*f).
    """

    frequency = np.asarray(frequency, dtype=np.float64)
    return (1 / frequency) / (2 * np.pi)

def _cwt_sl(
    data,
    wavelet,
    scales,
    dt,
    support_sd=6.0,
    fft_data_cache=None,
    use_fft_cache=True,
):

    """
    Continuous wavelet transform helper for the superlet Morlet wavelet.

    This implementation follows the superlet-specific Morlet formulation
    used by Moca et al. The wavelet support depends on both scale and
    cycle count, and the sampled wavelet follows the modified CWT
    normalization based on 1/a scaling.

    The function returns the complex time-frequency response. For
    real-valued signals, a corresponding power estimate is
    `2 * abs(response)**2`.

    Notes
    -----
    The time axis is expected along the first dimension.
    If `use_fft_cache` is True, FFTs of the input data are reused across
    wavelet convolutions.
    """

    if use_fft_cache:
        return _cwt_sl_fft_cached(
            data,
            wavelet,
            scales,
            dt,
            support_sd=support_sd,
            fft_data_cache=fft_data_cache,
        )

    return _cwt_sl_fftconvolve(
        data,
        wavelet,
        scales,
        dt,
        support_sd=support_sd,
    )

def _cwt_sl_fftconvolve(data, wavelet, scales, dt, support_sd=6.0):

    data = np.asarray(data)

    # wavelets can be complex so output is complex
    output = np.zeros((len(scales),) + data.shape, dtype=np.complex64)

    # this checks if really a Superlet Wavelet is being used
    if not isinstance(wavelet, _MorletSL):
        raise ValueError("Wavelet is not of MorletSL type!")

    # 1st axis is time
    slices = [None for _ in data.shape]
    slices[0] = slice(None)

    for ind, scale in enumerate(scales):

        t = _get_superlet_support(
            scale, dt, wavelet.c_i, k_sd=wavelet.k_sd, support_sd=support_sd
        )
        # sample wavelet and normalise
        wavelet_data = dt * wavelet(t, scale)
        output[ind, :] = fftconvolve(
            data,
            wavelet_data[tuple(slices)],
            mode="same",
        )

    return output

def _cwt_sl_fft_cached(
    data,
    wavelet,
    scales,
    dt,
    support_sd=6.0,
    fft_data_cache=None,
):
    data = np.asarray(data)

    # wavelets can be complex so output is complex
    output = np.zeros((len(scales),) + data.shape, dtype=np.complex64)

    # this checks if really a Superlet Wavelet is being used
    if not isinstance(wavelet, _MorletSL):
        raise ValueError("Wavelet is not of MorletSL type!")

    if fft_data_cache is None:
        fft_data_cache = {}

    data_len = data.shape[0]
    wavelet_shape = (slice(None),) + (None,) * (data.ndim - 1)

    for ind, scale in enumerate(scales):
        t = _get_superlet_support(
            scale, dt, wavelet.c_i, k_sd=wavelet.k_sd, support_sd=support_sd
        )
        # sample wavelet and normalise
        wavelet_data = dt * wavelet(t, scale)

        full_len = data_len + wavelet_data.shape[0] - 1
        fft_len = next_fast_len(full_len)

        if fft_len not in fft_data_cache:
            fft_data_cache[fft_len] = fft(data, n=fft_len, axis=0)

        data_fft = fft_data_cache[fft_len]
        wavelet_fft = fft(wavelet_data[wavelet_shape], n=fft_len, axis=0)
        conv_full = ifft(data_fft * wavelet_fft, n=fft_len, axis=0)
        conv_full = conv_full[:full_len]

        start = (full_len - data_len) // 2
        output[ind, :] = conv_full[start:start + data_len]

    return output

def _get_superlet_support(scale, dt, cycles, k_sd=5.0, support_sd=6.0):

    """
    Effective support for the convolution is here not only
    scale but also cycle dependent.

    The paper uses a practical convolution window spanning 6
    standard deviations of the Gaussian envelope. The support_sd
    parameter keeps this as the default while allowing a wider or
    narrower numerical window if desired.
    """

    sigma_t = 2 * np.pi * scale * cycles / k_sd
    half_width = int(np.ceil((support_sd / 2.0) * sigma_t / dt))
    t = np.arange(-half_width, half_width + 1, dtype=np.float64) * dt

    return t

def _combine_weighted_components(
    per_order_response,
    order_weights,
    phase_combination,
):
    """Combine per-order complex responses using the requested phase rule."""
    
    order_weights = np.asarray(order_weights, dtype=np.float64)
    per_order_response = np.asarray(per_order_response, dtype=np.complex128)
    
    # Match any trailing signal axes, e.g. time-only or time-plus-channels.
    broadcast_weights = order_weights.reshape(
        order_weights.shape
        + (1,) * (per_order_response.ndim - order_weights.ndim)
    )
    eps = 1e-12

    if phase_combination == "standard":
    # Original superlet-style combination: multiply complex responses
    # after raising each order contribution to its weight
        combined_response = np.ones_like(
            per_order_response[0],
            dtype=np.complex128,
        )
        for order_index in range(per_order_response.shape[0]):
            active_weights = broadcast_weights[order_index] > 0
            if not np.any(active_weights):
                continue
            combined_response[active_weights] *= np.power(
                per_order_response[order_index][active_weights],
                broadcast_weights[order_index][active_weights],
            )
        return combined_response

    # The alternative phase rules keep the geometric amplitude but replace
    # the phase combination step
    
    magnitude = np.abs(per_order_response)
    geometric_amplitude = np.exp(
        np.sum(broadcast_weights * np.log(np.maximum(magnitude, eps)), axis=0)
    )

    # Average phase after unwrapping across the order axis
    if phase_combination == "unwrapped":
        phase_by_order = np.unwrap(np.angle(per_order_response), axis=0)
        combined_phase = np.sum(broadcast_weights * phase_by_order, axis=0)
        return geometric_amplitude * np.exp(1j * combined_phase)

    # Circular phase average: combine phase directions as weighted unit phasors
    unit_phasor = per_order_response / np.maximum(magnitude, eps)
    mean_phasor = np.sum(broadcast_weights * unit_phasor, axis=0)
    combined_phase = np.angle(mean_phasor)
    return geometric_amplitude * np.exp(1j * combined_phase)

def _compute_adaptive_order(freq, order_min, order_max):
    """
    Computes the superlet order for a given frequency of interest
    for the fractional adaptive SLT (FASLT) according to
    equation 7 of Moca et al. 2021.

    This is a simple linear mapping between the minimal
    and maximal order onto the respective minimal and maximal
    frequencies.

    Note that `freq` should be ordered low to high and contain at
    least two distinct values.
    """

    f_min, f_max = freq[0], freq[-1]

    if not f_min < f_max:
        raise ValueError(
            "adaptive_slt requires at least two distinct frequencies "
            "ordered low to high"
        )

    order = (order_max - order_min) * (freq - f_min) / (f_max - f_min)

    return order_min + order