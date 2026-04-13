"""Dash callbacks for echopile."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dash import dcc, html, ctx, callback, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import MissingCallbackContextException, PreventUpdate
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from scipy.integrate import cumulative_trapezoid

from ...config import (
    SPECTRUM_PLOT_HEIGHT_PX,
    LINECOLOR_TIMEPLOT,
    ALPHA_TRACE,
    LIST_COLORS,
    COLORSCALE_PHASE,
    CUSTOM_CMAP_COLORS,
    SETTINGS_ROW_STYLE,
    SLIDER_SETTINGS_ROW_STYLE,
    DMC_SLIDER_STYLES,
    DMC_SLIDER_WRAPPER_STYLE,
    MAX_UPLOAD_FILE_MB,
    MAX_UPLOAD_TOTAL_MB,
    MAX_UPLOAD_FILE_BYTES,
    MAX_UPLOAD_TOTAL_BYTES,
)
from ...translations import translate
from ...core.superlet_complex import slt, adaptive_slt
from ...core.io_readers import (
    build_zbl_labels,
    decode_txt_upload,
    is_zbl_txt,
    parse_contents,
    parse_plain_columns_table,
    parse_zbl_sections,
)
from ...core.settings_defaults import SNC_UI_SETTING_KEYS, get_snc_ui_defaults_list, get_snc_ui_defaults_map
from ...core.processing_pipeline import ensure_time_ms_df as core_ensure_time_ms_df, process_signals as core_process_signals
from ...core.snc_io import normalize_snc_settings_for_ui, serialize_snc_text
from ...core.slt_analysis import (
    apply_coi_nan_mask as _apply_coi_nan_mask,
    arrange_slt_cmap_limits as _arrange_slt_cmap_limits,
    attribute_metric_keys as _attribute_metric_keys,
    build_slt_attribute_curves as _build_slt_attribute_curves,
    build_slt_matrix as _build_slt_matrix,
    cache_get as _slt_cache_get,
    cache_set as _slt_cache_set,
    coi_edge_half_samples as _coi_edge_half_samples,
    compute_slt_bundle as _compute_slt_bundle,
    log_floor_ratio_from_exponent as _log_floor_ratio_from_exponent,
    log_transform_nonnegative as _log_transform_nonnegative_slt,
    maybe_apply_coi_mask as _maybe_apply_coi_mask,
    supports_log_colorscale as _supports_slt_log_colorscale,
)
from ...core.signal_processing import (
    amplificate_signal,
    round_up,
    shift_signal,
    find_reference_peak_time,
    butter_lowpass,
    butter_lowpass_filter,
    get_spectrum,
    hex2rgb,
    matplotlib_to_plotly,
    make_plotly_colorscale,
    sp_detrend,
    find_peaks,
    sosfreqz,
    BSpline,
    splrep,
    decimate_factor_per_file,
    regularized_fd_integrate,
    zero_baseline,
    flip_signal_polarity,
)

logger = logging.getLogger(__name__)

UI_DEFAULTS = get_snc_ui_defaults_map()


# ---------- helpers ----------
def _current_triggered_id():
    try:
        return ctx.triggered_id
    except MissingCallbackContextException:
        return None


def _rgba_from_hex(hex_color: str, alpha: float) -> str:
    r, g, b = hex2rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"

def _upload_stem(filename: str) -> str:
    if filename.lower().endswith(".pp.csv"):
        return Path(Path(filename).stem).stem
    return Path(filename).stem


def _parsed_signal_name(filename: str, label: str) -> str:
    return f"{_upload_stem(filename)}[{label}]"


def _ensure_time_ms_df(
    df: pd.DataFrame,
    meta: Optional[dict] = None,
    time_unit_override: Optional[str] = None,
) -> pd.DataFrame:
    return core_ensure_time_ms_df(df, meta, time_unit_override)


def _spectrum_full_xmax(
    freq_series: list[np.ndarray],
    filter_response_freq: Optional[np.ndarray] = None,
) -> Optional[float]:
    maxima: list[float] = []
    for freq in freq_series:
        freq_arr = np.asarray(freq, dtype=float)
        finite = freq_arr[np.isfinite(freq_arr)]
        if finite.size:
            maxima.append(float(finite.max()))

    if filter_response_freq is not None:
        w_arr = np.asarray(filter_response_freq, dtype=float)
        finite_w = w_arr[np.isfinite(w_arr)]
        if finite_w.size:
            maxima.append(float(finite_w.max()))

    return max(maxima) if maxima else None


def _spectrum_autozoom_xmax(
    freq_series: list[np.ndarray],
    amp_series: list[np.ndarray],
    *,
    freq_floor_hz: float = 500.0,
    threshold_fraction: float = 0.01,
) -> Optional[float]:
    cutoffs: list[float] = []

    for freq, amp in zip(freq_series, amp_series):
        freq_arr = np.asarray(freq, dtype=float)
        amp_arr = np.asarray(amp, dtype=float)
        valid = np.isfinite(freq_arr) & np.isfinite(amp_arr) & (freq_arr >= freq_floor_hz)
        if not np.any(valid):
            continue

        freq_valid = freq_arr[valid]
        amp_valid = amp_arr[valid]
        ref = float(np.nanmax(amp_valid))
        if not np.isfinite(ref) or ref <= 0:
            continue

        threshold = threshold_fraction * ref
        above = np.flatnonzero(amp_valid > threshold)
        if above.size:
            cutoffs.append(float(freq_valid[above[-1]]))

    return max(cutoffs) if cutoffs else None

def _integration_times_for_signal(signal_meta: Optional[dict], integration_mode: str) -> int:
    default_integrations = int((signal_meta or {}).get("default_integrations", 0) or 0)
    if integration_mode == "Auto":
        return default_integrations
    if integration_mode == "Off":
        return 0
    if integration_mode == "x1":
        return 1
    if integration_mode == "x2":
        return 2
    return default_integrations


def _preprocess_before_amplification(
    df_in: pd.DataFrame,
    signal_meta: Optional[dict],
    *,
    flip_polarity: bool,
    d_user: int,
    aa_on: bool,
    f_lp: Optional[float],
    integration_mode: str,
    integration_method: str,
    integration_low_frequency_hz: float,
    integration_zero_baseline: bool,
    detrend_on: bool,
    detrend_after_amp: bool,
) -> pd.DataFrame:
    df = flip_signal_polarity(df_in, flip_polarity)
    if len(df) < 10:
        raise ValueError("A loaded trace has fewer than 10 points.")

    dt_ms = float(np.median(np.diff(df["time"].to_numpy(float))))
    fs_in = 1000.0 / dt_ms
    f_need = max(4000.0, float(f_lp or 0))
    t2, y2, _fs_out, d_used = decimate_factor_per_file(
        t_ms=df["time"].to_numpy(float),
        y=df["amp"].to_numpy(float),
        fs_hz=fs_in,
        d_user=int(d_user or 1),
        f_need_hz=f_need,
        ensure_min_samples=50,
        gamma=2.2,
        anti_alias=bool(aa_on),
    )

    if d_used > 1:
        df = pd.DataFrame({"time": t2, "amp": y2})

    if len(df) < 10:
        raise ValueError("Trace fell below 10 points after decimation. Reduce the downsampling factor.")

    if integration_zero_baseline:
        df = zero_baseline(df)

    integration_times = _integration_times_for_signal(signal_meta, integration_mode)
    if integration_times > 0:
        amp_in = df["amp"].to_numpy(float)
        time_s = df["time"].to_numpy(float) / 1000.0
        if integration_method == "cumulative_trapezoid":
            if integration_times == 1:
                amp_out = cumulative_trapezoid(amp_in, time_s, initial=0.0)
            else:
                vel = cumulative_trapezoid(amp_in, time_s, initial=0.0)
                amp_out = cumulative_trapezoid(vel, time_s, initial=0.0)
        else:
            fs_current = 1000.0 / float(np.median(np.diff(df["time"].to_numpy(float))))
            amp_out = regularized_fd_integrate(
                amp_in,
                fs=fs_current,
                low_frequency_hz=float(integration_low_frequency_hz or 10.0),
                times=integration_times,
            )
        df = df.copy()
        df["amp"] = amp_out

        if integration_zero_baseline:
            df = zero_baseline(df)

    if detrend_on and not detrend_after_amp:
        df = df.copy()
        df["amp"] = sp_detrend(df["amp"].to_numpy(), type="linear")

    m = max(abs(df["amp"])) or 1.0
    df = df.copy()
    df["amp"] = df["amp"] / m

    return df


def _apply_filter_reference_before_amplification(
    df_in: pd.DataFrame,
    *,
    filt_on: bool,
    filter_before_amp: bool,
    f_lp: Optional[float],
    f_hp: Optional[float],
    f_ord: Optional[int],
    fwd_bwd: bool,
) -> pd.DataFrame:
    if not (filter_before_amp and filt_on):
        return df_in

    amp = df_in["amp"]
    fs = 1000.0 / float(df_in["time"].iloc[1] - df_in["time"].iloc[0])
    sos = butter_lowpass(f_lp, f_hp, fs, f_ord)
    if isinstance(sos, str):
        return df_in

    af = butter_lowpass_filter(amp, f_lp, f_hp, fs, f_ord, fwd_bwd)
    df_out = df_in.copy()
    df_out["amp"] = np.asarray(af[: len(df_in)])
    df_out["time"] = pd.Series([(1000.0 / fs) * i for i in range(len(df_out))])
    return df_out


def _shift_amount_ms(
    df_ref: pd.DataFrame,
    *,
    shift_on: bool,
    pk_dist: int,
    pk_prom: float,
    pk_wmin: int,
    pk_wmax: Optional[int],
) -> tuple[float, Optional[str]]:
    dt = float(df_ref["time"].iloc[1] - df_ref["time"].iloc[0])
    return shift_signal(
        shift_on,
        df_ref["amp"],
        df_ref["time"],
        pk_dist,
        pk_prom,
        pk_wmin,
        pk_wmax,
        dt,
    )


def _empty_peak_markers():
    return [[[None], [None]], [[None], [None]]]


def _build_peak_markers(x_values, amp_values, pk_dist, pk_prom, pk_wmin, pk_wmax):
    x = pd.Series(x_values).reset_index(drop=True)
    y = pd.Series(amp_values).reset_index(drop=True)
    if len(x) < 2 or len(y) < 2:
        return _empty_peak_markers()

    p_pos, _ = find_peaks(y, distance=pk_dist, prominence=pk_prom, width=(pk_wmin, pk_wmax))
    p_neg, _ = find_peaks(-y, distance=pk_dist, prominence=pk_prom, width=(pk_wmin, pk_wmax))

    peaks_pos = [x.iloc[p_pos].to_list(), y.iloc[p_pos].to_list()] if p_pos.size else [[None], [None]]
    peaks_neg = [x.iloc[p_neg].to_list(), y.iloc[p_neg].to_list()] if p_neg.size else [[None], [None]]
    return [peaks_pos, peaks_neg]


def _max_display_end_ms(
    raw_signals,
    signal_assumptions,
    *,
    detrend_on: bool,
    detrend_after_amp: bool,
    shift_on: bool,
    flip_polarity: bool,
    pk_dist: int,
    pk_wmin: int,
    pk_wmax: Optional[int],
    pk_prom: float,
    integration_mode: str,
    integration_method: str,
    integration_low_frequency_hz: float,
    integration_zero_baseline: bool,
    filt_on: bool,
    filter_before_amp: bool,
    fwd_bwd: bool,
    f_lp: Optional[float],
    f_hp: Optional[float],
    f_ord: Optional[int],
    d_user: int,
    aa_on: bool,
) -> Optional[float]:
    if not raw_signals:
        return None

    display_ends: list[float] = []
    for idx, rs in enumerate(raw_signals):
        signal_meta = signal_assumptions[idx] if signal_assumptions and idx < len(signal_assumptions) else {
            "assumed_input": "Unknown",
            "default_integrations": 0,
            "time_unit": "ms",
            "time_unit_known": True,
        }
        df_raw = pd.DataFrame(rs).reset_index(drop=True)
        try:
            df_ref = _preprocess_before_amplification(
                df_raw,
                signal_meta,
                flip_polarity=flip_polarity,
                d_user=d_user,
                aa_on=aa_on,
                f_lp=f_lp,
                integration_mode=integration_mode,
                integration_method=integration_method,
                integration_low_frequency_hz=integration_low_frequency_hz,
                integration_zero_baseline=integration_zero_baseline,
                detrend_on=detrend_on,
                detrend_after_amp=detrend_after_amp,
                )
            df_ref = _apply_filter_reference_before_amplification(
                df_ref,
                filt_on=filt_on,
                filter_before_amp=filter_before_amp,
                f_lp=f_lp,
                f_hp=f_hp,
                f_ord=f_ord,
                fwd_bwd=fwd_bwd,
            )
        except ValueError:
            continue

        full_end_ms = float(df_ref["time"].max())
        shift_amount_ms = 0.0
        if shift_on:
            shift_amount_ms, _warning = _shift_amount_ms(
                df_ref,
                shift_on=shift_on,
                pk_dist=pk_dist,
                pk_prom=pk_prom,
                pk_wmin=pk_wmin,
                pk_wmax=pk_wmax,
            )
        display_ends.append(max(0.0, full_end_ms - shift_amount_ms))

    return max(display_ends) if display_ends else None


def _signal_end_slider_step(max_value: float) -> float:
    if not np.isfinite(max_value) or max_value <= 0:
        return 0.1
    if max_value >= 10.0:
        return 0.1
    exponent = int(np.floor(np.log10(max_value))) - 2
    return float(10.0 ** exponent)


def _step_decimals(step: float) -> int:
    if not np.isfinite(step) or step <= 0 or step >= 1:
        return 0
    return max(0, int(round(-np.log10(step))))


def _window_length_display(value_ms, to_length, wavespeed):
    value_ms = max(0.0, float(value_ms or 0.0))
    unit_scale = (float(wavespeed) / 2000.0) if to_length else 1.0
    step_value = max(0.001, 0.01 * unit_scale)
    decimals = max(2, _step_decimals(step_value))
    return round(value_ms * unit_scale, decimals), step_value, decimals


def _render_window_length_input(value_ms, to_length, wavespeed, *, input_id: str):
    display_value, step_value, decimals = _window_length_display(value_ms, to_length, wavespeed)
    return dmc.NumberInput(
        id=input_id,
        size="xs",
        min=0,
        step=step_value,
        decimalScale=decimals,
        fixedDecimalScale=False,
        value=display_value,
    )


def _axis_position_display(value_ms, to_length, wavespeed):
    if value_ms in (None, ""):
        unit_scale = (float(wavespeed) / 2000.0) if to_length else 1.0
        step_value = max(0.001, 0.01 * unit_scale)
        decimals = max(2, _step_decimals(step_value))
        return None, step_value, decimals
    return _window_length_display(value_ms, to_length, wavespeed)


def _render_axis_position_input(value_ms, to_length, wavespeed, *, input_id: str):
    display_value, step_value, decimals = _axis_position_display(value_ms, to_length, wavespeed)
    return dmc.NumberInput(
        id=input_id,
        size="xs",
        min=0,
        step=step_value,
        decimalScale=decimals,
        fixedDecimalScale=False,
        value=display_value,
    )


def _dmc_slider_marks(marks):
    if not marks:
        return None
    converted = []
    for value in sorted(marks, key=float):
        item = marks[value]
        label = item.get("label", "") if isinstance(item, dict) else str(item)
        converted.append({"value": float(value), "label": label})
    return converted


def _translated_slt_output_data(lang: str) -> list[dict[str, str]]:
    return [
        {"value": "Power", "label": translate("Power", lang)},
        {"value": "Abs", "label": translate("Amp", lang)},
        {"value": "Arg", "label": translate("Phase", lang)},
        {"value": "Re", "label": translate("Re", lang)},
        {"value": "Im", "label": translate("Im", lang)},
    ]


def _translated_cycle_scaling_data(lang: str) -> list[dict[str, str]]:
    return [
        {"value": "multiplicative", "label": translate("Multiplicative", lang)},
        {"value": "additive", "label": translate("Additive", lang)},
    ]


def _resolve_slt_colorscale(cmap_name: str):
    if cmap_name == "Default":
        return make_plotly_colorscale(CUSTOM_CMAP_COLORS)
    if cmap_name == "nipy_spectral":
        return matplotlib_to_plotly("nipy_spectral", 255)
    if cmap_name == "colorscale_phase":
        return COLORSCALE_PHASE
    return cmap_name


def _stable_value_token(value) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, list):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _hash_numeric_array(values) -> str:
    arr = np.asarray(values, dtype=float)
    return hashlib.sha1(np.ascontiguousarray(arr).tobytes()).hexdigest()[:16]


def _current_slt_source(data, av_signal, filenames, lang):
    if av_signal and av_signal != [[], []]:
        return (
            np.asarray(av_signal[0], dtype=float),
            np.asarray(av_signal[1], dtype=float),
            translate("AV", lang),
        )
    df0 = pd.DataFrame(data[0][0])
    return df0["time"].to_numpy(float), df0["amp"].to_numpy(float), filenames[0]


def _build_slt_cache_key(
    *,
    x_values,
    signal_values,
    source_name: str,
    to_length: bool,
    wavespeed,
    padding_ms,
    slt_mode,
    superlet_set_mode,
    superlet_phase_combination,
    freq_min,
    freq_max,
    freq_count,
    c_1,
    k_sd,
    support_sd,
    order_slt,
    order_min,
    order_max,
) -> str:
    payload = {
        "source_name": str(source_name),
        "x_hash": _hash_numeric_array(x_values),
        "signal_hash": _hash_numeric_array(signal_values),
        "to_length": bool(to_length),
        "wavespeed": _stable_value_token(wavespeed),
        "padding_ms": _stable_value_token(padding_ms),
        "slt_mode": str(slt_mode),
        "set_mode": str(superlet_set_mode),
        "phase_mode": str(superlet_phase_combination),
        "freq_min": _stable_value_token(freq_min),
        "freq_max": _stable_value_token(freq_max),
        "freq_count": _stable_value_token(freq_count),
        "c_1": _stable_value_token(c_1),
        "k_sd": _stable_value_token(k_sd),
        "support_sd": _stable_value_token(support_sd),
        "order_slt": _stable_value_token(order_slt),
        "order_min": _stable_value_token(order_min),
        "order_max": _stable_value_token(order_max),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:20]


def _prepare_slt_heatmap_data(
    *,
    spec: np.ndarray,
    slt_out: str,
    log_colorscale: bool,
    log_floor_exp,
    coi_mask_on: bool,
    cmin,
    cmax,
    lang: str,
    to_length: bool,
    x_unit: str,
    t,
    foi,
    sample_freq: float,
    coi_settings: dict | None,
    source_name: str,
):
    z_values = _build_slt_matrix(spec, slt_out)

    degree = "°"
    display_meta = {
        "Power": {"label": translate("Power", lang), "unit": "", "fmt": ".3g"},
        "Abs": {"label": translate("Amp", lang), "unit": "", "fmt": ".3g"},
        "Arg": {"label": translate("Phase", lang), "unit": degree, "fmt": ".1f"},
        "Re": {"label": translate("Re", lang), "unit": "", "fmt": ".3g"},
        "Im": {"label": translate("Im", lang), "unit": "", "fmt": ".3g"},
    }
    meta = display_meta[slt_out]

    z_values = _maybe_apply_coi_mask(
        z_values,
        frequencies=np.asarray(foi, dtype=float),
        sample_freq=float(sample_freq),
        coi_mask_on=bool(coi_mask_on),
        coi_settings=coi_settings,
    )

    z_display = z_values
    colorbar_title = meta["label"] + (", " + meta["unit"] if meta["unit"] else "")
    extra_hover_line = ""
    raw_values = None
    if log_colorscale and _supports_slt_log_colorscale(slt_out):
        raw_values = z_values
        z_display, eps = _log_transform_nonnegative_slt(
            z_values,
            floor_ratio=_log_floor_ratio_from_exponent(log_floor_exp),
        )
        colorbar_title = f"log10({meta['label']})"
        if eps is None:
            extra_hover_line = "<br>log10(" + meta["label"] + "): 0"
        else:
            extra_hover_line = "<br>log10(" + meta["label"] + "): %{z:.3f}"

    vmin, vmax = _arrange_slt_cmap_limits(cmin, cmax, z_display, center_zero=slt_out in {"Re", "Im"})
    x_hover_label = translate("Depth, m", lang).split(",")[0] if to_length else translate("Time, ms", lang).split(",")[0]
    y_hover_label = translate("Frequency, Hz", lang).split(",")[0]
    if raw_values is None:
        hover_value = "%{z:" + meta["fmt"] + "}"
    else:
        hover_value = "%{customdata:" + meta["fmt"] + "}"
    hovertemplate = (
        "<b>%{text}</b><br>"
        + x_hover_label + ": %{x:.2f} " + x_unit + "<br>"
        + y_hover_label + ": %{y:.0f} Hz<br>"
        + meta["label"] + ": " + hover_value + meta["unit"]
        + extra_hover_line
        + "<extra></extra>"
    )

    return {
        "x": t,
        "y": foi,
        "z": z_display,
        "customdata": raw_values,
        "text": [[source_name] * len(t)] * len(foi),
        "hovertemplate": hovertemplate,
        "colorbar_title": colorbar_title,
        "vmin": vmin,
        "vmax": vmax,
    }


def _add_slt_heatmap_trace(
    fig,
    slt_plot_data: dict,
    cmap,
    *,
    row: int,
    col: int,
    figure_height_px: float,
    colorbar_offset: float = 0.01,
    colorbar_len_factor: float = 0.95,
    colorbar_thickness: int = 15,
    colorbar_title_font_size: int = 15,
    colorbar_x_override: float | None = None,
) -> None:
    fig.add_trace(
        go.Heatmap(
            x=slt_plot_data["x"],
            y=slt_plot_data["y"],
            z=slt_plot_data["z"],
            customdata=slt_plot_data["customdata"],
            text=slt_plot_data["text"],
            hovertemplate=slt_plot_data["hovertemplate"],
            colorscale=cmap,
            zmin=slt_plot_data["vmin"],
            zmax=slt_plot_data["vmax"],
            name="SLT",
        ),
        row=row,
        col=col,
    )
    trace = fig.data[-1]
    axis_ref = str(getattr(trace, "yaxis", "y") or "y")
    layout_axis_name = "yaxis" if axis_ref == "y" else f"yaxis{axis_ref[1:]}"
    axis_layout = getattr(fig.layout, layout_axis_name, None)
    domain = tuple(getattr(axis_layout, "domain", (0.0, 1.0)) or (0.0, 1.0))
    domain_min, domain_max = float(domain[0]), float(domain[1])
    domain_span = max(domain_max - domain_min, 1e-6)
    xaxis_layout = getattr(fig.layout, _layout_axis_name(getattr(trace, "xaxis", "x"), "x"), None)
    x_domain = tuple(getattr(xaxis_layout, "domain", (0.0, 1.0)) or (0.0, 1.0))
    colorbar_x = (
        float(colorbar_x_override)
        if colorbar_x_override is not None
        else float(x_domain[1]) + float(colorbar_offset)
    )
    colorbar_len_px = max(40.0, float(colorbar_len_factor) * float(figure_height_px) * domain_span)
    trace.colorbar = dict(
        title=dict(text=slt_plot_data["colorbar_title"], side="top", font=dict(size=colorbar_title_font_size)),
        len=colorbar_len_px,
        lenmode="pixels",
        y=0.5 * (domain_min + domain_max),
        yanchor="middle",
        x=colorbar_x,
        xanchor="left",
        xpad=0,
        thickness=colorbar_thickness,
        tickmode="auto",
        nticks=5,
    )


def _add_global_marker(fig, marker_x, marker_label: str, positions: list[tuple[int, int]], *, annotation_xref: str = "x") -> None:
    if marker_x in (None, ""):
        return
    marker_color = "#C2185B"
    _add_vertical_reference_lines(
        fig,
        positions,
        float(marker_x),
        line_width=3,
        line_dash="dash",
        line_color=marker_color,
    )
    marker_label = str(marker_label or "").strip()
    if marker_label:
        fig.add_annotation(
            x=float(marker_x),
            y=1.0,
            xref=annotation_xref,
            yref="paper",
            text=marker_label,
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor=marker_color,
            borderwidth=1,
        )


def _effective_attribute_placement(placement: str, attribute_data: dict) -> str:
    selected = list(attribute_data.get("curves") or [])
    if not selected:
        return str(placement or "below_slt")
    has_phase = bool(attribute_data.get("has_phase"))
    has_non_phase = bool(attribute_data.get("has_non_phase"))
    non_phase_normalized = bool(attribute_data.get("non_phase_normalized"))
    if str(placement or "below_slt") == "signal" and has_phase and has_non_phase and not non_phase_normalized:
        return "below_slt"
    return str(placement or "below_slt")


_PHASE_AXIS_TICKS = [-180.0, -90.0, 0.0, 90.0, 180.0]


def _time_plot_graph_config(filename: str) -> dict:
    return {
        "displaylogo": True,
        "toImageButtonOptions": {"filename": filename, "scale": 10},
        "modeBarButtonsToRemove": ["pan", "select", "zoomIn", "zoomOut", "lasso2d"],
    }


def _horizontal_time_plot_grid(
    has_slt_row: bool,
    has_attr_row: bool,
    *,
    signal_secondary_y: bool,
    attr_secondary_y: bool,
) -> tuple[int, list[list[dict | None]], list[float], dict[str, tuple[int, int]]]:
    if has_slt_row and has_attr_row:
        return (
            5,
            [[{"secondary_y": signal_secondary_y}, None, {"secondary_y": False}, None, {"secondary_y": attr_secondary_y}]],
            [1.0, 0.14, 1.0, 0.06, 1.0],
            {"signal": (1, 1), "slt": (1, 3), "attr": (1, 5)},
        )
    if has_slt_row:
        return (
            2,
            [[{"secondary_y": signal_secondary_y}, {"secondary_y": False}]],
            [1.0, 1.0],
            {"signal": (1, 1), "slt": (1, 2)},
        )
    return (
        2,
        [[{"secondary_y": signal_secondary_y}, {"secondary_y": attr_secondary_y}]],
        [1.0, 1.0],
        {"signal": (1, 1), "attr": (1, 2)},
    )


def _metric_axis_title(curve: dict) -> str:
    if str(curve.get("axis")) == "phase":
        return "Phase, °"
    title = str(curve.get("name") or "").strip() or str(curve.get("key") or "")
    if bool(curve.get("normalized")):
        title += " (norm.)"
    return title


def _normalize_y_axis_exponent_format(value) -> str:
    if value in {"none", "E", "power", "B", "SI"}:
        return str(value)
    return "SI"


def _format_frequency_hz(value) -> str:
    numeric = float(value)
    if not np.isfinite(numeric):
        return ""
    if np.isclose(numeric, round(numeric), atol=1e-9):
        return str(int(round(numeric)))
    return f"{numeric:.4g}"


def _attribute_source_badge_text(curve: dict) -> str:
    if str(curve.get("source_kind")) == "slice":
        return f"slice {_format_frequency_hz(curve.get('source_frequency_hz'))} Hz"
    band_min = curve.get("source_band_min_hz")
    band_max = curve.get("source_band_max_hz")
    return f"band {_format_frequency_hz(band_min)}-{_format_frequency_hz(band_max)} Hz"


def _layout_axis_name(axis_ref: str, axis_letter: str) -> str:
    axis_ref = str(axis_ref or axis_letter)
    if axis_ref == axis_letter:
        return f"{axis_letter}axis"
    return f"{axis_letter}axis{axis_ref[1:]}"


def _add_single_attribute_badge(fig, curve: dict, *, row: int, col: int) -> None:
    if row is None:
        return
    matching_trace = None
    for trace in reversed(fig.data):
        if str(getattr(trace, "name", "")) == str(curve.get("name", "")):
            matching_trace = trace
            break
    if matching_trace is None:
        return
    xaxis_layout = getattr(fig.layout, _layout_axis_name(getattr(matching_trace, "xaxis", "x"), "x"), None)
    yaxis_layout = getattr(fig.layout, _layout_axis_name(getattr(matching_trace, "yaxis", "y"), "y"), None)
    x_domain = tuple(getattr(xaxis_layout, "domain", (0.0, 1.0)) or (0.0, 1.0))
    y_domain = tuple(getattr(yaxis_layout, "domain", (0.0, 1.0)) or (0.0, 1.0))
    x_right = float(x_domain[1]) - 0.008
    y_top = float(y_domain[1]) - 0.02 * max(float(y_domain[1]) - float(y_domain[0]), 1e-6)
    fig.add_annotation(
        x=x_right,
        y=y_top,
        xref="paper",
        yref="paper",
        text=_attribute_source_badge_text(curve),
        showarrow=False,
        xanchor="right",
        yanchor="top",
        font={"size": 12, "color": "#334155"},
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="rgba(148,163,184,0.75)",
        borderwidth=1,
    )


def _add_vertical_reference_lines(fig, positions, x_value, *, line_width: int, line_dash: str, line_color: str, annotation_text: str | None = None, annotation_font_color: str | None = None, annotation_position: str | None = None) -> None:
    for idx, (row, col) in enumerate(positions):
        kwargs = {
            "x": x_value,
            "line_width": line_width,
            "line_dash": line_dash,
            "line_color": line_color,
            "row": row,
            "col": col,
        }
        if annotation_text and idx == 0:
            kwargs["annotation_text"] = annotation_text
            if annotation_font_color is not None:
                kwargs["annotation_font_color"] = annotation_font_color
            if annotation_position is not None:
                kwargs["annotation_position"] = annotation_position
        fig.add_vline(**kwargs)


def _add_attribute_curves(
    fig,
    *,
    attribute_data: dict,
    row: int,
    col: int,
    placement: str,
    showlegend: bool,
) -> None:
    if not attribute_data or not attribute_data.get("curves"):
        return

    standalone_phase_subplot = str(placement or "below_slt") == "below_slt" and bool(attribute_data.get("has_phase")) and not bool(attribute_data.get("has_non_phase"))
    hide_single_subplot_legend = str(placement or "below_slt") == "below_slt" and len(attribute_data.get("curves") or []) == 1
    metric_colors = {
        "power": "#D94801",
        "log_power": "#F59E0B",
        "amp": "#0077B6",
        "log_amp": "#E11D48",
        "re": "#7C3AED",
        "im": "#0F766E",
        "phase": "#1D9A6C",
    }
    for curve in attribute_data["curves"]:
        axis = curve.get("axis")
        if placement == "signal":
            use_secondary_y = axis == "phase" or not bool(curve.get("normalized"))
        else:
            use_secondary_y = axis == "phase" and not standalone_phase_subplot
        fig.add_trace(
            go.Scatter(
                x=curve["x"],
                y=curve["y"],
                mode="lines",
                line={"width": 2.25, "color": metric_colors.get(curve.get("key"), "#334155")},
                name=curve["name"],
                showlegend=bool(showlegend) and not hide_single_subplot_legend,
                connectgaps=False,
            ),
            row=row,
            col=col,
            secondary_y=use_secondary_y if row is not None else False,
        )


def _render_time_plot(
    *,
    data,
    av_signal,
    peaks,
    wavespeed,
    length_marker,
    reflection,
    generic_marker_ms,
    generic_marker_label,
    show_markers,
    simplify_plot,
    reverse_axis,
    filenames,
    color_map,
    compute_store,
    superlet_plot,
    superlet_coi_mask_on,
    slt_out,
    cmap_name,
    cmin,
    cmax,
    cmap_log,
    cmap_log_floor_exp,
    superlet_attributes_on,
    superlet_attribute_placement,
    superlet_attribute_keys,
    superlet_attr_normalize,
    superlet_attr_zero_baseline,
    superlet_attr_freq_reduce,
    superlet_attr_x_reduce,
    superlet_attr_x_window_ms,
    superlet_attr_freq_min_hz,
    superlet_attr_freq_max_hz,
    superlet_attr_show_band_guides,
    superlet_attr_show_source_badge,
    superlet_attr_phase_freq_hz,
    to_length,
    show_legend,
    horizontal_subplots,
    plot_width_pct,
    plot_height_px,
    lang,
    y_axis_exponent_format="SI",
):
    subplot_height = int(max(120, min(1200, float(plot_height_px or UI_DEFAULTS["main_plot_height_px"]))))
    x_title = translate("Depth, m", lang) if to_length else translate("Time, ms", lang)
    y_axis_exponent_format = _normalize_y_axis_exponent_format(y_axis_exponent_format)
    x_unit = translate("m", lang) if to_length else translate("ms", lang)
    hovertext = "<b>%{text}</b><br>%{x:.2f} " + x_unit + "<extra></extra>"

    compute_store = compute_store or {}
    cache_entry = _slt_cache_get(compute_store.get("cache_key"))
    compute_error = str(compute_store.get("error") or "").strip()
    x_min, x_max = float(data[1]), float(data[2])
    multi = len(data[0]) != 1
    generic_marker_x = None if generic_marker_ms in (None, "") else float(generic_marker_ms)

    attribute_keys = [str(item) for item in (superlet_attribute_keys or []) if item in _attribute_metric_keys()]
    attribute_data = {"curves": [], "messages": [], "has_phase": False, "has_non_phase": False, "non_phase_normalized": False}
    if bool(superlet_attributes_on) and cache_entry is not None and attribute_keys:
        attribute_data = _build_slt_attribute_curves(
            spec=cache_entry["spec"],
            x_values=cache_entry["x"],
            frequencies=cache_entry["frequencies"],
            sample_freq=cache_entry["sample_freq"],
            metric_keys=attribute_keys,
            normalize_on=bool(superlet_attr_normalize),
            zero_baseline_on=bool(superlet_attr_zero_baseline),
            freq_reduce=superlet_attr_freq_reduce,
            x_reduce=superlet_attr_x_reduce,
            x_window_ms=float(superlet_attr_x_window_ms or 0.0),
            band_min_hz=superlet_attr_freq_min_hz,
            band_max_hz=superlet_attr_freq_max_hz,
            phase_freq_hz=superlet_attr_phase_freq_hz,
            coi_mask_on=bool(superlet_coi_mask_on),
            coi_settings=cache_entry.get("coi_settings"),
        )

    effective_attr_placement = _effective_attribute_placement(superlet_attribute_placement, attribute_data)
    has_attr_overlay = bool(superlet_attributes_on and attribute_data.get("curves") and effective_attr_placement == "signal")
    has_attr_row = bool(superlet_attributes_on and attribute_data.get("curves") and effective_attr_placement == "below_slt")
    has_slt_row = bool(superlet_plot)
    panel_order = ["signal"]
    if has_slt_row:
        panel_order.append("slt")
    if has_attr_row:
        panel_order.append("attr")
    horizontal_mode = bool(horizontal_subplots) and len(panel_order) > 1
    signal_secondary_y = bool(has_attr_overlay)
    attr_secondary_y = bool(attribute_data.get("has_phase")) and bool(attribute_data.get("has_non_phase"))

    if horizontal_mode:
        rows = 1
        cols, row_specs, column_widths, panel_positions = _horizontal_time_plot_grid(
            has_slt_row,
            has_attr_row,
            signal_secondary_y=signal_secondary_y,
            attr_secondary_y=attr_secondary_y,
        )
        height = subplot_height
        fig = make_subplots(
            rows=rows,
            cols=cols,
            shared_xaxes=False,
            horizontal_spacing=0.035 if has_slt_row and has_attr_row else 0.09,
            specs=row_specs,
            column_widths=column_widths,
        )
    else:
        row_specs = [[{"secondary_y": True}]]
        if has_slt_row:
            row_specs.append([{"secondary_y": False}])
        if has_attr_row:
            row_specs.append([{"secondary_y": attr_secondary_y}])
        rows = len(row_specs)
        cols = 1
        height = subplot_height * rows
        fig = make_subplots(
            rows=rows,
            cols=cols,
            shared_xaxes=True,
            vertical_spacing=0.05 if rows < 3 else 0.04,
            specs=row_specs,
            row_heights=[1.0] * rows,
        )
        panel_positions = {"signal": (1, 1)}
        next_row = 2
        if has_slt_row:
            panel_positions["slt"] = (next_row, 1)
            next_row += 1
        if has_attr_row:
            panel_positions["attr"] = (next_row, 1)

    signal_row, signal_col = panel_positions["signal"]
    slt_pos = panel_positions.get("slt")
    attr_pos = panel_positions.get("attr")
    external_horizontal_colorbar = bool(horizontal_mode and slt_pos is not None and attr_pos is not None)
    attr_row, attr_col = attr_pos if attr_pos is not None else (None, None)
    visible_positions = [panel_positions[panel] for panel in panel_order]
    non_slt_positions = [panel_positions[panel] for panel in panel_order if panel != "slt"]

    for i, d in enumerate(data[0]):
        df = pd.DataFrame(d)
        t, amp = df["time"], df["amp"]

        if multi:
            col = color_map[filenames[i]]
            trace = go.Scatter(
                x=t,
                y=amp,
                mode="lines",
                line={"color": _rgba_from_hex(col, ALPHA_TRACE), "width": 3.0, "simplify": bool(simplify_plot)},
                hovertemplate=hovertext,
                text=[filenames[i]] * len(t),
                name=filenames[i],
                showlegend=bool(show_legend),
            )
        else:
            trace = go.Scatter(
                x=t,
                y=amp,
                mode="lines",
                line={"color": LINECOLOR_TIMEPLOT, "width": 3.0, "simplify": bool(simplify_plot)},
                hovertemplate=hovertext,
                text=[filenames[i]] * len(t),
                showlegend=False,
            )
            mask = amp >= 0
            amp_pos = np.where(mask, amp, 0)
            fig.add_trace(
                go.Scatter(
                    x=t,
                    y=amp_pos,
                    mode="lines",
                    line={"color": LINECOLOR_TIMEPLOT, "width": 0.0, "simplify": bool(simplify_plot)},
                    fill="tozeroy",
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=signal_row,
                col=signal_col,
            )

        fig.add_trace(trace, row=signal_row, col=signal_col)

    if show_markers:
        fig.add_trace(
            go.Scatter(
                x=peaks[0][0],
                y=peaks[0][1],
                mode="markers",
                hoverinfo="skip",
                opacity=0.75,
                marker=dict(size=10, color="#23C552", line=dict(width=2, color="DarkSlateGrey")),
                showlegend=False,
            ),
            row=signal_row,
            col=signal_col,
        )
        fig.add_trace(
            go.Scatter(
                x=peaks[1][0],
                y=peaks[1][1],
                mode="markers",
                hoverinfo="skip",
                opacity=0.75,
                marker=dict(size=10, color="#F84F31", line=dict(width=2, color="DarkSlateGrey")),
                showlegend=False,
            ),
            row=signal_row,
            col=signal_col,
        )

    if multi and av_signal and av_signal != [[], []]:
        fig.add_trace(
            go.Scatter(
                x=av_signal[0],
                y=av_signal[1],
                mode="lines",
                line={"color": "#000000", "width": 3.0, "simplify": bool(simplify_plot)},
                hovertemplate=hovertext,
                text=[translate("AV", lang)] * len(av_signal[0]),
                name=translate("AV", lang),
                showlegend=bool(show_legend),
            ),
            row=signal_row,
            col=signal_col,
        )

    if has_attr_overlay:
        _add_attribute_curves(
            fig,
            attribute_data=attribute_data,
            row=signal_row,
            col=signal_col,
            placement="signal",
            showlegend=bool(show_legend),
        )

    if length_marker:
        _add_vertical_reference_lines(
            fig,
            non_slt_positions,
            length_marker,
            line_width=3,
            line_dash="dash",
            line_color="green",
            annotation_text=f"{round(length_marker, 2)} {x_unit}",
        )
    if reflection:
        nref = min(int(x_max // reflection), 10)
        for k in range(nref):
            _add_vertical_reference_lines(
                fig,
                non_slt_positions,
                (k + 1) * reflection,
                line_width=2,
                line_dash="dot",
                line_color="grey",
                annotation_text=f"{round((k + 1) * reflection, 2)} {x_unit}",
                annotation_position="bottom right",
            )

    if not reverse_axis:
        fig.update_yaxes(autorange="reversed", row=signal_row, col=signal_col, secondary_y=False)
    fig.update_yaxes(title=translate("Amplitude", lang), row=signal_row, col=signal_col, secondary_y=False)
    fig.update_yaxes(exponentformat=y_axis_exponent_format, row=signal_row, col=signal_col, secondary_y=False)

    overlay_secondary_curves = []
    if has_attr_overlay:
        overlay_secondary_curves = [
            curve for curve in attribute_data.get("curves", [])
            if curve.get("axis") == "phase" or not bool(curve.get("normalized"))
        ]
        if overlay_secondary_curves:
            if all(curve.get("axis") == "phase" for curve in overlay_secondary_curves):
                secondary_title = translate("Phase", lang) + ", deg"
            elif any(curve.get("axis") == "phase" for curve in overlay_secondary_curves):
                secondary_title = translate("Phase", lang) + " / 1D metrics"
            else:
                secondary_title = "1D metrics"
            fig.update_yaxes(title=secondary_title, row=signal_row, col=signal_col, secondary_y=True)
            if any(curve.get("axis") == "phase" for curve in overlay_secondary_curves):
                fig.update_yaxes(
                    autorange=False,
                    range=[-180.0, 180.0],
                    tickmode="array",
                    tickvals=_PHASE_AXIS_TICKS,
                    row=signal_row,
                    col=signal_col,
                    secondary_y=True,
                )
            else:
                fig.update_yaxes(exponentformat=y_axis_exponent_format, row=signal_row, col=signal_col, secondary_y=True)

    if slt_pos is not None:
        slt_row, slt_col = slt_pos
        if cache_entry is not None:
            cmap = _resolve_slt_colorscale(cmap_name)
            slt_plot_data = _prepare_slt_heatmap_data(
                spec=cache_entry["spec"],
                slt_out=slt_out,
                log_colorscale=bool(cmap_log),
                log_floor_exp=cmap_log_floor_exp,
                coi_mask_on=bool(superlet_coi_mask_on),
                cmin=cmin,
                cmax=cmax,
                lang=lang,
                to_length=to_length,
                x_unit=x_unit,
                t=cache_entry["x"],
                foi=cache_entry["frequencies"],
                sample_freq=cache_entry["sample_freq"],
                coi_settings=cache_entry.get("coi_settings"),
                source_name=cache_entry.get("source_name", filenames[0]),
            )
            _add_slt_heatmap_trace(
                fig,
                slt_plot_data,
                cmap,
                row=slt_row,
                col=slt_col,
                figure_height_px=height,
                colorbar_offset=0.01 if horizontal_mode else 0.022,
                colorbar_len_factor=0.88 if horizontal_mode else 0.95,
                colorbar_thickness=9 if horizontal_mode else 15,
                colorbar_title_font_size=13 if horizontal_mode else 15,
                colorbar_x_override=(
                    float(fig.get_subplot(attr_row, attr_col).xaxis.domain[1]) + 0.02
                    if external_horizontal_colorbar
                    else None
                ),
            )

            if length_marker:
                _add_vertical_reference_lines(
                    fig,
                    [slt_pos],
                    length_marker,
                    line_width=3,
                    line_dash="dash",
                    line_color="white",
                    annotation_text=f"{round(length_marker, 2)} {x_unit}",
                    annotation_font_color="white",
                )
            if reflection:
                nref = min(int(x_max // reflection), 10)
                for k in range(nref):
                    _add_vertical_reference_lines(
                        fig,
                        [slt_pos],
                        (k + 1) * reflection,
                        line_width=2,
                        line_dash="dot",
                        line_color="grey",
                        annotation_text=f"{round((k + 1) * reflection, 2)} {x_unit}",
                        annotation_font_color="white",
                        annotation_position="bottom right",
                    )
            if bool(superlet_attr_show_band_guides) and (bool(attribute_data.get("has_non_phase")) or bool(attribute_data.get("has_phase"))):
                band_min = None if superlet_attr_freq_min_hz in (None, "") else float(superlet_attr_freq_min_hz)
                band_max = None if superlet_attr_freq_max_hz in (None, "") else float(superlet_attr_freq_max_hz)
                if band_min is not None and band_max is not None and band_max < band_min:
                    band_min, band_max = band_max, band_min
                phase_freq = None if superlet_attr_phase_freq_hz in (None, "") else float(superlet_attr_phase_freq_hz)
                guide_values = []
                if bool(attribute_data.get("has_non_phase")):
                    guide_values.extend([band_min, band_max])
                if bool(attribute_data.get("has_phase")):
                    guide_values.append(phase_freq)
                for band_value in guide_values:
                    if band_value is None:
                        continue
                    fig.add_hline(
                        y=band_value,
                        line_width=2,
                        line_dash="dash",
                        line_color="white",
                        row=slt_row,
                        col=slt_col,
                    )

            fig.update_yaxes(title=translate("Frequency, Hz", lang), type="log", autorange=True, exponentformat=y_axis_exponent_format, row=slt_row, col=slt_col)
        else:
            fig.add_annotation(
                x=0.5,
                y=0.5,
                xref="x domain",
                yref="y domain",
                text=compute_error or "SLT is unavailable.",
                showarrow=False,
                font={"color": "#FF4949"},
                row=slt_row,
                col=slt_col,
            )

    if attr_pos is not None:
        attr_row, attr_col = attr_pos
        _add_attribute_curves(
            fig,
            attribute_data=attribute_data,
            row=attr_row,
            col=attr_col,
            placement="below_slt",
            showlegend=bool(show_legend),
        )
        if not reverse_axis:
            if not (bool(attribute_data.get("has_phase")) and not bool(attribute_data.get("has_non_phase"))):
                fig.update_yaxes(autorange="reversed", row=attr_row, col=attr_col, secondary_y=False)
            if bool(attribute_data.get("has_non_phase")):
                fig.update_yaxes(autorange="reversed", row=attr_row, col=attr_col, secondary_y=True)
        if bool(attribute_data.get("has_phase")) and not bool(attribute_data.get("has_non_phase")):
            fig.update_yaxes(
                title="Phase, °",
                autorange=False,
                range=[-180.0, 180.0],
                tickmode="array",
                tickvals=_PHASE_AXIS_TICKS,
                row=attr_row,
                col=attr_col,
                secondary_y=False,
            )
        elif len(attribute_data.get("curves") or []) == 1:
            fig.update_yaxes(title=_metric_axis_title(attribute_data["curves"][0]), row=attr_row, col=attr_col, secondary_y=False)
        elif bool(attribute_data.get("has_non_phase")):
            fig.update_yaxes(title="1D metrics", row=attr_row, col=attr_col, secondary_y=False)
        if not (bool(attribute_data.get("has_phase")) and not bool(attribute_data.get("has_non_phase"))):
            fig.update_yaxes(exponentformat=y_axis_exponent_format, row=attr_row, col=attr_col, secondary_y=False)
        if any(curve.get("axis") == "phase" for curve in attribute_data.get("curves", [])):
            if bool(attribute_data.get("has_non_phase")):
                fig.update_yaxes(
                    title=translate("Phase", lang) + ", deg",
                    autorange=False,
                    range=[-180.0, 180.0],
                    tickmode="array",
                    tickvals=_PHASE_AXIS_TICKS,
                    row=attr_row,
                    col=attr_col,
                    secondary_y=True,
                )
        if len(attribute_data.get("curves") or []) == 1 and bool(superlet_attr_show_source_badge):
            _add_single_attribute_badge(fig, attribute_data["curves"][0], row=attr_row, col=attr_col)

    fig.update_xaxes(
        zeroline=False,
        showline=True,
        linewidth=1,
        linecolor="grey",
        mirror=True,
        range=[x_min, x_max],
        ticks="outside",
        automargin=True,
    )
    if horizontal_mode:
        for idx, panel in enumerate(panel_order):
            row, col = panel_positions[panel]
            xaxis_kwargs = {
                "title": x_title,
                "title_standoff": 5,
                "showticklabels": True,
                "tickfont": {"size": 12},
                "title_font": {"size": 13},
                "automargin": True,
            }
            if idx > 0:
                xaxis_kwargs["matches"] = "x"
            fig.update_xaxes(row=row, col=col, **xaxis_kwargs)
    else:
        fig.update_xaxes(title=x_title, title_standoff=5, row=rows, col=1)
    fig.update_yaxes(
        zeroline=True,
        showline=True,
        linewidth=1,
        linecolor="grey",
        mirror=True,
        ticks="outside",
        title_standoff=0,
        automargin=True,
    )
    if horizontal_mode:
        fig.update_yaxes(tickfont={"size": 12}, title_font={"size": 13})

    _add_global_marker(fig, generic_marker_x, generic_marker_label, visible_positions)

    for message in attribute_data.get("messages") or []:
        warnings.warn(f"1D SLT metrics: {message}", RuntimeWarning, stacklevel=2)

    margin = dict(b=60, t=10)
    if horizontal_mode:
        margin["l"] = 36
        margin["r"] = 70 if external_horizontal_colorbar else (14 if has_slt_row and not has_attr_row else 4)
    else:
        margin["l"] = 70
        margin["r"] = 70

    fig.update_layout(
        height=height,
        font=dict(size=13 if horizontal_mode else 15),
        margin=margin,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        showlegend=show_legend,
    )

    filename = filenames[0].split(".")[0]
    config = _time_plot_graph_config(filename)
    plot_width = max(50.0, min(100.0, float(plot_width_pct or 100.0)))
    return [dcc.Graph(id="graph_time", config=config, figure=fig, style={"width": f"{plot_width}%", "margin": "0 auto"})]


@callback(
    Output("btn-upload", "children"),
    Output("btn-download", "children"),
    Output("btn-reset-defaults", "children"),
    Output("btn-save-time-plot", "children"),
    Output("btn-save-spectrum-plot", "children"),
    Output("main-plot-width-label", "children"),
    Output("main-plot-height-label", "children"),
    Output("filenames-label", "children"),
    Output("amplification-label", "children"),
    Output("smoothing-label", "children"),
    Output("wavespeed-label", "children"),
    Output("show-legend-label", "children"),
    Output("superlet-label", "children"),
    Output("slt-mode-label", "children"),
    Output("cycle-scaling-label", "children"),
    Output("freq-slt-min-label", "children"),
    Output("freq-slt-max-label", "children"),
    Output("freq-slt-no-label", "children"),
    Output("cycles-label", "children"),
    Output("order-slt-label", "children"),
    Output("order-min-label", "children"),
    Output("order-max-label", "children"),
    Output("ksd-label", "children"),
    Output("support-sd-label", "children"),
    Output("slt-output-label", "children"),
    Output("superlet-set-mode", "data"),
    Output("SLT_output", "data"),
    Output("colorscale-label", "children"),
    Output("log-colorscale-label", "children"),
    Output("cmap-min-label", "children"),
    Output("cmap-max-label", "children"),
    Output("advanced-settings-label", "children"),
    Output("downsample-label", "children"),
    Output("downsample-aa", "label"),
    Output("sampling-in-out-label", "children"),
    Output("factors-label", "children"),
    Output("signal-settings-label", "children"),
    Output("visualization-settings-label", "children"),
    Output("signal-window-switch-label", "children"),
    Output("convert-time-label", "children"),
    Output("show-markers-label", "children"),
    Output("simplify-plot-label", "children"),
    Output("detrend-label", "children"),
    Output("detrend-tick", "label"),
    Output("shift-label", "children"),
    Output("reverse-axis-label", "children"),
    Output("filter-settings-label", "children"),
    Output("advanced-filter-settings-label", "children"),
    Output("forward-backward-filter-switch-label", "children"),
    Output("filter-draw-switch-label", "children"),
    Output("slt-settings-label", "children"),
    Output("slt-phase-handling-label", "children"),
    Output("superlet-coi-mask-label", "children"),
    Output("local-extrema-label", "children"),
    Output("peak-distance-label", "children"),
    Output("peak-width-min-label", "children"),
    Output("peak-width-max-label", "children"),
    Output("peak-prominence-label", "children"),
    Output("enable-filter-label", "children"),
    Output("filter-tick", "label"),
    Output("autozoom-frequency-axis-label", "children"),
    Output("low-pass-label", "children"),
    Output("high-pass-label", "children"),
    Output("filter-order-label", "children"),
    Output("amplitude-spectrum-label", "children"),
    Output("generic-marker-text-label", "children"),
    Output("slt-log-floor-exp-label", "children"),
    Output("superlet-attributes-label", "children"),
    Output("superlet-attr-placement-label", "children"),
    Output("superlet-attr-keys-label", "children"),
    Output("superlet-attr-normalize-label", "children"),
    Output("superlet-attr-freq-reduce-label", "children"),
    Output("superlet-attr-x-reduce-label", "children"),
    Output("superlet-attr-band-guides-label", "children"),
    Output("superlet-attr-source-badge-label", "children"),
    Output("horizontal-subplots-label", "children"),
    Output("y-axis-exponent-format-label", "children"),
    Output("time-unit-override-label", "children"),
    Output("assumed-signal-type-label", "children"),
    Output("integration-label", "children"),
    Input("lang-segment", "value"),
    Input("length-switch", "value"),
)
def update_layout_language(lang, to_length):
    lang = lang or "EN"
    extra_labels = {
        "EN": [
            "Generic marker label",
            "Log floor exponent",
            "1D SLT metrics",
            "Plot location",
            "Metrics",
            "Normalize to max",
            "Band reducer",
            "Curve reducer",
            "Show band on SLT",
            "Show source badge",
            "Display subplots horizontally",
            "Y-axis exponent format",
            "Text file time unit",
            "Assumed signal type",
            "Integration",
        ],
        "RU": [
            "Подпись общего маркера",
            "Показатель log-floor",
            "1D метрики SLT",
            "Место графика",
            "Метрики",
            "Нормировать до максимума",
            "Редьюсер по полосе",
            "Редьюсер кривой",
            "Показывать полосу на SLT",
            "Показывать подпись источника",
            "Горизонтальные подграфики",
            "Формат показателей оси Y",
            "Единица времени в текстовом файле",
            "Предполагаемый тип сигнала",
            "Интегрирование",
        ],
    }
    return [
        translate("Load", lang),
        translate("Save", lang),
        translate("Reset settings to defaults", lang),
        translate("Save plot as image", lang),
        translate("Save spectrum plot as image", lang),
        translate("Main plot width, %", lang),
        "Subplot height, px",
        translate("Filenames", lang),
        translate("Amplification", lang),
        translate("Smoothing", lang),
        translate("Wave speed, m/s", lang),
        translate("Show legend", lang),
        translate("Superlet", lang),
        translate("SLT mode", lang),
        translate("Cycle scaling", lang),
        translate("Minimal freq", lang),
        translate("Maximal freq", lang),
        translate("Number of freqs", lang),
        translate("Base cycles", lang),
        translate("Order", lang),
        translate("Min order", lang),
        translate("Max order", lang),
        ["k", html.Sub("sd"), " (Gaussian width)"],
        translate("support_sd", lang),
        translate("Display", lang),
        _translated_cycle_scaling_data(lang),
        _translated_slt_output_data(lang),
        translate("Colorscale", lang),
        translate("Log colorscale", lang),
        translate("Low limit", lang),
        translate("High limit", lang),
        translate("Advanced settings", lang),
        translate("Downsampling (factor)", lang),
        translate("Anti-alias filter", lang),
        translate("Sampling (in/out)", lang),
        translate("Factors", lang),
        translate("Signal settings", lang),
        "Visualization" if lang == "EN" else "Визуализация",
        translate("Window signal for processing", lang),
        translate("Convert time to length", lang),
        translate("Show markers", lang),
        translate("Simplify signal plot", lang),
        translate("Detrend signal", lang),
        translate("After amplification", lang),
        translate("Shift signal along time-axis", lang),
        translate("Reverse y-axis", lang),
        translate("Filter settings", lang),
        translate("Advanced filter settings", lang),
        translate("Forward-backward filtering", lang),
        translate("Show filter frequency response", lang),
        translate("SLT settings", lang),
        translate("Phase mode", lang),
        translate("Edge mask (COI)", lang),
        translate("Local extrema settings", lang),
        translate("Min. distance between peaks, in samples", lang),
        translate("Min. width of peaks, in samples", lang),
        translate("Max. width of peaks, in samples", lang),
        translate("Min. prominence of peaks", lang),
        translate("Enable filter", lang),
        translate("Apply before amplification", lang),
        translate("Autozoom frequency axis", lang),
        translate("Low-pass filter cutoff frequency, Hz", lang),
        translate("High-pass filter cutoff frequency, Hz", lang),
        translate("Filter order", lang),
        translate("Amplitude spectrum", lang),
        *extra_labels.get(lang, extra_labels["EN"]),
    ]


@callback(
    Output("signal-length-label", "children"),
    Output("averaging-window-label", "children"),
    Output("length-marker-label", "children"),
    Output("multiple-reflections-label", "children"),
    Output("generic-marker-label", "children"),
    Output("signal-window-taper-label", "children"),
    Output("signal-window-padding-label", "children"),
    Output("superlet-attr-window-label", "children"),
    Input("lang-segment", "value"),
    Input("length-switch", "value"),
)
def update_length_unit_labels(lang, to_length):
    lang = lang or "EN"
    if to_length:
        return [
            translate("Signal end, m", lang),
            translate("Averaging window size, m", lang),
            translate("Pile length marker, m", lang),
            translate("Multiple reflections, m", lang),
            translate("Generic marker, m", lang),
            translate("Right-edge taper, m", lang),
            translate("Symmetric padding, m", lang),
            translate("Curve averaging, m", lang),
        ]
    return [
        translate("Signal end, ms", lang),
        translate("Averaging window size, ms", lang),
        translate("Pile length marker, ms", lang),
        translate("Multiple reflections, ms", lang),
        translate("Generic marker, ms", lang),
        translate("Right-edge taper, ms", lang),
        translate("Symmetric padding, ms", lang),
        translate("Curve averaging, ms", lang),
    ]


@callback(
    Output("slt-log-colorscale-row", "style"),
    Input("SLT_output", "value"),
)
def toggle_slt_log_colorscale_control(slt_out):
    if _supports_slt_log_colorscale(slt_out):
        return dict(SETTINGS_ROW_STYLE)
    return {**SETTINGS_ROW_STYLE, "display": "none"}


@callback(
    Output("slt-log-floor-row", "style"),
    Input("cmap_SLT_log", "value"),
    Input("SLT_output", "value"),
)
def toggle_slt_log_floor_row(cmap_log, slt_out):
    if bool(cmap_log) and _supports_slt_log_colorscale(slt_out):
        return dict(SETTINGS_ROW_STYLE)
    return {**SETTINGS_ROW_STYLE, "display": "none"}


@callback(
    Output("signal-window-taper-row", "style"),
    Output("signal-window-padding-row", "style"),
    Input("signal-window-switch", "value"),
)
def toggle_signal_window_controls(signal_window_on):
    if signal_window_on:
        return dict(SETTINGS_ROW_STYLE), dict(SETTINGS_ROW_STYLE)
    hidden = {**SETTINGS_ROW_STYLE, "display": "none"}
    return hidden, hidden


@callback(
    Output("averaging-window-row", "style"),
    Output("smoothing-row", "style"),
    Input("selected-filenames-store", "data"),
)
def toggle_average_only_controls(selected_filenames):
    if selected_filenames and len(selected_filenames) > 1:
        return dict(SLIDER_SETTINGS_ROW_STYLE), dict(SETTINGS_ROW_STYLE)
    return (
        {**SLIDER_SETTINGS_ROW_STYLE, "display": "none"},
        {**SETTINGS_ROW_STYLE, "display": "none"},
    )


@callback(
    Output("signal-window-taper-container", "children"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("signal-window-taper-ms-store", "data"),
)
def render_signal_window_taper_input(to_length, wavespeed, taper_ms):
    if wavespeed is None:
        raise PreventUpdate
    return _render_window_length_input(
        taper_ms,
        to_length,
        wavespeed,
        input_id="signal-window-taper-input",
    )


@callback(
    Output("signal-window-padding-container", "children"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("signal-window-padding-ms-store", "data"),
)
def render_signal_window_padding_input(to_length, wavespeed, padding_ms):
    if wavespeed is None:
        raise PreventUpdate
    return _render_window_length_input(
        padding_ms,
        to_length,
        wavespeed,
        input_id="signal-window-padding-input",
    )


@callback(
    Output("signal-window-taper-ms-store", "data", allow_duplicate=True),
    Input("signal-window-taper-input", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def store_signal_window_taper_ms(input_value, to_length, wavespeed):
    if input_value is None:
        raise PreventUpdate

    value = max(0.0, float(input_value))
    if to_length:
        if not wavespeed:
            raise PreventUpdate
        return value * 2000.0 / float(wavespeed)
    return value


@callback(
    Output("superlet-attr-window-container", "children"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("superlet-attr-x-window-ms-store", "data"),
)
def render_superlet_attr_window_input(to_length, wavespeed, window_ms):
    if wavespeed is None:
        raise PreventUpdate
    return _render_window_length_input(
        window_ms,
        to_length,
        wavespeed,
        input_id="superlet-attr-window-input",
    )


@callback(
    Output("superlet-attr-x-window-ms-store", "data", allow_duplicate=True),
    Input("superlet-attr-window-input", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def store_superlet_attr_window_ms(input_value, to_length, wavespeed):
    if input_value in (None, ""):
        return 0.0

    value = max(0.0, float(input_value))
    if to_length:
        if not wavespeed:
            raise PreventUpdate
        return value * 2000.0 / float(wavespeed)
    return value


@callback(
    Output("superlet-attr-placement-row", "style"),
    Output("superlet-attr-keys-row", "style"),
    Output("superlet-attr-normalize-row", "style"),
    Output("superlet-attr-zero-baseline-row", "style"),
    Output("superlet-attr-freq-reduce-row", "style"),
    Output("superlet-attr-window-row", "style"),
    Output("superlet-attr-x-reduce-row", "style"),
    Output("superlet-attr-band-row", "style"),
    Output("superlet-attr-band-guides-row", "style"),
    Output("superlet-attr-source-badge-row", "style"),
    Output("superlet-attr-phase-row", "style"),
    Input("superlet-attributes-switch", "value"),
    Input("superlet-attribute-keys", "value"),
    Input("superlet-attr-x-window-ms-store", "data"),
    Input("superlet-attribute-placement", "value"),
    Input("superlet-switch", "value"),
)
def toggle_superlet_attribute_controls(attributes_on, metric_keys, x_window_ms, attribute_placement, superlet_plot):
    hidden = {**SETTINGS_ROW_STYLE, "display": "none"}
    if not attributes_on:
        return (hidden, hidden, hidden, hidden, hidden, hidden, hidden, hidden, hidden, hidden, hidden)

    selected = [str(item) for item in (metric_keys or [])]
    has_phase = "phase" in selected
    has_non_phase = any(item in _attribute_metric_keys() and item != "phase" for item in selected)
    has_x_window = float(x_window_ms or 0.0) > 0.0
    show_source_badge_toggle = len(selected) == 1 and str(attribute_placement or "below_slt") == "below_slt"
    row = dict(SETTINGS_ROW_STYLE)
    return (
        row,
        row,
        row if has_non_phase else hidden,
        row if has_non_phase else hidden,
        row if has_non_phase else hidden,
        row,
        row if has_x_window else hidden,
        row if has_non_phase else hidden,
        row if (has_non_phase or has_phase) and bool(superlet_plot) else hidden,
        row if show_source_badge_toggle else hidden,
        row if has_phase else hidden,
    )


@callback(
    Output("signal-window-padding-ms-store", "data", allow_duplicate=True),
    Input("signal-window-padding-input", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def store_signal_window_padding_ms(input_value, to_length, wavespeed):
    if input_value is None:
        raise PreventUpdate

    value = max(0.0, float(input_value))
    if to_length:
        if not wavespeed:
            raise PreventUpdate
        return value * 2000.0 / float(wavespeed)
    return value


@callback(
    Output("cycles-col", "style"),
    Output("order-slt-col", "style"),
    Output("order-min-col", "style"),
    Output("order-max-col", "style"),
    Input("slt-mode", "value"),
)
def update_superlet_mode_controls(slt_mode):
    if slt_mode == "fixed":
        return (
            {"width": "50%", "display": "inline-block"},
            {"width": "50%", "display": "inline-block"},
            {"display": "none"},
            {"display": "none"},
        )
    return (
        {"width": "33%", "display": "inline-block"},
        {"display": "none"},
        {"width": "33%", "display": "inline-block"},
        {"width": "33%", "display": "inline-block"},
    )


# ---------- download settings + raw ----------
@callback(
    Output("download", "data"),
    Input("btn-download", "n_clicks"),
    State("signal_raw", "data"),
    State("selected-filenames-store", "data"),
    State("amp-slider", "value"),
    State("signal-end-ms-store", "data"),
    State("detrend-switch", "value"),
    State("detrend-tick", "value"),
    State("shift-switch", "value"),
    State("flip-polarity-switch", "value"),
    State("peak-distance", "value"),
    State("peak-width-min", "value"),
    State("peak-width-max", "value"),
    State("peak-prominence-min", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    State("main-plot-width", "value"),
    State("main-plot-height", "value"),
    State("downsample-factor", "value"),
    State("downsample-aa", "value"),
    State("filter-switch", "value"),
    State("forward-backward-filter-switch", "value"),
    State("filter-cutoff_lp", "value"),
    State("filter-cutoff_hp", "value"),
    State("filter-order", "value"),
    State("spectrum-autozoom-x", "value"),
    State("av-win-ms-store", "data"),
    State("smoothing-slider", "value"),
    State("length-marker", "value"),
    State("multiple-reflections", "value"),
    State("generic-marker-input", "value"),
    State("generic-marker-text", "value"),
    State("show-markers-switch", "value"),
    State("simplify-plot-switch", "value"),
    State("reverse-axis-switch", "value"),
    State("signal-window-switch", "value"),
    State("signal-window-taper-ms-store", "data"),
    State("signal-window-padding-ms-store", "data"),
    State("time-unit-override", "value"),
    State("integration-mode", "value"),
    State("integration-method", "value"),
    State("integration-lowfreq-hz", "value"),
    State("integration-zero-baseline-switch", "value"),
    State("signal-assumptions-store", "data"),
    State("superlet-switch", "value"),
    State("slt-mode", "value"),
    State("superlet-set-mode", "value"),
    State("superlet-phase-combination", "value"),
    State("superlet-coi-mask-switch", "value"),
    State("freq_SLT_min", "value"),
    State("freq_SLT_max", "value"),
    State("freq_SLT_no", "value"),
    State("c_1", "value"),
    State("k_sd", "value"),
    State("support_sd", "value"),
    State("order_slt", "value"),
    State("order_min", "value"),
    State("order_max", "value"),
    State("SLT_output", "value"),
    State("cmap_SLT", "value"),
    State("cmap_SLT_min", "value"),
    State("cmap_SLT_max", "value"),
    State("cmap_SLT_log", "value"),
    State("cmap_SLT_log_floor_exp", "value"),
    State("superlet-attributes-switch", "value"),
    State("superlet-attribute-placement", "value"),
    State("superlet-attribute-keys", "value"),
    State("superlet-attr-normalize-switch", "value"),
    State("superlet-attr-zero-baseline-switch", "value"),
    State("superlet-attr-freq-reduce", "value"),
    State("superlet-attr-x-reduce", "value"),
    State("superlet-attr-x-window-ms-store", "data"),
    State("superlet-attr-band-min-hz", "value"),
    State("superlet-attr-band-max-hz", "value"),
    State("superlet-attr-show-band-guides-switch", "value"),
    State("superlet-attr-show-source-badge-switch", "value"),
    State("superlet-attr-phase-freq-hz", "value"),
    State("filter-draw-switch", "value"),
    State("show-legend-switch", "value"),
    State("filter-tick", "value"),
    State("horizontal-subplots-switch", "value"),
    State("y-axis-exponent-format", "value"),
    prevent_initial_call=True,
)
def download_file(
    _,
    raw_signals, selected_filenames,
    a0, lim_time_max, detrend_on, detrend_tick,
    shift_on, flip_polarity, peak_distance, peak_width_min, peak_width_max, peak_prominence_min,
    length_on, wavespeed, main_plot_width_pct, main_plot_height_px, downsample_factor, downsample_aa,
    filter_switch, forward_backward_filter,
    filter_cutoff_lp, filter_cutoff_hp, filter_order, spectrum_autozoom_x,
    moving_window_size, spline_smoothing,
    length_marker, reflection, generic_marker_ms, generic_marker_label, show_markers, simplify_plot, reverse_axis, signal_window_on, signal_window_taper_ms, signal_window_padding_ms, time_unit_override, integration_mode, integration_method, integration_low_frequency_hz, integration_zero_baseline, signal_assumptions,
    superlet_plot, slt_mode, superlet_set_mode, superlet_phase_combination, superlet_coi_mask_on, freq_SLT_min, freq_SLT_max, freq_SLT_no,
    c_1, k_sd, support_sd, order_slt=None, order_min=None, order_max=None, SLT_output=None,
    cmap_SLT=None, cmap_SLT_min=None, cmap_SLT_max=None, cmap_SLT_log=None, cmap_SLT_log_floor_exp=None,
    superlet_attributes_on=None, superlet_attribute_placement=None, superlet_attribute_keys=None,
    superlet_attr_normalize=None, superlet_attr_zero_baseline=None, superlet_attr_freq_reduce=None, superlet_attr_x_reduce=None,
    superlet_attr_x_window_ms=None, superlet_attr_freq_min_hz=None, superlet_attr_freq_max_hz=None, superlet_attr_show_band_guides=None, superlet_attr_show_source_badge=None, superlet_attr_phase_freq_hz=None, filter_draw=None,
    show_legend=None, filter_tick=None, display_subplots_horizontally=None, y_axis_exponent_format=None,
):
    if None in (raw_signals, selected_filenames) or not selected_filenames:
        raise PreventUpdate

    settings_map = {
        "a0": a0,
        "lim_time_max": lim_time_max,
        "detrend_on": detrend_on,
        "detrend_tick": detrend_tick,
        "shift_on": shift_on,
        "flip_polarity": flip_polarity,
        "peak_distance": peak_distance,
        "peak_width_min": peak_width_min,
        "peak_width_max": peak_width_max,
        "peak_prominence_min": peak_prominence_min,
        "length_on": length_on,
        "wavespeed": wavespeed,
        "main_plot_width_pct": main_plot_width_pct,
        "main_plot_height_px": main_plot_height_px,
        "downsample_factor": downsample_factor,
        "downsample_aa": downsample_aa,
        "filter_switch": filter_switch,
        "forward_backward_filter": forward_backward_filter,
        "filter_cutoff_lp": filter_cutoff_lp,
        "filter_cutoff_hp": filter_cutoff_hp,
        "filter_order": filter_order,
        "spectrum_autozoom_x": spectrum_autozoom_x,
        "moving_window_size": moving_window_size,
        "spline_smoothing": spline_smoothing,
        "length_marker": length_marker,
        "reflection": reflection,
        "generic_marker_ms": generic_marker_ms,
        "generic_marker_label": generic_marker_label,
        "show_markers": show_markers,
        "simplify_plot": simplify_plot,
        "reverse_axis": reverse_axis,
        "signal_window_on": signal_window_on,
        "signal_window_taper_ms": signal_window_taper_ms,
        "signal_window_padding_ms": signal_window_padding_ms,
        "superlet_plot": superlet_plot,
        "superlet_set_mode": superlet_set_mode,
        "superlet_phase_combination": superlet_phase_combination,
        "superlet_coi_mask_on": superlet_coi_mask_on,
        "freq_SLT_min": freq_SLT_min,
        "freq_SLT_max": freq_SLT_max,
        "freq_SLT_no": freq_SLT_no,
        "c_1": c_1,
        "k_sd": k_sd,
        "support_sd": support_sd,
        "order_slt": order_slt,
        "order_min": order_min,
        "order_max": order_max,
        "slt_mode": slt_mode,
        "SLT_output": SLT_output,
        "cmap_SLT": cmap_SLT,
        "cmap_SLT_min": cmap_SLT_min,
        "cmap_SLT_max": cmap_SLT_max,
        "cmap_SLT_log": cmap_SLT_log,
        "cmap_SLT_log_floor_exp": cmap_SLT_log_floor_exp,
        "superlet_attributes_on": superlet_attributes_on,
        "superlet_attribute_placement": superlet_attribute_placement,
        "superlet_attribute_keys": superlet_attribute_keys,
        "superlet_attr_normalize": superlet_attr_normalize,
        "superlet_attr_zero_baseline": superlet_attr_zero_baseline,
        "superlet_attr_freq_reduce": superlet_attr_freq_reduce,
        "superlet_attr_x_reduce": superlet_attr_x_reduce,
        "superlet_attr_x_window_ms": superlet_attr_x_window_ms,
        "superlet_attr_freq_min_hz": superlet_attr_freq_min_hz,
        "superlet_attr_freq_max_hz": superlet_attr_freq_max_hz,
        "superlet_attr_show_band_guides": superlet_attr_show_band_guides,
        "superlet_attr_show_source_badge": superlet_attr_show_source_badge,
        "superlet_attr_phase_freq_hz": superlet_attr_phase_freq_hz,
        "filter_draw": filter_draw,
        "show_legend": show_legend,
        "filter_tick": filter_tick,
        "display_subplots_horizontally": display_subplots_horizontally,
        "y_axis_exponent_format": y_axis_exponent_format,
        "time_unit_override": time_unit_override,
        "integration_mode": integration_mode,
        "integration_method": integration_method,
        "integration_low_frequency_hz": integration_low_frequency_hz,
        "integration_zero_baseline": integration_zero_baseline,
    }
    text = serialize_snc_text(raw_signals, selected_filenames, settings_map, signal_assumptions)
    return {"content": text, "filename": f"{selected_filenames[0]}.snc"}


# ---------- filename в†’ checkbox list ----------
@callback(
    Output("filename-store", "data"),
    Output("files-select-div", "style"),
    Output("checkbox-group", "children"),
    Output("checkbox-group", "value"),
    Output("notify", "sendNotifications", allow_duplicate=True),
    Input("upload-data", "filename"),
    Input("upload-data", "contents"),
    prevent_initial_call=True,
)
def store_filenames(filenames, list_of_contents):
    if not filenames:
        raise PreventUpdate

    limit_notification = _validate_upload_size_limits(filenames, list_of_contents)
    if limit_notification is not None:
        return no_update, {"display": "none"}, no_update, no_update, [limit_notification]

    div_style = {"display": "block", "padding": "10px 0 12px 10px"}
    checks, values, notifications = [], [], []

    for i, fname in enumerate(filenames):
        ext = Path(fname).suffix.lower()
        lower_name = fname.lower()

        try:
            if lower_name.endswith(".pp.csv"):
                _, channel_list, _, _, _ = parse_contents(list_of_contents[i], fname, 1)
                for channel in channel_list:
                    display_label = str(channel["label"])
                    value = _parsed_signal_name(fname, display_label)
                    checks.append(dmc.Checkbox(label=value, value=value))
                    values.append(value)

            elif ext == ".sgy":
                _, channel_list, _, _, _ = parse_contents(list_of_contents[i], fname, 1)
                if not channel_list:
                    notifications.append(_toast("Upload error", f"{fname}: SEG-Y file could not be parsed."))
                    continue
                for channel in channel_list:
                    value = _parsed_signal_name(fname, str(channel["value"]))
                    checks.append(dmc.Checkbox(label=value, value=value))
                    values.append(value)

            elif ext == ".txt":
                _, content_string = list_of_contents[i].split(",", 1)
                decoded = base64.b64decode(content_string)
                file_data = decode_txt_upload(decoded)

                if file_data is None:
                    notifications.append(_toast("Upload error", f"{fname}: text file could not be decoded."))
                    continue

                if is_zbl_txt(file_data):
                    sections, _, section_keys, blow_times = parse_zbl_sections(file_data.splitlines())
                    if not sections:
                        notifications.append(_toast("Upload error", f"{fname}: ZBL waveform blocks could not be parsed."))
                        continue
                    if len(sections) > 1 and all(key is None for key in section_keys):
                        notifications.append(_toast("Upload warning", f"{Path(fname).stem}: ZBL labels were inferred from section order.", color="yellow"))
                    labels = build_zbl_labels(section_keys, blow_times)
                    for display_label in labels:
                        value = _parsed_signal_name(fname, str(display_label))
                        checks.append(dmc.Checkbox(label=value, value=value))
                        values.append(value)
                else:
                    plain_df = parse_plain_columns_table(file_data)
                    signal_count = plain_df.shape[1] - 1
                    if signal_count > 1:
                        for b in range(1, signal_count + 1):
                            value = _parsed_signal_name(fname, str(b))
                            checks.append(dmc.Checkbox(label=value, value=value))
                            values.append(value)
                    else:
                        value = _upload_stem(fname)
                        checks.append(dmc.Checkbox(label=value, value=value))
                        values.append(value)

            elif ext == ".snc":
                _, names, _, settings, _ = parse_contents(list_of_contents[i], fname, 1)
                for col in names:
                    checks.append(dmc.Checkbox(label=col, value=col))
                    values.append(col)
                if settings and len(settings) != len(SNC_UI_SETTING_KEYS):
                    notifications.append(_toast("Upload warning", f"{fname}: settings are incomplete and will be ignored.", color="yellow"))
            else:
                notifications.append(_toast("Upload error", f"{fname}: unsupported file type."))
                continue

        except Exception as exc:
            logger.warning("Upload parse failed for %s: %s", fname, exc)
            notifications.append(_toast("Upload error", _friendly_upload_error(fname, ext, exc)))
            continue

    div_style = div_style if checks else {"display": "none"}
    return filenames, div_style, dmc.Group(checks, mt=5), values, notifications


# ---------- read selected files to stores ----------
@callback(
    Output("signal_raw", "data"),
    Output("selected-filenames-store", "data"),
    Output("selected-filenames-color-store", "data"),
    Output("signal-assumptions-store", "data"),
    Output("signal-end-ms-store", "data", allow_duplicate=True),
    Output("notify", "sendNotifications", allow_duplicate=True),
    Input("upload-data", "contents"),
    Input("checkbox-group", "value"),
    Input("time-unit-override", "value"),
    State("upload-data", "filename"),
    State("upload-data", "last_modified"),
    prevent_initial_call=True,
)
def store_raw_signals_selected_filenames(list_of_contents, selected_filenames, time_unit_override, list_of_names, list_of_dates):
    if not list_of_contents or not selected_filenames:
        raise PreventUpdate

    limit_notification = _validate_upload_size_limits(list_of_names, list_of_contents)
    if limit_notification is not None:
        return no_update, no_update, no_update, no_update, no_update, [limit_notification]

    stored, checked, values, max_times, assumptions, notifications = [], [], [], [], [], []

    for i, contents in enumerate(list_of_contents):
        name = list_of_names[i]
        ext = Path(name).suffix.lower()
        lower_name = name.lower()

        try:
            if lower_name.endswith(".pp.csv"):
                _, channel_list, _, _, _ = parse_contents(contents, name, 1)
                for channel in channel_list:
                    display_label = str(channel["label"])
                    value = _parsed_signal_name(name, display_label)
                    values.append(value)
                    if value not in selected_filenames:
                        continue
                    df_raw, _, _, _, meta = parse_contents(contents, name, int(channel["value"]))
                    df_raw = _ensure_time_ms_df(df_raw, meta, time_unit_override)
                    checked.append(value)
                    max_times.append(round_up(float(df_raw["time"].max()), 1))
                    stored.append(df_raw.to_dict())
                    assumptions.append({"name": value, "display_name": value, **meta})

            elif ext == ".sgy":
                df_first, channel_list, _, _, meta_first = parse_contents(contents, name, 1)
                df_first = _ensure_time_ms_df(df_first, meta_first)
                if not channel_list:
                    notifications.append(_toast("Upload error", f"{name}: SEG-Y file could not be parsed."))
                    continue
                for channel in channel_list:
                    ch = int(channel["value"])
                    value = _parsed_signal_name(name, str(ch))
                    values.append(value)
                    if value not in selected_filenames:
                        continue
                    if ch == 1:
                        df_raw, meta = df_first, meta_first
                    else:
                        df_raw, _, _, _, meta = parse_contents(contents, name, ch)
                    checked.append(value)
                    max_times.append(round_up(float(df_raw["time"].max()), 1))
                    stored.append(df_raw.to_dict())
                    assumptions.append({"name": value, "display_name": value, **meta})

            elif ext == ".snc":
                df_list, _, _, _, meta_list = parse_contents(contents, name, 1)
                for j in range(len(df_list)):
                    value = list(df_list[j].keys())[0][2:]
                    values.append(value)
                    if value not in selected_filenames:
                        continue
                    checked.append(value)
                    dfp = pd.DataFrame(df_list[j]).rename(columns=lambda c: "time" if c.startswith("t_") else ("amp" if c.startswith("s_") else c))
                    meta = meta_list[j] if j < len(meta_list) else {"assumed_input": "Unknown", "default_integrations": 0, "time_unit": "ms", "time_unit_known": True}
                    dfp = _ensure_time_ms_df(dfp, meta, time_unit_override)
                    max_times.append(round_up(float(dfp["time"].max()), 1))
                    stored.append(dfp.to_dict())
                    assumptions.append({"name": value, "display_name": value, **meta})
                break

            elif ext == ".txt":
                _, content_string = contents.split(",", 1)
                decoded = base64.b64decode(content_string)
                file_data = decode_txt_upload(decoded)
                if file_data is None:
                    notifications.append(_toast("Upload error", f"{name}: text file could not be decoded."))
                    continue

                if is_zbl_txt(file_data):
                    sections, _, section_keys, blow_times = parse_zbl_sections(file_data.splitlines())
                    labels = build_zbl_labels(section_keys, blow_times)
                    for ch, display_label in enumerate(labels, start=1):
                        value = _parsed_signal_name(name, str(display_label))
                        values.append(value)
                        if value not in selected_filenames:
                            continue
                        df_raw, _, _, _, meta = parse_contents(contents, name, ch)
                        df_raw = _ensure_time_ms_df(df_raw, meta, time_unit_override)
                        checked.append(value)
                        max_times.append(round_up(float(df_raw["time"].max()), 1))
                        stored.append(df_raw.to_dict())
                        if not meta.get("time_unit_known", True) and time_unit_override:
                            meta = {**meta, "time_unit": time_unit_override}
                        assumptions.append({"name": value, "display_name": value, **meta})
                else:
                    plain_df = parse_plain_columns_table(file_data)
                    signal_count = plain_df.shape[1] - 1
                    if signal_count > 1:
                        for ch in range(1, signal_count + 1):
                            value = _parsed_signal_name(name, str(ch))
                            values.append(value)
                            if value not in selected_filenames:
                                continue
                            df_raw, _, _, _, meta = parse_contents(contents, name, ch)
                            df_raw = _ensure_time_ms_df(df_raw, meta, time_unit_override)
                            checked.append(value)
                            max_times.append(round_up(float(df_raw["time"].max()), 1))
                            stored.append(df_raw.to_dict())
                            if not meta.get("time_unit_known", True) and time_unit_override:
                                meta = {**meta, "time_unit": time_unit_override}
                            assumptions.append({"name": value, "display_name": value, **meta})
                    else:
                        value = _upload_stem(name)
                        values.append(value)
                        if value in selected_filenames:
                            df_raw, _, _, _, meta = parse_contents(contents, name, 1)
                            df_raw = _ensure_time_ms_df(df_raw, meta, time_unit_override)
                            checked.append(value)
                            max_times.append(round_up(float(df_raw["time"].max()), 1))
                            stored.append(df_raw.to_dict())
                            if not meta.get("time_unit_known", True) and time_unit_override:
                                meta = {**meta, "time_unit": time_unit_override}
                            assumptions.append({"name": value, "display_name": value, **meta})
        except Exception as exc:
            logger.warning("Upload parse failed for %s: %s", name, exc)
            notifications.append(_toast("Upload error", _friendly_upload_error(name, ext, exc)))
            continue

    if not max_times:
        if notifications:
            return no_update, no_update, no_update, no_update, no_update, notifications
        raise PreventUpdate

    colors = [LIST_COLORS[i % len(LIST_COLORS)] for i in range(len(values))]
    color_map = {values[i]: colors[i] for i in range(len(values))}
    signal_end_value = None if _current_triggered_id() == "time-unit-override" else no_update
    return stored, checked, color_map, assumptions, signal_end_value, notifications


# ---------- render signal end slider ----------
@callback(
    Output("time-slider-container", "children"),
    Input("signal_raw", "data"),
    Input("signal-assumptions-store", "data"),
    State("signal-end-ms-store", "data"),
    Input("detrend-switch", "value"),
    Input("detrend-tick", "value"),
    Input("shift-switch", "value"),
    Input("flip-polarity-switch", "value"),
    Input("peak-distance", "value"),
    Input("peak-width-min", "value"),
    Input("peak-width-max", "value"),
    Input("peak-prominence-min", "value"),
    Input("integration-mode", "value"),
    Input("integration-method", "value"),
    Input("integration-lowfreq-hz", "value"),
    Input("integration-zero-baseline-switch", "value"),
    Input("filter-switch", "value"),
    Input("filter-tick", "value"),
    Input("forward-backward-filter-switch", "value"),
    Input("filter-cutoff_lp", "value"),
    Input("filter-cutoff_hp", "value"),
    Input("filter-order", "value"),
    Input("downsample-factor", "value"),
    Input("downsample-aa", "value"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
)
def render_signal_end_slider(
    raw_signals, signal_assumptions, signal_end_ms, detrend_on, detrend_after_amp,
    shift_on, flip_polarity, pk_dist, pk_wmin, pk_wmax, pk_prom, integration_mode, integration_method,
    integration_low_frequency_hz, integration_zero_baseline, filt_on, filter_before_amp, fwd_bwd,
    f_lp, f_hp, f_ord, d_user, aa_on, to_length, wavespeed,
):
    if not raw_signals:
        raise PreventUpdate

    max_end_ms = _max_display_end_ms(
        raw_signals,
        signal_assumptions,
        detrend_on=detrend_on,
        detrend_after_amp=detrend_after_amp,
        shift_on=shift_on,
        flip_polarity=flip_polarity,
        pk_dist=pk_dist,
        pk_wmin=pk_wmin,
        pk_wmax=pk_wmax,
        pk_prom=pk_prom,
        integration_mode=integration_mode,
        integration_method=integration_method,
        integration_low_frequency_hz=integration_low_frequency_hz,
        integration_zero_baseline=integration_zero_baseline,
        filt_on=filt_on,
        filter_before_amp=filter_before_amp,
        fwd_bwd=fwd_bwd,
        f_lp=f_lp,
        f_hp=f_hp,
        f_ord=f_ord,
        d_user=d_user,
        aa_on=aa_on,
    )
    if max_end_ms is None:
        raise PreventUpdate

    current_end_ms = max_end_ms if signal_end_ms is None else min(float(signal_end_ms), max_end_ms)
    unit_scale = (float(wavespeed) / 2000.0) if to_length else 1.0
    max_display_value = max_end_ms * unit_scale
    slider_step = _signal_end_slider_step(max_display_value)
    decimals = _step_decimals(slider_step)
    slider_max = round_up(max_display_value, decimals)
    slider_value = min(slider_max, round(float(current_end_ms) * unit_scale, decimals))
    return dmc.Slider(
        min=0,
        max=slider_max,
        step=slider_step,
        precision=decimals,
        value=slider_value,
        id="time-slider",
        className="ep-main-slider",
        marks=None,
        color="cyan",
        size="xs",
        styles=DMC_SLIDER_STYLES,
        style=DMC_SLIDER_WRAPPER_STYLE,
        updatemode="mouseup",
        labelAlwaysOn=True,
    )


# ---------- store signal end in canonical milliseconds ----------
@callback(
    Output("signal-end-ms-store", "data", allow_duplicate=True),
    Input("time-slider", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def store_signal_end_ms(slider_value, to_length, wavespeed):
    if slider_value is None:
        raise PreventUpdate

    slider_value = float(slider_value)
    if to_length:
        if not wavespeed:
            raise PreventUpdate
        return slider_value * 2000.0 / float(wavespeed)
    return slider_value


def _averaging_window_display(value_ms, to_length, wavespeed):
    value_ms = float(value_ms or 0.0)
    unit_scale = (float(wavespeed) / 2000.0) if to_length else 1.0
    max_value = 3.0 * unit_scale
    step_value = 0.01 * unit_scale
    decimals = max(1, _step_decimals(step_value))
    display_value = round(min(max(value_ms, 0.0), 3.0) * unit_scale, decimals)
    display_max = round(max_value, decimals)

    def _mark_key(mark_value: float) -> float:
        if mark_value == 0.0:
            return 0.0
        rounded_int = round(mark_value)
        if abs(mark_value - rounded_int) > 10 ** (-(decimals + 1)):
            return mark_value
        epsilon = min(step_value / 100.0, 10 ** (-(decimals + 2)))
        return mark_value - epsilon if abs(mark_value - display_max) <= epsilon else mark_value + epsilon

    marks = {
        0: {"label": "OFF", "style": {"whiteSpace": "nowrap"}},
    }
    for base_ms in (1.0, 2.0, 3.0):
        mark_value = round(base_ms * unit_scale, decimals)
        marks[_mark_key(mark_value)] = {
            "label": f"{mark_value:.{decimals}f}",
            "style": {"whiteSpace": "nowrap"},
        }

    return display_max, step_value, marks, min(display_value, display_max)


@callback(
    Output("av-win-slider-container", "children"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("av-win-ms-store", "data"),
)
def render_averaging_window_slider(to_length, wavespeed, av_win_ms):
    if wavespeed is None:
        raise PreventUpdate

    slider_max, slider_step, slider_marks, slider_value = _averaging_window_display(av_win_ms, to_length, wavespeed)
    return dmc.Slider(
        min=0,
        max=slider_max,
        step=slider_step,
        precision=max(1, _step_decimals(slider_step)),
        value=slider_value,
        id="av-win-slider",
        className="ep-main-slider",
        marks=_dmc_slider_marks(slider_marks),
        color="cyan",
        size="xs",
        styles=DMC_SLIDER_STYLES,
        style=DMC_SLIDER_WRAPPER_STYLE,
        updatemode="mouseup",
        showLabelOnHover=True,
    )


@callback(
    Output("av-win-ms-store", "data", allow_duplicate=True),
    Input("av-win-slider", "value"),
    State("length-switch", "value"),
    State("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def store_averaging_window_ms(slider_value, to_length, wavespeed):
    if slider_value is None:
        raise PreventUpdate

    slider_value = float(slider_value)
    if to_length:
        if not wavespeed:
            raise PreventUpdate
        return slider_value * 2000.0 / float(wavespeed)
    return slider_value


@callback(
    Output("btn-save-time-plot-wrap", "style"),
    Output("amplitude-spectrum-label-wrap", "style"),
    Output("btn-save-spectrum-plot-wrap", "style"),
    Input("selected-filenames-store", "data"),
)
def toggle_plot_save_buttons(filenames):
    if filenames:
        return (
            {"display": "block", "marginTop": "4px", "marginBottom": "8px"},
            {"display": "block", "marginTop": "18px"},
            {"display": "block", "marginTop": "10px"},
        )
    return (
        {"display": "none", "marginTop": "4px", "marginBottom": "8px"},
        {"display": "none", "marginTop": "18px"},
        {"display": "none", "marginTop": "10px"},
    )


# ---------- dependent numeric limits ----------
@callback(
    Output("multiple-reflections", "max"),
    Output("length-marker", "max"),
    Input("time-slider", "value"),
)
def get_max_multiple_reflection(t_max):
    if t_max is None:
        raise PreventUpdate
    return t_max, t_max * 2.5


# ---------- find downsample factor and its limits ----------
@callback(
    Output("downsample-factor", "max"),
    Output("downsample-factor", "value", allow_duplicate=True),
    Input("signal_raw", "data"),
    State("downsample-factor", "value"),
    State("filter-cutoff_lp", "value"),
    prevent_initial_call=True,
)
def set_downsample_factor_limits(raw_signals, cur_val, f_lp):
    if not raw_signals:
        raise PreventUpdate

    f_need = 4000.0  # вЂњsafeвЂќ floor for PIT signals < 4 kHz
    if isinstance(f_lp, (int, float)) and f_lp:
        f_need = max(f_need, float(f_lp))

    caps, d20 = [], []
    for rs in raw_signals:
        df = pd.DataFrame(rs)
        t = df["time"].to_numpy(float)
        n = t.size
        if n < 2:
            continue
        dt_ms = float(np.median(np.diff(t)))
        if dt_ms <= 0:
            continue
        fs = 1000.0 / dt_ms

        d_len = max(1, int(np.floor(n / 50.0)))                      # keep в‰Ґ 50 samples
        d_nyq = max(1, int(np.floor(fs / max(2.2 * f_need, 1.0))))   # Nyquist guard (optional)
        caps.append(max(1, min(d_len, d_nyq)))

        d20.append(max(1, int(np.floor(fs / 99000.0))))              # gentle default toward 99 kHz

    if not caps:
        raise PreventUpdate

    d_max = int(max(1, min(caps)))                      # global cap across files
    trig = _current_triggered_id()

    if trig == "signal_raw":                            # on load, suggest a default
        d_suggest = int(np.median(d20)) if d20 else 1
        d_val = min(max(1, d_suggest), d_max)
    else:                                               # clamp current value to cap
        d_val = int(max(1, min(int(cur_val or 1), d_max)))

    return d_max, d_val

def _decoded_upload_size_bytes(contents):
    if not contents:
        return 0
    try:
        _, content_string = contents.split(",", 1)
    except ValueError:
        return 0
    try:
        return len(base64.b64decode(content_string))
    except Exception:
        return 0


def _validate_upload_size_limits(filenames, list_of_contents):
    if not filenames or not list_of_contents:
        return None

    total_bytes = 0
    for fname, contents in zip(filenames, list_of_contents):
        size_bytes = _decoded_upload_size_bytes(contents)
        total_bytes += size_bytes
        if size_bytes > MAX_UPLOAD_FILE_BYTES:
            return _toast(
                "Upload error",
                f"{fname}: file exceeds the {MAX_UPLOAD_FILE_MB} MB limit.",
            )

    if total_bytes > MAX_UPLOAD_TOTAL_BYTES:
        return _toast(
            "Upload error",
            f"Total upload size exceeds the {MAX_UPLOAD_TOTAL_MB} MB limit.",
        )

    return None


def _toast(title, msg, color="red"):
    return {
        "action": "show",
        "title": title,
        "message": msg,
        "color": color,
        "withCloseButton": True,
        "autoClose": 4000,
    }


def _friendly_upload_error(fname, ext, exc):
    raw_msg = str(exc).strip().rstrip('.')
    msg = raw_msg.lower()
    lower_name = fname.lower()

    if "out of range" in msg:
        return f"{fname}: selected signal is not available in this file."

    if lower_name.endswith(".pp.csv"):
        if "decode" in msg:
            return f"{fname}: PET file could not be decoded."
        if "signal table" in msg:
            return f"{fname}: PET signal table was not found."
        if "sampling rate" in msg:
            return f"{fname}: PET sampling rate could not be read."
        if "readable signals" in msg:
            return f"{fname}: PET file does not contain readable signals."
        return f"{fname}: {raw_msg}."

    if ext == ".sgy":
        if "dependencies are unavailable" in msg:
            return f"{fname}: SEG-Y support is unavailable because required dependencies are not installed."
        if "readable traces" in msg:
            return f"{fname}: SEG-Y file does not contain readable traces."
        return f"{fname}: {raw_msg}."

    if ext == ".snc":
        if "decode" in msg:
            return f"{fname}: SNC file could not be decoded."
        if "raw signal table" in msg:
            return f"{fname}: SNC file does not contain the saved raw signal table."
        return f"{fname}: {raw_msg}."

    if ext == ".txt":
        if "decode" in msg:
            return f"{fname}: text file could not be decoded."
        if "zbl waveform" in msg:
            return f"{fname}: ZBL waveform blocks could not be parsed."
        if "plain text file must contain at least time and one signal column" in msg:
            return f"{fname}: plain text file must contain at least two numeric columns: time and one signal."
        if "plain text file must contain at least two numeric rows" in msg:
            return f"{fname}: plain text file must contain at least two numeric rows."
        if "plain text file must contain at least two time samples" in msg:
            return f"{fname}: plain text file must contain at least two time samples."
        if "plain text file contains invalid time values" in msg:
            return f"{fname}: time column contains invalid numeric values."
        if "plain text time axis must be strictly increasing" in msg:
            return f"{fname}: time column must be strictly increasing."
        if "plain text time axis must be uniformly sampled" in msg:
            return f"{fname}: time column is not uniformly sampled enough for processing."
        return f"{fname}: {raw_msg}."

    return f"{fname}: {raw_msg}."

@callback(
    Output("assumed-input-summary", "children"),
    Output("assumed-input-details", "children"),
    Output("time-unit-row", "style"),
    Output("notify", "sendNotifications", allow_duplicate=True),
    Input("signal-assumptions-store", "data"),
    Input("integration-mode", "value"),
    prevent_initial_call=True,
)
def update_integration_assumptions(signal_assumptions, integration_mode):
    hidden_time_unit_style = {**SETTINGS_ROW_STYLE, "display": "none"}
    if not signal_assumptions:
        return "", [], hidden_time_unit_style, []

    def _assumption_text(value):
        text = str(value or "Unknown").strip().lower()
        if text == "acceleration":
            return "acceleration (integrated once in Auto mode)"
        if text == "unknown":
            return "unknown (no integration in Auto mode)"
        return text

    assumed = [item.get("assumed_input", "Unknown") for item in signal_assumptions]
    unique_assumed = {_assumption_text(item) for item in assumed}
    count = len(signal_assumptions)

    if len(unique_assumed) == 1:
        assumed_text = _assumption_text(assumed[0])
        if count == 1:
            summary = assumed_text
        else:
            summary = f"{assumed_text} for all loaded files"
        details = []
    else:
        summary = "Mixed"
        details = [
            html.Div(f"{item.get('display_name') or item.get('name', 'signal')}: {_assumption_text(item.get('assumed_input', 'Unknown'))}")
            for item in signal_assumptions
        ]

    notifications = []
    default_integrations = {int(item.get("default_integrations", 0)) for item in signal_assumptions}
    if integration_mode == "Auto" and len(default_integrations) > 1:
        notifications.append(
            _toast(
                "Integration warning",
                "Uploaded files have different default integration settings. Auto will use each file default.",
                color="yellow",
            )
        )

    show_time_unit = any(not bool(item.get("time_unit_known", True)) for item in signal_assumptions)
    time_unit_style = dict(SETTINGS_ROW_STYLE) if show_time_unit else hidden_time_unit_style

    return summary, details, time_unit_style, notifications


@callback(
    Output("integration-lowfreq-row", "style"),
    Input("integration-method", "value"),
)
def toggle_integration_lowfreq_row(integration_method):
    return dict(SETTINGS_ROW_STYLE) if integration_method == "regularized_fd" else {**SETTINGS_ROW_STYLE, "display": "none"}

# ---------- core processing ----------
@callback(
    Output("signal", "data"),
    Output("peaks", "data"),
    Output("spectrum", "data"),
    Output("av_signal", "data"),
    Output("notify", "sendNotifications", allow_duplicate=True),
    Input("signal_raw", "data"),
    Input("selected-filenames-store", "data"),
    Input("signal-assumptions-store", "data"),
    Input("amp-slider", "value"),
    Input("signal-end-ms-store", "data"),
    Input("detrend-switch", "value"),
    Input("detrend-tick", "value"),
    Input("shift-switch", "value"),
    Input("flip-polarity-switch", "value"),
    Input("peak-distance", "value"),
    Input("peak-width-min", "value"),
    Input("peak-width-max", "value"),
    Input("peak-prominence-min", "value"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("integration-mode", "value"),
    Input("integration-method", "value"),
    Input("integration-lowfreq-hz", "value"),
    Input("integration-zero-baseline-switch", "value"),
    Input("filter-switch", "value"),
    Input("filter-tick", "value"),
    Input("forward-backward-filter-switch", "value"),
    Input("filter-cutoff_lp", "value"),
    Input("filter-cutoff_hp", "value"),
    Input("filter-order", "value"),
    Input("av-win-ms-store", "data"),
    Input("smoothing-slider", "value"),
    Input("downsample-factor", "value"),
    Input("downsample-aa", "value"),
    Input("signal-window-switch", "value"),
    Input("signal-window-taper-ms-store", "data"),
    Input("signal-window-padding-ms-store", "data"),
    prevent_initial_call=True,
)
def process_signal(
    raw_signals, selected, signal_assumptions, a0, lim_t,
    detrend_on, detrend_after_amp, shift_on, flip_polarity, pk_dist, pk_wmin, pk_wmax, pk_prom,
    to_length, wavespeed, integration_mode, integration_method, integration_low_frequency_hz, integration_zero_baseline, filt_on, filter_before_amp, fwd_bwd,
    f_lp, f_hp, f_ord, mov_win, spline_smooth, d_user, aa_on, signal_window_on=False, signal_window_taper_ms=0.0, signal_window_padding_ms=0.0,
):
    if None in (raw_signals, selected, wavespeed) or not selected:
        raise PreventUpdate
    
    def _bad(msg):
        return (
            no_update, no_update, no_update, no_update,
            [_toast("Not enough samples", msg)],
        )

    try:
        result = core_process_signals(
            raw_signals,
            selected,
            signal_assumptions,
            a0,
            lim_t,
            detrend_on,
            detrend_after_amp,
            shift_on,
            flip_polarity,
            pk_dist,
            pk_wmin,
            pk_wmax,
            pk_prom,
            to_length,
            wavespeed,
            integration_mode,
            integration_method,
            integration_low_frequency_hz,
            integration_zero_baseline,
            filt_on,
            filter_before_amp,
            fwd_bwd,
            f_lp,
            f_hp,
            f_ord,
            mov_win,
            spline_smooth,
            d_user,
            aa_on,
            signal_window_on=signal_window_on,
            signal_window_taper_ms=signal_window_taper_ms,
            signal_window_padding_ms=signal_window_padding_ms,
        )
    except ValueError as exc:
        return _bad(str(exc))

    notifications = [
        _toast(item["title"], item["message"], color=item.get("color", "red"))
        for item in result["notifications"]
    ]
    return result["signal"], result["peaks"], result["spectrum"], result["av_signal"], notifications


# ---------- update the downsample info ----------
@callback(
    Output("downsample-fs-info", "children"),
    Output("downsample-factor-info", "children"),
    Output("downsample-factor-row", "style"),
    Input("signal_raw", "data"),
    Input("downsample-factor", "value"),
    Input("downsample-aa", "value"),
    Input("filter-cutoff_lp", "value"),
)
def update_downsample_info(raw_signals, d_user, aa_on, f_lp):
    if not raw_signals:
        raise PreventUpdate

    f_need = max(4000.0, float(f_lp or 0)) # вЂњsafeвЂќ floor for PIT signals < 4 kHz
    fs_in_list, fs_out_list, fac_list = [], [], []

    for rs in raw_signals:
        df = pd.DataFrame(rs)
        t = df["time"].to_numpy(float)
        if t.size < 2:
            continue
        dt_ms = float(np.median(np.diff(t)))
        if dt_ms <= 0:
            continue
        fs_in = 1000.0 / dt_ms
        _, _, fs_out, d_used = decimate_factor_per_file(
            t_ms=t, y=np.zeros_like(t), fs_hz=fs_in,
            d_user=int(d_user or 1),
            f_need_hz=f_need, ensure_min_samples=50,
            gamma=2.2, anti_alias=bool(aa_on),
        )
        fs_in_list.append(fs_in); fs_out_list.append(fs_out); fac_list.append(d_used)

    def approx_equal_all(vals):
        if not vals: return True
        v0 = vals[0]
        return all(abs(v - v0) <= 1e-6 * max(1.0, v0) for v in vals)

    def fmt_khz_list(vals):
        return ", ".join(f"{v/1000:.2f}" for v in vals) + " kHz" if vals else ""

    # Sampling condensed
    if approx_equal_all(fs_in_list) and approx_equal_all(fs_out_list):
        fs_info = f"in: {fs_in_list[0]/1000:.2f} kHz | out: {fs_out_list[0]/1000:.2f} kHz"
    else:
        fs_info = f"in: {fmt_khz_list(fs_in_list)} | out: {fmt_khz_list(fs_out_list)}"

    fac_same = approx_equal_all(fac_list)
    fac_info = "" if fac_same else ", ".join(f"Г—{int(d)}" for d in fac_list)
    fac_style = {"display": "none"} if fac_same else {"display": "block"}

    return fs_info, fac_info, fac_style


# ---------- wavespeed input/slider sync ----------
@callback(
    Output("wavespeed-input", "value"),
    Output("wavespeed-slider", "value", allow_duplicate=True),
    Input("wavespeed-input", "value"),
    Input("wavespeed-slider", "value"),
    prevent_initial_call=True,
)
def wavespeed_slider_input_sync(input_value, slider_value):
    trig = _current_triggered_id()
    if isinstance(input_value, str) and trig == "wavespeed-input":
        raise PreventUpdate
    value = input_value if trig == "wavespeed-input" else slider_value
    return value, value


@callback(
    Output("freq_SLT_no", "value", allow_duplicate=True),
    Input("freq_SLT_no", "value"),
    prevent_initial_call=True,
)
def normalize_slt_frequency_count(value):
    if value is None:
        raise PreventUpdate

    try:
        normalized = max(1, int(round(float(value))))
    except (TypeError, ValueError):
        return 1

    if isinstance(value, (int, float)) and float(value) == normalized:
        return no_update
    return normalized


# ---------- load .snc settings into UI ----------
@callback(
    Output("amp-slider", "value"),
    Output("signal-end-ms-store", "data"),
    Output("detrend-switch", "value"),
    Output("detrend-tick", "value"),
    Output("shift-switch", "value"),
    Output("flip-polarity-switch", "value"),
    Output("peak-distance", "value"),
    Output("peak-width-min", "value"),
    Output("peak-width-max", "value"),
    Output("peak-prominence-min", "value"),
    Output("length-switch", "value"),
    Output("wavespeed-slider", "value"),
    Output("main-plot-width", "value"),
    Output("main-plot-height", "value"),
    Output("downsample-factor", "value"),
    Output("downsample-aa", "value"),
    Output("filter-switch", "value"),
    Output("forward-backward-filter-switch", "value"),
    Output("filter-cutoff_lp", "value"),
    Output("filter-cutoff_hp", "value"),
    Output("filter-order", "value"),
    Output("spectrum-autozoom-x", "value"),
    Output("av-win-ms-store", "data"),
    Output("smoothing-slider", "value"),
    Output("length-marker", "value"),
    Output("multiple-reflections", "value"),
    Output("generic-marker-input", "value"),
    Output("generic-marker-text", "value"),
    Output("show-markers-switch", "value"),
    Output("simplify-plot-switch", "value"),
    Output("reverse-axis-switch", "value"),
    Output("signal-window-switch", "value"),
    Output("signal-window-taper-ms-store", "data"),
    Output("signal-window-padding-ms-store", "data"),
    Output("superlet-switch", "value"),
    Output("slt-mode", "value"),
    Output("superlet-set-mode", "value"),
    Output("superlet-phase-combination", "value"),
    Output("superlet-coi-mask-switch", "value"),
    Output("freq_SLT_min", "value"),
    Output("freq_SLT_max", "value"),
    Output("freq_SLT_no", "value"),
    Output("c_1", "value"),
    Output("k_sd", "value"),
    Output("support_sd", "value"),
    Output("order_slt", "value"),
    Output("order_min", "value"),
    Output("order_max", "value"),
    Output("SLT_output", "value"),
    Output("cmap_SLT", "value"),
    Output("cmap_SLT_min", "value"),
    Output("cmap_SLT_max", "value"),
    Output("cmap_SLT_log", "value"),
    Output("cmap_SLT_log_floor_exp", "value"),
    Output("superlet-attributes-switch", "value"),
    Output("superlet-attribute-placement", "value"),
    Output("superlet-attribute-keys", "value"),
    Output("superlet-attr-normalize-switch", "value"),
    Output("superlet-attr-zero-baseline-switch", "value"),
    Output("superlet-attr-freq-reduce", "value"),
    Output("superlet-attr-x-reduce", "value"),
    Output("superlet-attr-x-window-ms-store", "data"),
    Output("superlet-attr-band-min-hz", "value"),
    Output("superlet-attr-band-max-hz", "value"),
    Output("superlet-attr-show-band-guides-switch", "value"),
    Output("superlet-attr-show-source-badge-switch", "value"),
    Output("superlet-attr-phase-freq-hz", "value"),
    Output("filter-draw-switch", "value"),
    Output("show-legend-switch", "value"),
    Output("filter-tick", "value"),
    Output("horizontal-subplots-switch", "value"),
    Output("y-axis-exponent-format", "value"),
    Output("time-unit-override", "value"),
    Output("integration-mode", "value"),
    Output("integration-method", "value"),
    Output("integration-lowfreq-hz", "value"),
    Output("integration-zero-baseline-switch", "value"),
    Output("notify", "sendNotifications", allow_duplicate=True),
    Input("upload-data", "contents"),
    Input("btn-reset-defaults", "n_clicks"),
    State("upload-data", "filename"),
    State("upload-data", "last_modified"),
    prevent_initial_call=True,
)
def load_settings(list_of_contents, reset_clicks, list_of_names, list_of_dates):
    defaults = get_snc_ui_defaults_list()
    defaults_map = get_snc_ui_defaults_map()
    trigger = _current_triggered_id()

    if trigger == "btn-reset-defaults":
        return (*defaults, [_toast("Settings reset", "Settings reset to defaults", color="green")])

    if trigger is None and list_of_contents and list_of_names:
        trigger = "upload-data"

    if trigger != "upload-data" or not list_of_contents or not list_of_names:
        raise PreventUpdate

    limit_notification = _validate_upload_size_limits(list_of_names, list_of_contents)
    if limit_notification is not None:
        return (*([no_update] * len(SNC_UI_SETTING_KEYS)), [limit_notification])
    try:
        idx = next(i for i, n in enumerate(list_of_names) if n.lower().endswith(".snc"))
    except StopIteration:
        raise PreventUpdate

    try:
        _, _, _, settings, _ = parse_contents(list_of_contents[idx], list_of_names[idx], 1)
    except Exception as exc:
        logger.warning("SNC settings load failed for %s: %s", list_of_names[idx], exc)
        return (*([no_update] * len(SNC_UI_SETTING_KEYS)), [_toast("Upload error", _friendly_upload_error(list_of_names[idx], ".snc", exc))])

    if settings and len(settings) != len(SNC_UI_SETTING_KEYS):
        return (*([no_update] * len(SNC_UI_SETTING_KEYS)), [_toast("Upload warning", f"{list_of_names[idx]}: settings are incomplete and will be ignored.", color="yellow")])

    settings = normalize_snc_settings_for_ui(settings)
    return (*settings, [])


@callback(
    Output("compute-result-store", "data"),
    Input("signal", "data"),
    Input("av_signal", "data"),
    Input("selected-filenames-store", "data"),
    Input("superlet-switch", "value"),
    Input("superlet-attributes-switch", "value"),
    Input("length-switch", "value"),
    Input("wavespeed-slider", "value"),
    Input("signal-window-switch", "value"),
    Input("signal-window-padding-ms-store", "data"),
    Input("slt-mode", "value"),
    Input("superlet-set-mode", "value"),
    Input("superlet-phase-combination", "value"),
    Input("freq_SLT_min", "value"),
    Input("freq_SLT_max", "value"),
    Input("freq_SLT_no", "value"),
    Input("c_1", "value"),
    Input("k_sd", "value"),
    Input("support_sd", "value"),
    Input("order_slt", "value"),
    Input("order_min", "value"),
    Input("order_max", "value"),
)
def compute_slt_result(
    data,
    av_signal,
    filenames,
    superlet_plot,
    superlet_attributes_on,
    to_length,
    wavespeed,
    signal_window_on,
    signal_window_padding_ms,
    slt_mode,
    superlet_set_mode,
    superlet_phase_combination,
    freq_slt_min,
    freq_slt_max,
    freq_slt_no,
    c_1,
    k_sd,
    support_sd,
    order_slt,
    order_min,
    order_max,
):
    if None in (data, filenames, wavespeed) or not filenames:
        raise PreventUpdate
    if not (superlet_plot or superlet_attributes_on):
        return {"cache_key": None, "error": None}

    try:
        x_values, signal_values, source_name = _current_slt_source(data, av_signal, filenames, "EN")
        cache_key = _build_slt_cache_key(
            x_values=x_values,
            signal_values=signal_values,
            source_name=source_name,
            to_length=to_length,
            wavespeed=wavespeed,
            padding_ms=float(signal_window_padding_ms or 0.0) if signal_window_on else 0.0,
            slt_mode=slt_mode,
            superlet_set_mode=superlet_set_mode,
            superlet_phase_combination=superlet_phase_combination,
            freq_min=freq_slt_min,
            freq_max=freq_slt_max,
            freq_count=freq_slt_no,
            c_1=c_1,
            k_sd=k_sd,
            support_sd=support_sd,
            order_slt=order_slt,
            order_min=order_min,
            order_max=order_max,
        )
        if _slt_cache_get(cache_key) is None:
            _slt_cache_set(
                cache_key,
                _compute_slt_bundle(
                    time_values=x_values,
                    signal_values=signal_values,
                    source_name=source_name,
                    to_length=bool(to_length),
                    wavespeed=float(wavespeed),
                    padding_ms=float(signal_window_padding_ms or 0.0) if signal_window_on else 0.0,
                    slt_mode=slt_mode,
                    superlet_set_mode=superlet_set_mode,
                    superlet_phase_combination=superlet_phase_combination,
                    freq_min=freq_slt_min,
                    freq_max=freq_slt_max,
                    freq_count=freq_slt_no,
                    c_1=c_1,
                    k_sd=k_sd,
                    support_sd=support_sd,
                    order_slt=order_slt,
                    order_min=order_min,
                    order_max=order_max,
                ),
            )
        return {"cache_key": cache_key, "error": None}
    except Exception as exc:
        return {"cache_key": None, "error": str(exc)}


# ---------- main time plot (and SLT) ----------
@callback(
    Output("time_plot", "children"),
    Input("signal", "data"),
    Input("av_signal", "data"),
    Input("peaks", "data"),
    Input("wavespeed-slider", "value"),
    Input("length-marker", "value"),
    Input("multiple-reflections", "value"),
    Input("generic-marker-input", "value"),
    Input("generic-marker-text", "value"),
    Input("show-markers-switch", "value"),
    Input("simplify-plot-switch", "value"),
    Input("reverse-axis-switch", "value"),
    Input("selected-filenames-store", "data"),
    Input("selected-filenames-color-store", "data"),
    Input("compute-result-store", "data"),
    Input("superlet-switch", "value"),
    Input("superlet-coi-mask-switch", "value"),
    Input("SLT_output", "value"),
    Input("cmap_SLT", "value"),
    Input("cmap_SLT_min", "value"),
    Input("cmap_SLT_max", "value"),
    Input("cmap_SLT_log", "value"),
    Input("cmap_SLT_log_floor_exp", "value"),
    Input("superlet-attributes-switch", "value"),
    Input("superlet-attribute-placement", "value"),
    Input("superlet-attribute-keys", "value"),
    Input("superlet-attr-normalize-switch", "value"),
    Input("superlet-attr-zero-baseline-switch", "value"),
    Input("superlet-attr-freq-reduce", "value"),
    Input("superlet-attr-x-reduce", "value"),
    Input("superlet-attr-x-window-ms-store", "data"),
    Input("superlet-attr-band-min-hz", "value"),
    Input("superlet-attr-band-max-hz", "value"),
    Input("superlet-attr-show-band-guides-switch", "value"),
    Input("superlet-attr-show-source-badge-switch", "value"),
    Input("superlet-attr-phase-freq-hz", "value"),
    Input("length-switch", "value"),
    Input("show-legend-switch", "value"),
    Input("horizontal-subplots-switch", "value"),
    Input("main-plot-width", "value"),
    Input("main-plot-height", "value"),
    Input("lang-segment", "value"),
    Input("y-axis-exponent-format", "value"),
)
def plot_signal(
    data, av_signal, peaks, wavespeed, length_marker, reflection, generic_marker_ms, generic_marker_label, show_markers, simplify_plot, reverse_axis,
    filenames, color_map, compute_store, superlet_plot, superlet_coi_mask_on, slt_out, cmap_name, cmin, cmax, cmap_log, cmap_log_floor_exp,
    superlet_attributes_on, superlet_attribute_placement, superlet_attribute_keys, superlet_attr_normalize, superlet_attr_zero_baseline, superlet_attr_freq_reduce, superlet_attr_x_reduce,
    superlet_attr_x_window_ms, superlet_attr_freq_min_hz, superlet_attr_freq_max_hz, superlet_attr_show_band_guides, superlet_attr_show_source_badge, superlet_attr_phase_freq_hz, to_length, show_legend, horizontal_subplots, plot_width_pct, plot_height_px, lang,
    y_axis_exponent_format="SI",
):
    if None in (data, filenames, wavespeed) or not filenames:
        raise PreventUpdate
    return _render_time_plot(
        data=data,
        av_signal=av_signal,
        peaks=peaks,
        wavespeed=wavespeed,
        length_marker=length_marker,
        reflection=reflection,
        generic_marker_ms=generic_marker_ms,
        generic_marker_label=generic_marker_label,
        show_markers=show_markers,
        simplify_plot=simplify_plot,
        reverse_axis=reverse_axis,
        filenames=filenames,
        color_map=color_map,
        compute_store=compute_store,
        superlet_plot=superlet_plot,
        superlet_coi_mask_on=superlet_coi_mask_on,
        slt_out=slt_out,
        cmap_name=cmap_name,
        cmin=cmin,
        cmax=cmax,
        cmap_log=cmap_log,
        cmap_log_floor_exp=cmap_log_floor_exp,
        superlet_attributes_on=superlet_attributes_on,
        superlet_attribute_placement=superlet_attribute_placement,
        superlet_attribute_keys=superlet_attribute_keys,
        superlet_attr_normalize=superlet_attr_normalize,
        superlet_attr_zero_baseline=superlet_attr_zero_baseline,
        superlet_attr_freq_reduce=superlet_attr_freq_reduce,
        superlet_attr_x_reduce=superlet_attr_x_reduce,
        superlet_attr_x_window_ms=superlet_attr_x_window_ms,
        superlet_attr_freq_min_hz=superlet_attr_freq_min_hz,
        superlet_attr_freq_max_hz=superlet_attr_freq_max_hz,
        superlet_attr_show_band_guides=superlet_attr_show_band_guides,
        superlet_attr_show_source_badge=superlet_attr_show_source_badge,
        superlet_attr_phase_freq_hz=superlet_attr_phase_freq_hz,
        to_length=to_length,
        show_legend=show_legend,
        horizontal_subplots=horizontal_subplots,
        plot_width_pct=plot_width_pct,
        plot_height_px=plot_height_px,
        lang=lang,
        y_axis_exponent_format=y_axis_exponent_format,
    )

# ---------- spectrum ----------
@callback(
    Output("spectrum_plot", "children"),
    Input("spectrum", "data"),
    Input("filter-switch", "value"),
    Input("filter-draw-switch", "value"),
    Input("selected-filenames-store", "data"),
    Input("selected-filenames-color-store", "data"),
    Input("spectrum-autozoom-x", "value"),
    Input("show-legend-switch", "value"),
    Input("lang-segment", "value"),
    Input("y-axis-exponent-format", "value"),
)
def plot_spectrum(spectrum, filter_switch, filter_draw, filenames, color_map, spectrum_autozoom_x, show_legend, lang, y_axis_exponent_format="SI"):
    if spectrum is None or not filenames:
        raise PreventUpdate
    y_axis_exponent_format = _normalize_y_axis_exponent_format(y_axis_exponent_format)

    xf_list, yf_list, xff_list, yff_list, w, h = spectrum[0], spectrum[1], spectrum[2], spectrum[3], spectrum[4], spectrum[5]
    multi = len(filenames) != 1

    fig = go.Figure(
        layout=go.Layout(
            height=SPECTRUM_PLOT_HEIGHT_PX,
            xaxis={"title": translate("Frequency, Hz", lang), "zeroline": False},
            yaxis={"title": translate("Amplitude", lang), "zeroline": False},
        )
    )

    for i in range(len(xf_list)):
        if multi:
            col = _rgba_from_hex(color_map[filenames[i]], ALPHA_TRACE)
            trace = go.Scatter(x=xf_list[i], y=yf_list[i], name=filenames[i], mode="lines", line={"color": col, "width": 1.5})
        else:
            trace = go.Scatter(
                name="before filtering",
                x=xf_list[i], y=yf_list[i],
                mode="lines",
                line={"color": "rgba(132,30,98,0.99)", "width": 1.0},
                fill="tozeroy", fillcolor="rgba(132,30,98,0.75)",
            )
        fig.add_trace(trace)

        if filter_switch:
            if multi:
                col = _rgba_from_hex(color_map[filenames[i]], ALPHA_TRACE)
                trace_f = go.Scatter(
                    name=translate("after filtering", lang),
                    x=xff_list[i], y=yff_list[i],
                    mode="lines", line={"color": col, "width": 1.5}, line_dash="dot",
                )
            else:
                trace_f = go.Scatter(
                    name="after filtering",
                    x=xff_list[i], y=yff_list[i],
                    mode="lines",
                    line={"color": "rgba(0,0,0,0.5)", "width": 1.5}, line_dash="dot",
                    fill="tozeroy", fillcolor="rgba(35,197,82,0.99)",
                )
            fig.add_trace(trace_f)

    if filter_draw and filter_switch and w is not None and h is not None:
        fig.add_trace(
            go.Scatter(
                name=translate("filter response", lang),
                x=w, y=h, mode="lines", line={"color": "#FF4949", "width": 2.0}, line_dash="dash",
            )
        )
    source_freq = xf_list
    source_amp = yf_list
    full_xmax = _spectrum_full_xmax(source_freq, w if filter_draw and filter_switch and w is not None else None)
    auto_xmax = _spectrum_autozoom_xmax(source_freq, source_amp) if spectrum_autozoom_x else None
    x_max = auto_xmax if auto_xmax is not None else full_xmax

    xaxis_kwargs = {
        "rangemode": "tozero",
        "zeroline": False,
        "showline": True,
        "linewidth": 1,
        "linecolor": "grey",
    }
    if x_max is not None and x_max > 0:
        xaxis_kwargs["range"] = [0, x_max]

    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(rangemode="tozero", exponentformat=y_axis_exponent_format)

    show_sp_legend = bool(show_legend) and not (not filter_switch and not multi)
    fig.update_layout(showlegend=show_sp_legend, font=dict(size=15), margin=dict(r=25, t=30))

    filename = f"spectrum_{filenames[0].split('.')[0]}"
    config = {
        "displaylogo": True,
        "toImageButtonOptions": {"filename": filename, "scale": 10},
        "modeBarButtonsToRemove": ["pan", "select", "zoomIn", "zoomOut", "lasso2d"],
    }
    return [dcc.Graph(id="graph_spectrum", config=config, figure=fig)]





