"""High-level signal processing flow used by the interactive app."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid

from .signal_processing import (
    BSpline,
    amplificate_signal,
    butter_lowpass,
    butter_lowpass_filter,
    decimate_factor_per_file,
    find_peaks,
    find_reference_peak_time,
    flip_signal_polarity,
    get_spectrum,
    regularized_fd_integrate,
    shift_signal,
    sosfreqz,
    sp_detrend,
    splrep,
    zero_baseline,
)


def ensure_time_ms_df(
    df: pd.DataFrame,
    meta: Optional[dict] = None,
    time_unit_override: Optional[str] = None,
) -> pd.DataFrame:
    meta = meta or {}
    out = df.copy()
    time_unit_known = bool(meta.get("time_unit_known", True))

    if "time_raw" in out.columns and not time_unit_known:
        unit = str(time_unit_override or meta.get("time_unit", "s") or "s").lower()
        scale_map = {"s": 1000.0, "ms": 1.0, "us": 0.001}
        scale = scale_map.get(unit)
        if scale is None:
            raise ValueError(f"Unsupported time unit: {unit}")

        out["time_raw"] = pd.to_numeric(out["time_raw"], errors="coerce")
        if out["time_raw"].isna().any():
            raise ValueError("Trace contains invalid time values.")
        out["time_raw"] = out["time_raw"].astype(float)
        out["time"] = out["time_raw"] * scale
        return out

    if "time" in out.columns:
        out["time"] = pd.to_numeric(out["time"], errors="coerce")
        if out["time"].isna().any():
            raise ValueError("Trace contains invalid time values.")
        out["time"] = out["time"].astype(float)
        if "time_raw" in out.columns:
            out["time_raw"] = pd.to_numeric(out["time_raw"], errors="coerce").astype(float)
        return out

    if "time_raw" not in out.columns:
        raise ValueError("Trace does not contain a time axis.")

    unit = str(meta.get("time_unit", "s") or "s").lower()
    scale_map = {"s": 1000.0, "ms": 1.0, "us": 0.001}
    scale = scale_map.get(unit)
    if scale is None:
        raise ValueError(f"Unsupported time unit: {unit}")

    out["time_raw"] = pd.to_numeric(out["time_raw"], errors="coerce")
    if out["time_raw"].isna().any():
        raise ValueError("Trace contains invalid time values.")
    out["time_raw"] = out["time_raw"].astype(float)
    out["time"] = out["time_raw"] * scale
    return out


def empty_peak_markers():
    return [[[None], [None]], [[None], [None]]]


def build_peak_markers(x_values, amp_values, pk_dist, pk_prom, pk_wmin, pk_wmax):
    x = pd.Series(x_values).reset_index(drop=True)
    y = pd.Series(amp_values).reset_index(drop=True)
    if len(x) < 2 or len(y) < 2:
        return empty_peak_markers()

    p_pos, _ = find_peaks(y, distance=pk_dist, prominence=pk_prom, width=(pk_wmin, pk_wmax))
    p_neg, _ = find_peaks(-y, distance=pk_dist, prominence=pk_prom, width=(pk_wmin, pk_wmax))

    peaks_pos = [x.iloc[p_pos].to_list(), y.iloc[p_pos].to_list()] if p_pos.size else [[None], [None]]
    peaks_neg = [x.iloc[p_neg].to_list(), y.iloc[p_neg].to_list()] if p_neg.size else [[None], [None]]
    return [peaks_pos, peaks_neg]


def _notification(title: str, message: str, color: str = "red") -> dict[str, str]:
    return {"title": title, "message": message, "color": color}


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


def _window_sample_count_ms(time_values_ms: np.ndarray, window_ms: float) -> int:
    if window_ms <= 0 or time_values_ms.size < 2:
        return 0
    dt_ms = float(np.median(np.diff(np.asarray(time_values_ms, dtype=float))))
    if not np.isfinite(dt_ms) or dt_ms <= 0:
        return 0
    return max(1, int(np.ceil(float(window_ms) / dt_ms)))


def _apply_right_edge_taper(df_in: pd.DataFrame, taper_ms: float) -> pd.DataFrame:
    taper_samples = _window_sample_count_ms(df_in["time"].to_numpy(float), float(taper_ms))
    if taper_samples <= 0:
        return df_in

    df_out = df_in.copy()
    amp = df_out["amp"].to_numpy(float)
    taper_samples = min(len(amp), taper_samples)
    if taper_samples <= 0:
        return df_out
    if taper_samples == 1:
        amp[-1] = 0.0
    else:
        ramp = np.linspace(0.0, np.pi, taper_samples)
        weights = 0.5 * (1.0 + np.cos(ramp))
        amp[-taper_samples:] = amp[-taper_samples:] * weights
    df_out["amp"] = amp
    return df_out


def process_signals(
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
    signal_window_on=False,
    signal_window_taper_ms=0.0,
    signal_window_padding_ms=0.0,
):
    if None in (raw_signals, selected, wavespeed) or not selected:
        raise ValueError("No selected signals to process.")

    processed, xf_list, yf_list, xff_list, yff_list = [], [], [], [], []
    peaks_for_plot = empty_peak_markers()
    avg_step_list_ms, notifications = [], []
    signal_window_on = bool(signal_window_on)
    signal_window_taper_ms = max(0.0, float(signal_window_taper_ms or 0.0))
    signal_window_padding_ms = max(0.0, float(signal_window_padding_ms or 0.0))

    w_Hz, h, amp_filtered = [None], [None], [None]

    def _approx_equal_all(vals):
        if len(vals) < 2:
            return True
        v0 = float(vals[0])
        return all(abs(float(v) - v0) <= 1e-6 * max(1.0, abs(v0)) for v in vals[1:])

    for idx, rs in enumerate(raw_signals):
        signal_meta = signal_assumptions[idx] if signal_assumptions and idx < len(signal_assumptions) else {
            "assumed_input": "Unknown",
            "default_integrations": 0,
            "time_unit": "ms",
            "time_unit_known": True,
        }
        df = ensure_time_ms_df(pd.DataFrame(rs).reset_index(drop=True), signal_meta)

        df = _preprocess_before_amplification(
            df,
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

        def _do_filter(df_in: pd.DataFrame, *, padding_ms_local: float = 0.0):
            amp = df_in["amp"].to_numpy(float)
            time_values = df_in["time"].to_numpy(float)
            fs = 1000.0 / (df_in["time"].iloc[1] - df_in["time"].iloc[0])
            xf, yf = get_spectrum(amp, 1 / fs, len(df_in))
            if filt_on:
                sos = butter_lowpass(f_lp, f_hp, fs, f_ord)
                if not isinstance(sos, str):
                    pad_samples = _window_sample_count_ms(time_values, float(padding_ms_local or 0.0))
                    amp_for_filter = np.pad(amp, (pad_samples, pad_samples), mode="constant") if pad_samples > 0 else amp
                    af = butter_lowpass_filter(amp_for_filter, f_lp, f_hp, fs, f_ord, fwd_bwd)
                    af = np.asarray(af, dtype=float)
                    if pad_samples > 0:
                        af = af[pad_samples : pad_samples + len(df_in)]
                    else:
                        af = af[: len(df_in)]
                    xff, yff = get_spectrum(af, 1 / fs, len(df_in))
                    w, H = sosfreqz(sos, worN=512)
                    w_Hz_local = [(fs * 0.5 / np.pi) * _ for _ in w]
                    H_mag = [abs(_) * (max(yf) if len(yf) else 1.0) for _ in H]
                    df_out = df_in.copy()
                    df_out["amp"] = af
                    return df_out, xf, yf, xff, yff, w_Hz_local, H_mag, af
            return df_in, xf, yf, [None], [None], [None], [None], [None]

        if filter_before_amp:
            df, xf, yf, xff, yff, w_Hz, h, amp_filtered = _do_filter(df)

        shift_ref = df.copy()
        ref_peak_time_ms, _ref_peak_warning = find_reference_peak_time(
            shift_ref["amp"],
            shift_ref["time"],
            pk_dist,
            pk_prom,
            pk_wmin,
            pk_wmax,
        )
        shift_name = selected[idx] if idx < len(selected) else f"trace {idx + 1}"
        shift_ref_amount, shift_warning = _shift_amount_ms(
            shift_ref,
            shift_on=shift_on,
            pk_dist=pk_dist,
            pk_prom=pk_prom,
            pk_wmin=pk_wmin,
            pk_wmax=pk_wmax,
        )
        if shift_warning:
            notifications.append(_notification("Shift warning", f"{shift_name}: {shift_warning}", color="yellow"))

        full_cutoff_ms = float(shift_ref["time"].max())
        raw_cutoff_ms = full_cutoff_ms
        if lim_t is not None:
            min_cutoff_ms = float(shift_ref["time"].iloc[1])
            requested_cutoff_ms = float(lim_t) + shift_ref_amount
            raw_cutoff_ms = min(full_cutoff_ms, max(min_cutoff_ms, requested_cutoff_ms))

        df["time"], df["amp"] = amplificate_signal(df["time"], df["amp"], a0)
        df = df[df["time"] <= raw_cutoff_ms]
        if len(df) < 2:
            raise ValueError("No data remains within the selected signal end.")

        if detrend_on and detrend_after_amp:
            df["amp"] = sp_detrend(df["amp"].to_numpy(), type="linear")
        m = max(abs(df["amp"])) or 1.0
        df["amp"] = df["amp"] / m
        if signal_window_on and signal_window_taper_ms > 0:
            df = _apply_right_edge_taper(df, signal_window_taper_ms)

        if not filter_before_amp:
            filter_padding_ms = signal_window_padding_ms if signal_window_on else 0.0
            df, xf, yf, xff, yff, w_Hz, h, amp_filtered = _do_filter(
                df,
                padding_ms_local=filter_padding_ms,
            )

        dt_avg_ms = float(df["time"].iloc[1] - df["time"].iloc[0])
        avg_step_list_ms.append(abs(dt_avg_ms))

        if to_length:
            df["time"] = df["time"] * wavespeed / 2000.0
            shift0 = shift_ref_amount * wavespeed / 2000.0
        else:
            shift0 = shift_ref_amount

        df["time"] = pd.Series(df["time"]) - shift0
        ref_x = None
        if ref_peak_time_ms is not None:
            ref_x = (ref_peak_time_ms * wavespeed / 2000.0) if to_length else ref_peak_time_ms
            ref_x = ref_x - shift0
        if ref_x is not None and len(df) > 0:
            time_values = df["time"].to_numpy(float)
            if time_values.size:
                ref_idx = int(np.argmin(np.abs(time_values - ref_x)))
                m = abs(float(df["amp"].iloc[ref_idx])) or 1.0
                df["amp"] = df["amp"] / m
        else:
            p_pos, _ = find_peaks(df["amp"], distance=pk_dist, prominence=pk_prom, width=(pk_wmin, pk_wmax))
            if p_pos.size:
                m = abs(df["amp"].iloc[p_pos[0]]) or 1.0
                df["amp"] = df["amp"] / m

        if idx == 0:
            peaks_for_plot = build_peak_markers(df["time"], df["amp"], pk_dist, pk_prom, pk_wmin, pk_wmax)

        processed.append(df.to_dict())
        xf_list.append(xf)
        yf_list.append(yf)
        xff_list.append(xff)
        yff_list.append(yff)

    if not processed:
        raise ValueError("No valid traces to process.")

    x_min, x_max = float(pd.DataFrame(processed[0])["time"].min()), float(pd.DataFrame(processed[0])["time"].max())
    av_x, av_y = [], []
    if mov_win > 0 and len(processed) > 1:
        if not _approx_equal_all(avg_step_list_ms):
            notifications.append(_notification("Averaging warning", "Loaded signals have different sampling rates. The average trace may be inaccurate.", color="yellow"))
        ref_dt_ms = float(np.median(avg_step_list_ms)) if avg_step_list_ms else 0.0
        if ref_dt_ms <= 0:
            raise ValueError("Averaging window size could not be converted from milliseconds to samples.")
        mov_win_pts = max(1, int(round(float(mov_win) / ref_dt_ms)))
        all_df = pd.concat([pd.DataFrame(d) for d in processed]).reset_index(drop=True)
        all_df["time"] = all_df["time"].round(9)
        all_df = all_df.sort_values("time")
        av = pd.DataFrame({
            "time": all_df["time"].rolling(mov_win_pts).median(),
            "amp": all_df["amp"].rolling(mov_win_pts).mean(),
        }).dropna().drop_duplicates().drop_duplicates(subset=["time"])
        av_x = av["time"].to_list()
        av_y = av["amp"].to_numpy()
        if spline_smooth > 0 and len(av_x) > 3:
            tck = splrep(av_x, av_y, s=spline_smooth / 1000.0)
            av_y = BSpline(*tck)(av_x)
        x_min, x_max = av_x[0], av_x[-1]
        peaks_for_plot = build_peak_markers(av_x, av_y, pk_dist, pk_prom, pk_wmin, pk_wmax)

    return {
        "signal": [processed, x_min, x_max],
        "peaks": peaks_for_plot,
        "spectrum": [xf_list, yf_list, xff_list, yff_list, w_Hz, h, amp_filtered],
        "av_signal": [av_x, av_y],
        "notifications": notifications,
    }
