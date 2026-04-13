"""Reusable SLT computation and formatting helpers."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

import numpy as np
from scipy.ndimage import gaussian_filter1d

from .superlet_complex import adaptive_slt, slt
from .signal_processing import arrange_cmap_limits


_COMPUTE_CACHE: OrderedDict[str, dict] = OrderedDict()
_COMPUTE_CACHE_MAXSIZE = 3


def cache_get(cache_key: str | None) -> dict | None:
    if not cache_key:
        return None
    entry = _COMPUTE_CACHE.get(cache_key)
    if entry is not None:
        _COMPUTE_CACHE.move_to_end(cache_key)
    return entry


def cache_set(cache_key: str, value: dict, *, maxsize: int = _COMPUTE_CACHE_MAXSIZE) -> None:
    _COMPUTE_CACHE[cache_key] = value
    _COMPUTE_CACHE.move_to_end(cache_key)
    while len(_COMPUTE_CACHE) > maxsize:
        _COMPUTE_CACHE.popitem(last=False)


def cache_clear() -> None:
    _COMPUTE_CACHE.clear()


def supports_log_colorscale(slt_out: str) -> bool:
    return slt_out in {"Power", "Abs"}


def log_floor_ratio_from_exponent(log_floor_exp) -> float:
    return float(10.0 ** float(log_floor_exp or 0.0))


def log_transform_nonnegative(z_values: np.ndarray, *, floor_ratio: float | None = None) -> tuple[np.ndarray, float | None]:
    finite = np.asarray(z_values, dtype=float)
    positive_values = finite[np.isfinite(finite) & (finite > 0)]
    if positive_values.size == 0:
        empty_log = np.full_like(finite, np.nan, dtype=float)
        empty_log[np.isfinite(finite)] = 0.0
        return empty_log, None

    if floor_ratio is not None:
        floor_ratio = max(float(floor_ratio), np.finfo(float).tiny)
        eps = max(float(np.nanmax(positive_values)) * floor_ratio, np.finfo(float).tiny)
    else:
        eps = max(float(np.min(positive_values)) * 0.1, np.finfo(float).tiny)
    return np.log10(np.maximum(finite, eps)), eps


def coi_edge_half_samples(
    *,
    frequencies: np.ndarray,
    sample_freq: float,
    slt_mode: str,
    superlet_set_mode: str,
    c_1: float,
    k_sd: float,
    support_sd: float,
    order_slt: float,
    order_min: float,
    order_max: float,
) -> np.ndarray:
    """Return the conservative COI edge half-width in samples for each frequency row."""
    freqs = np.asarray(frequencies, dtype=float)
    dt = 1.0 / float(sample_freq)

    if slt_mode == "adaptive":
        f_min = float(freqs[0])
        f_max = float(freqs[-1])
        if f_max > f_min:
            adaptive_order = float(order_min) + (float(order_max) - float(order_min)) * (freqs - f_min) / (f_max - f_min)
        else:
            adaptive_order = np.full_like(freqs, float(order_min))
        max_orders = np.ceil(adaptive_order)
    else:
        max_orders = np.full(freqs.shape, float(order_slt))

    if superlet_set_mode == "multiplicative":
        c_max = float(c_1) * max_orders
    else:
        c_max = float(c_1) + max_orders - 1.0

    sigma_t = c_max / (float(k_sd) * freqs)
    return np.ceil((float(support_sd) / 2.0) * sigma_t / dt).astype(int)


def apply_coi_nan_mask(
    matrix: np.ndarray,
    coi_half_samples: np.ndarray,
    *,
    mask_lowest_rows: int = 0,
    smooth_sigma_rows: float = 0.0,
) -> np.ndarray:
    """Set edge pixels to NaN in an (n_freq, n_time) matrix using per-row COI widths."""
    n_freq, n_time = matrix.shape
    coi_half = np.asarray(coi_half_samples, dtype=float).copy()

    if smooth_sigma_rows > 0:
        coi_half = gaussian_filter1d(coi_half, sigma=smooth_sigma_rows, mode="nearest")

    coi_half = np.clip(np.rint(coi_half), 0, n_time).astype(int)
    time_idx = np.arange(n_time)
    edge_start = time_idx[None, :] < coi_half[:, None]
    edge_end = time_idx[None, :] >= (n_time - coi_half[:, None])

    masked = np.asarray(matrix, dtype=float).copy()
    masked[edge_start | edge_end] = np.nan
    if mask_lowest_rows > 0:
        masked[: min(mask_lowest_rows, n_freq), :] = np.nan
    return masked


def arrange_slt_cmap_limits(cmap_min, cmap_max, z_values: np.ndarray, *, center_zero: bool = False):
    finite_values = np.asarray(z_values, dtype=float)
    finite_values = finite_values[np.isfinite(finite_values)]
    if finite_values.size == 0:
        finite_values = np.array([0.0], dtype=float)
    return arrange_cmap_limits(cmap_min, cmap_max, finite_values, center_zero=center_zero)


def prepare_slt_signal_input(
    time_values,
    signal_values,
    *,
    padding_ms: float,
    to_length: bool,
    wavespeed: float,
):
    time_arr = np.asarray(time_values, dtype=float)
    sig_arr = np.asarray(signal_values, dtype=float)
    if padding_ms <= 0 or time_arr.size < 2 or sig_arr.size < 2:
        return sig_arr, 0

    dt_display = float(abs(time_arr[1] - time_arr[0]))
    if dt_display <= 0:
        return sig_arr, 0
    dt_ms = (2000.0 * dt_display / float(wavespeed)) if to_length else dt_display
    if not np.isfinite(dt_ms) or dt_ms <= 0:
        return sig_arr, 0

    pad_samples = max(1, int(np.ceil(float(padding_ms) / dt_ms)))
    return np.pad(sig_arr, (pad_samples, pad_samples), mode="constant"), pad_samples


def _clean_frequency_grid(frequencies, sample_freq: float) -> np.ndarray:
    fmin = max(float(frequencies["fmin"]), 1e-6)
    fmax_requested = max(float(frequencies["fmax"]), fmin * 1.2)
    fmax = min(fmax_requested, 0.45 * float(sample_freq))
    if fmax <= fmin:
        fmax = fmin * 1.2
    count = max(1, int(round(float(frequencies["count"]))))
    return np.logspace(np.log10(fmin), np.log10(fmax), count)


def compute_slt_bundle(
    *,
    time_values,
    signal_values,
    source_name: str,
    to_length: bool,
    wavespeed: float,
    padding_ms: float,
    slt_mode: str,
    superlet_set_mode: str,
    superlet_phase_combination: str,
    freq_min,
    freq_max,
    freq_count,
    c_1,
    k_sd,
    support_sd,
    order_slt,
    order_min,
    order_max,
) -> dict:
    time_arr = np.asarray(time_values, dtype=float)
    sig_arr = np.asarray(signal_values, dtype=float)
    if time_arr.size < 2 or sig_arr.size < 2:
        raise ValueError("SLT source does not contain enough samples.")

    dt_display = float(abs(time_arr[1] - time_arr[0]))
    if dt_display <= 0:
        raise ValueError("SLT source time step is invalid.")
    dt_ms = (2000.0 * dt_display / float(wavespeed)) if to_length else dt_display
    if not np.isfinite(dt_ms) or dt_ms <= 0:
        raise ValueError("SLT source time step is invalid.")
    sample_freq = 1000.0 / dt_ms

    frequencies = _clean_frequency_grid(
        {"fmin": freq_min, "fmax": freq_max, "count": freq_count},
        sample_freq=sample_freq,
    )

    adaptive = str(slt_mode or "adaptive") == "adaptive"
    order_fixed = max(1, int(round(float(order_slt))))
    c1_value = max(float(c_1), 1.0)
    k_sd_value = max(float(k_sd), 1.0e-9)
    support_sd_value = max(float(support_sd), 1.0e-9)
    order_min_value = max(float(order_min), 1.0)
    order_max_value = max(order_min_value, float(order_max))

    slt_signal, pad_samples = prepare_slt_signal_input(
        time_arr,
        sig_arr,
        padding_ms=float(padding_ms or 0.0),
        to_length=bool(to_length),
        wavespeed=float(wavespeed),
    )

    if adaptive:
        spec = adaptive_slt(
            slt_signal,
            fs=sample_freq,
            frequencies=frequencies,
            order_min=order_min_value,
            order_max=order_max_value,
            c_1=c1_value,
            set_mode=superlet_set_mode,
            k_sd=k_sd_value,
            support_sd=support_sd_value,
            use_fft_cache=True,
            phase_combination=superlet_phase_combination,
        )
    else:
        spec = slt(
            slt_signal,
            fs=sample_freq,
            frequencies=frequencies,
            order=order_fixed,
            c_1=c1_value,
            set_mode=superlet_set_mode,
            k_sd=k_sd_value,
            support_sd=support_sd_value,
            use_fft_cache=True,
            phase_combination=superlet_phase_combination,
        )

    if pad_samples > 0:
        spec = spec[:, pad_samples:-pad_samples]

    return {
        "x": time_arr,
        "signal": sig_arr,
        "source_name": str(source_name),
        "sample_freq": float(sample_freq),
        "frequencies": np.asarray(frequencies, dtype=float),
        "spec": np.asarray(spec),
        "coi_settings": {
            "slt_mode": str(slt_mode or "adaptive"),
            "superlet_set_mode": str(superlet_set_mode or "multiplicative"),
            "c_1": c1_value,
            "k_sd": k_sd_value,
            "support_sd": support_sd_value,
            "order_slt": float(order_fixed),
            "order_min": order_min_value,
            "order_max": order_max_value,
        },
    }


def build_slt_matrix(spec: np.ndarray, slt_out: str) -> np.ndarray:
    if slt_out == "Power":
        return 2.0 * np.abs(spec) ** 2
    if slt_out == "Abs":
        return np.abs(spec)
    if slt_out == "Re":
        return np.real(spec)
    if slt_out == "Im":
        return np.imag(spec)
    return np.angle(spec) * 180.0 / np.pi


def maybe_apply_coi_mask(
    matrix: np.ndarray,
    *,
    frequencies: np.ndarray,
    sample_freq: float,
    coi_mask_on: bool,
    coi_settings: dict | None,
) -> np.ndarray:
    if not coi_mask_on or coi_settings is None:
        return np.asarray(matrix, dtype=float)
    coi_half = coi_edge_half_samples(
        frequencies=np.asarray(frequencies, dtype=float),
        sample_freq=float(sample_freq),
        **coi_settings,
    )
    return apply_coi_nan_mask(
        np.asarray(matrix, dtype=float),
        coi_half,
        mask_lowest_rows=2,
        smooth_sigma_rows=2,
    )


def attribute_requires_log_floor(metric_key: str) -> bool:
    return metric_key in {"log_power", "log_amp"}


def attribute_metric_label(metric_key: str) -> str:
    labels = {
        "power": "Power",
        "log_power": "log10(Power)",
        "amp": "Amp",
        "log_amp": "log10(Amp)",
        "re": "Re",
        "im": "Im",
        "phase": "Phase",
    }
    return labels[metric_key]


def attribute_metric_keys() -> list[str]:
    return ["power", "log_power", "amp", "log_amp", "re", "im", "phase"]


def _attribute_matrix(spec: np.ndarray, metric_key: str) -> tuple[np.ndarray, bool]:
    if metric_key == "power":
        return 2.0 * np.abs(spec) ** 2, False
    if metric_key == "log_power":
        matrix, _eps = log_transform_nonnegative(2.0 * np.abs(spec) ** 2)
        return matrix, False
    if metric_key == "amp":
        return np.abs(spec), False
    if metric_key == "log_amp":
        matrix, _eps = log_transform_nonnegative(np.abs(spec))
        return matrix, False
    if metric_key == "re":
        return np.real(spec), False
    if metric_key == "im":
        return np.imag(spec), False
    return np.angle(spec) * 180.0 / np.pi, True


def _rolling_reduce(values: np.ndarray, reducer: str, window_samples: int) -> np.ndarray:
    if window_samples <= 1:
        return np.asarray(values, dtype=float)

    arr = np.asarray(values, dtype=float)
    out = np.full_like(arr, np.nan, dtype=float)
    half = window_samples // 2
    reducer_value = str(reducer or "mean").lower()
    for idx in range(arr.size):
        start = max(0, idx - half)
        stop = min(arr.size, start + window_samples)
        start = max(0, stop - window_samples)
        window = arr[start:stop]
        finite = window[np.isfinite(window)]
        if finite.size == 0:
            continue
        if reducer_value == "median":
            out[idx] = float(np.median(finite))
        else:
            out[idx] = float(np.mean(finite))
    return out


def _zero_baseline_curve(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float).copy()
    finite_idx = np.flatnonzero(np.isfinite(arr))
    if finite_idx.size == 0:
        return arr
    baseline_idx = finite_idx[: min(10, finite_idx.size)]
    baseline = float(np.median(arr[baseline_idx]))
    arr -= baseline
    return arr


def _normalize_curve_like_signal(values: np.ndarray) -> tuple[np.ndarray, bool]:
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return arr, False
    scale = float(np.max(np.abs(finite)))
    if scale <= 0:
        return arr, False
    return arr / scale, True


def _break_phase_near_wrap(values: np.ndarray, *, jump_threshold_deg: float = 350.0) -> np.ndarray:
    arr = np.asarray(values, dtype=float).copy()
    if arr.size < 2:
        return arr

    threshold = max(float(jump_threshold_deg), 0.0)
    previous = arr[:-1]
    current = arr[1:]
    valid = np.isfinite(previous) & np.isfinite(current)
    wrap_jump = np.abs(current - previous) >= threshold
    arr[1:][valid & wrap_jump] = np.nan
    return arr


def build_slt_attribute_curves(
    *,
    spec: np.ndarray,
    x_values,
    frequencies: np.ndarray,
    sample_freq: float,
    metric_keys: Iterable[str],
    normalize_on: bool,
    zero_baseline_on: bool = True,
    freq_reduce: str,
    x_reduce: str,
    x_window_ms: float,
    band_min_hz,
    band_max_hz,
    phase_freq_hz,
    coi_mask_on: bool,
    coi_settings: dict | None,
) -> dict:
    selected = [str(item) for item in metric_keys if item in attribute_metric_keys()]
    if not selected:
        return {"curves": [], "messages": [], "has_phase": False}

    freq_arr = np.asarray(frequencies, dtype=float)
    x_arr = np.asarray(x_values, dtype=float)
    messages: list[str] = []
    curves: list[dict] = []

    band_min = None if band_min_hz in (None, "") else float(band_min_hz)
    band_max = None if band_max_hz in (None, "") else float(band_max_hz)
    if band_min is not None and band_max is not None and band_max < band_min:
        band_min, band_max = band_max, band_min

    single_bound_slice = (band_min is None) != (band_max is None)
    non_phase_target_freq = band_min if band_min is not None else band_max
    non_phase_mask = np.ones_like(freq_arr, dtype=bool)
    if not single_bound_slice:
        if band_min is not None:
            non_phase_mask &= freq_arr >= band_min
        if band_max is not None:
            non_phase_mask &= freq_arr <= band_max
        if not np.any(non_phase_mask):
            nearest_idx = int(np.argmin(np.abs(freq_arr - (band_min or band_max or freq_arr[0]))))
            non_phase_mask = np.zeros_like(freq_arr, dtype=bool)
            non_phase_mask[nearest_idx] = True
            messages.append("Attribute band fell outside the SLT grid. Nearest frequency was used.")

    window_samples = max(0, int(np.ceil(float(x_window_ms or 0.0) * float(sample_freq) / 1000.0)))
    freq_reducer = str(freq_reduce or "mean").lower()
    has_phase = False
    non_phase_normalized = False

    for key in selected:
        matrix, is_phase = _attribute_matrix(spec, key)
        matrix = maybe_apply_coi_mask(
            matrix,
            frequencies=freq_arr,
            sample_freq=float(sample_freq),
            coi_mask_on=bool(coi_mask_on),
            coi_settings=coi_settings,
        )

        if is_phase:
            has_phase = True
            target_freq = float(phase_freq_hz or freq_arr[0])
            row_idx = int(np.argmin(np.abs(freq_arr - target_freq)))
            y_values = np.asarray(matrix[row_idx, :], dtype=float)
            axis = "phase"
            actual_freq = float(freq_arr[row_idx])
            curve_name = f"Phase @ {actual_freq:.0f} Hz"
            normalized = False
            source_kind = "slice"
            source_frequency_hz = actual_freq
            source_band_min_hz = None
            source_band_max_hz = None
        else:
            if single_bound_slice:
                row_idx = int(np.argmin(np.abs(freq_arr - float(non_phase_target_freq or freq_arr[0]))))
                y_values = np.asarray(matrix[row_idx, :], dtype=float)
                source_kind = "slice"
                source_frequency_hz = float(freq_arr[row_idx])
                source_band_min_hz = None
                source_band_max_hz = None
            else:
                band_values = np.asarray(matrix[non_phase_mask, :], dtype=float)
                with np.errstate(invalid="ignore"):
                    if freq_reducer == "median":
                        y_values = np.nanmedian(band_values, axis=0)
                    else:
                        y_values = np.nanmean(band_values, axis=0)
                source_kind = "band"
                source_frequency_hz = None
                source_band_min_hz = float(freq_arr[0]) if band_min is None else float(band_min)
                source_band_max_hz = float(freq_arr[-1]) if band_max is None else float(band_max)
            axis = "value"
            curve_name = attribute_metric_label(key)
            normalized = False
            if zero_baseline_on:
                y_values = _zero_baseline_curve(y_values)

        if window_samples > 1:
            y_values = _rolling_reduce(y_values, x_reduce, window_samples)

        if is_phase:
            y_values = _break_phase_near_wrap(y_values, jump_threshold_deg=350.0)

        if not is_phase and normalize_on:
            y_values, normalized = _normalize_curve_like_signal(y_values)
            if normalized:
                non_phase_normalized = True

        curves.append(
            {
                "key": key,
                "name": curve_name,
                "x": x_arr,
                "y": np.asarray(y_values, dtype=float),
                "axis": axis,
                "normalized": normalized,
                "source_kind": source_kind,
                "source_frequency_hz": source_frequency_hz,
                "source_band_min_hz": source_band_min_hz,
                "source_band_max_hz": source_band_max_hz,
            }
        )

    return {
        "curves": curves,
        "messages": messages,
        "has_phase": has_phase,
        "has_non_phase": any(curve["axis"] != "phase" for curve in curves),
        "non_phase_normalized": non_phase_normalized,
    }
