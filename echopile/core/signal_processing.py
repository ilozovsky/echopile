"""Signal processing helpers"""
from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import numpy as np
import pandas as pd
from numpy.fft import rfft, rfftfreq
from scipy.interpolate import BSpline, splrep  # type: ignore
from scipy.signal import (  # type: ignore
    butter,
    detrend as sp_detrend,
    find_peaks,
    sosfilt,
    sosfiltfilt,
    sosfreqz,
)


def regularized_fd_integrate(
    signal: np.ndarray,
    fs: float,
    low_frequency_hz: float = 10.0,
    times: int = 1,
    target_accuracy: float = 0.97,
) -> np.ndarray:
    """Integrate a time series in the frequency domain with smooth low-frequency suppression.

    This is an offline regularized integrator:
    - at useful frequencies it behaves like standard x1 / x2 integration
    - near zero frequency it stays bounded, which suppresses drift growth
    """
    if fs <= 0:
        raise ValueError("fs must be positive")
    if low_frequency_hz <= 0:
        raise ValueError("low_frequency_hz must be positive")
    if not (0.0 < target_accuracy < 1.0):
        raise ValueError("target_accuracy must be between 0 and 1")
    if times not in (0, 1, 2):
        raise ValueError("times must be 0, 1, or 2")

    x = np.asarray(signal, dtype=float)
    if x.ndim != 1:
        raise ValueError("signal must be one-dimensional")
    if x.size == 0:
        return x.copy()

    # Keep the rFFT / irFFT round-trip simple for odd-length signals.
    odd = bool(x.size % 2)
    if odd:
        x = np.append(x, 0.0)

    freqs_hz = np.fft.rfftfreq(x.size, d=1.0 / fs)
    omega = 2.0 * np.pi * freqs_hz
    spectrum = np.fft.rfft(x)

    # The regularization strength is tied to the desired accuracy at the chosen low-frequency boundary.
    beta = np.sqrt((1.0 - target_accuracy) / target_accuracy) * (2.0 * np.pi * low_frequency_hz) ** 2
    denom = omega**4 + beta**2

    if times == 0:
        y = np.fft.irfft(spectrum, n=x.size)
    elif times == 1:
        # Single integration derived from the same regularized x2 transfer function family.
        transfer = (-1j * omega**3) / denom
        y = np.fft.irfft(spectrum * transfer, n=x.size)
    else:
        # Double integration with smooth attenuation of the problematic near-zero band.
        transfer = -(omega**2) / denom
        y = np.fft.irfft(spectrum * transfer, n=x.size)

    return y[:-1] if odd else y


def amplificate_signal(t: Sequence[float], amp: Sequence[float], a0: float) -> Tuple[list[float], list[float]]:
    """Exponential amplification A(t) = amp * exp(a0 * t)."""
    t = list(t)
    out = (np.asarray(amp)[: len(t)] * np.exp(np.asarray(t) * a0)).tolist()
    return t, out


def zero_baseline(df_in: pd.DataFrame) -> pd.DataFrame:
    """Shift the signal so the first few samples are centered around zero."""
    baseline_samples = min(10, len(df_in))
    if baseline_samples <= 0:
        return df_in

    baseline = float(np.median(df_in["amp"].iloc[:baseline_samples]))
    df_out = df_in.copy()
    df_out["amp"] = df_out["amp"] - baseline
    return df_out


def flip_signal_polarity(df_in: pd.DataFrame, flip_on: bool = False) -> pd.DataFrame:
    """Coerce amplitude to float and optionally flip signal polarity."""
    df_out = df_in.copy()
    amp = pd.to_numeric(df_out["amp"], errors="coerce").astype(float).fillna(0.0)
    df_out["amp"] = -amp if flip_on else amp
    return df_out


def round_up(n: float, decimals: int) -> float:
    mult = 10 ** decimals
    return float(np.ceil(n * mult) / mult)


def find_reference_peak_time(
    signal: Sequence[float],
    time: Sequence[float],
    peak_distance: int,
    peak_prominence_min: float,
    peak_width_min: int,
    peak_width_max: int | None,
):
    """Return the time of the earliest positive or negative peak in the first 30% of the signal."""
    signal_arr = np.asarray(signal, dtype=float)
    time_arr = np.asarray(time, dtype=float)
    if signal_arr.size < 2 or time_arr.size < 2:
        return None, "Reference peak was not found because the signal is too short."

    search_limit = float(time_arr[0] + 0.3 * (time_arr[-1] - time_arr[0]))
    mask = time_arr <= search_limit
    if np.count_nonzero(mask) < 2:
        return None, "Reference peak was not found because the first 30% of the full signal is too short."

    sig_search = signal_arr[mask]
    time_search = time_arr[mask]
    pos_idx, _ = find_peaks(
        sig_search,
        height=-1,
        distance=peak_distance,
        prominence=peak_prominence_min,
        width=(peak_width_min, peak_width_max),
    )
    neg_idx, _ = find_peaks(
        -sig_search,
        height=-1,
        distance=peak_distance,
        prominence=peak_prominence_min,
        width=(peak_width_min, peak_width_max),
    )

    candidates = []
    if pos_idx.size:
        candidates.append(int(pos_idx[0]))
    if neg_idx.size:
        candidates.append(int(neg_idx[0]))
    if not candidates:
        return None, "Reference peak was not found because no positive or negative peak was found in the first 30% of the full signal."

    idx0 = min(candidates)
    return float(time_search[idx0]), None


def shift_signal(
    shift_on: bool,
    signal: Sequence[float],
    time: Sequence[float],
    peak_distance: int,
    peak_prominence_min: float,
    peak_width_min: int,
    peak_width_max: int | None,
    dt: float,
):
    """Pick a zero-shift amount from the earliest positive or negative peak in the first 30% of the full signal."""
    if not shift_on:
        return 0.0, None

    time_arr = np.asarray(time, dtype=float)
    ref_time, warning = find_reference_peak_time(
        signal,
        time,
        peak_distance,
        peak_prominence_min,
        peak_width_min,
        peak_width_max,
    )
    if ref_time is None:
        if warning is None:
            warning = "Zero shift was not applied because the reference peak could not be found."
        else:
            warning = warning.replace("Reference peak was not found", "Zero shift was not applied")
        return 0.0, warning

    shift = float(ref_time - time_arr[0])
    return shift, None

def butter_lowpass(cutoff_lp, cutoff_hp, fs, order):
    """Design LP/HP/BP in SOS form; returns 'skip_filtering' if both cutoffs are None/0."""
    order = 1 if (order is None or order < 1) else int(order)
    nyq = 0.5 * fs

    if cutoff_lp == 0:
        cutoff_lp = None
    if cutoff_hp == 0:
        cutoff_hp = None

    if cutoff_lp and not cutoff_hp:
        return butter(order, cutoff_lp / nyq, btype="lowpass", output="sos")
    if cutoff_hp and not cutoff_lp:
        return butter(order, cutoff_hp / nyq, btype="highpass", output="sos")
    if cutoff_lp and cutoff_hp:
        if cutoff_lp < cutoff_hp:
            cutoff_lp, cutoff_hp = cutoff_hp, cutoff_lp
        return butter(order, [cutoff_hp / nyq, cutoff_lp / nyq], btype="bandpass", output="sos")
    return "skip_filtering"


def butter_lowpass_filter(data, cutoff_lp, cutoff_hp, fs, order, forward_backward_filter: bool):
    sos = butter_lowpass(cutoff_lp, cutoff_hp, fs, order=order)
    if isinstance(sos, str):
        return np.asarray(data)
    return sosfiltfilt(sos, data) if forward_backward_filter else sosfilt(sos, data)


def get_spectrum(amp: Sequence[float], dt: float, N: int):
    y = np.asarray(amp, float)
    yf = np.abs(rfft(y)) / N
    xf = rfftfreq(len(y), dt)
    return xf, yf


def hex2rgb(hex_code: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' or '#RGB' в†’ (R, G, B) in 0..255."""
    h = hex_code[1:] if hex_code.startswith("#") else hex_code
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError("Hex code must be 3 or 6 hex chars.")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return r, g, b


def arrange_cmap_limits(cmap_min, cmap_max, z, *, center_zero: bool = False):
    z = np.asarray(z)
    auto_min = np.min(z)
    auto_max = np.max(z)

    if center_zero:
        if cmap_min is None and cmap_max is None:
            span = max(abs(auto_min), abs(auto_max))
            return -span, span
        if cmap_min is None:
            span = abs(cmap_max)
            return -span, span
        if cmap_max is None:
            span = abs(cmap_min)
            return -span, span

    vmin = auto_min if cmap_min is None else cmap_min
    vmax = auto_max if cmap_max is None else cmap_max
    if vmin > vmax:
        vmin, vmax = vmax, vmin
    return vmin, vmax


def matplotlib_to_plotly(cmap_name: str, pl_entries: int):
    """Convert a Matplotlib colormap into a Plotly colorscale."""
    from matplotlib import colormaps  # local import to keep optional

    step = 1.0 / (pl_entries - 1)
    out = []
    for k in range(pl_entries):
        r, g, b, *_ = colormaps.get_cmap(cmap_name)(k * step)
        out.append([k * step, f"rgb({int(round(r*255))},{int(round(g*255))},{int(round(b*255))})"])
    return out


def make_plotly_colorscale(color_list_01: Iterable[Tuple[float, float, float]]):
    """Build a Plotly colorscale from 0..1 RGB tuples."""
    lst = list(color_list_01)
    n = len(lst)
    if n == 0:
        return [[0.0, "rgb(0,0,0)"]]
    scale = []
    for i, (r, g, b) in enumerate(lst):
        pos = i / (n - 1) if n > 1 else 0.0
        R, G, B = int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
        scale.append([pos, f"rgb({R},{G},{B})"])
    return scale


def _aa_lpf_sos(cut_hz: float, fs_hz: float, order: int = 8):
    nyq = 0.5 * fs_hz
    cut = min(max(cut_hz, 1.0), nyq * 0.99) / nyq
    return butter(order, cut, btype="lowpass", output="sos")

def decimate_factor_per_file(
    t_ms: np.ndarray,
    y: np.ndarray,
    fs_hz: float,
    d_user: int,
    f_need_hz: float,
    ensure_min_samples: int = 50,
    gamma: float = 2.2,
    anti_alias: bool = True,
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """
    Integer decimation with safety caps.
    Returns (t_ms_out, y_out, fs_out_hz, d_used).
    """
    n = int(len(y))
    if n < 2 or fs_hz <= 0:
        return t_ms, y, fs_hz, 1

    d_nyq = max(1, int(np.floor(fs_hz / max(gamma * f_need_hz, 1.0))))
    d_len = max(1, int(np.floor(n / max(ensure_min_samples, 1))))
    d_cap = max(1, min(d_nyq, d_len))

    d_used = max(1, min(int(d_user), d_cap))
    if d_used == 1:
        return t_ms, y, fs_hz, 1

    fs_out = fs_hz / d_used
    if anti_alias:
        sos = _aa_lpf_sos(0.45 * fs_out, fs_hz, order=8)
        y_f = sosfiltfilt(sos, y)
    else:
        y_f = y

    return t_ms[::d_used].copy(), y_f[::d_used].copy(), fs_out, d_used


__all__ = [
    "regularized_fd_integrate",
    "amplificate_signal",
    "zero_baseline",
    "flip_signal_polarity",
    "round_up",
    "shift_signal",
    "find_reference_peak_time",
    "butter_lowpass",
    "butter_lowpass_filter",
    "get_spectrum",
    "hex2rgb",
    "arrange_cmap_limits",
    "matplotlib_to_plotly",
    "make_plotly_colorscale",
    "sp_detrend",
    "find_peaks",
    "sosfreqz",
    "BSpline",
    "splrep",
    "decimate_factor_per_file",
]



