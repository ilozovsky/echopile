"""Helpers for reading and writing the SNC session format."""

from __future__ import annotations

import io
import json
from typing import Optional, Union

import numpy as np
import pandas as pd

from .settings_defaults import SNC_UI_SETTING_KEYS, build_snc_ui_settings_list, get_snc_ui_defaults_list, get_snc_ui_defaults_map

_LEGACY_OPTIONAL_SNC_KEYS = {
    "main_plot_width_pct",
    "main_plot_height_px",
    "downsample_factor",
    "downsample_aa",
    "generic_marker_ms",
    "generic_marker_label",
    "signal_window_on",
    "signal_window_taper_ms",
    "signal_window_padding_ms",
    "cmap_SLT_log",
    "cmap_SLT_log_floor_exp",
    "superlet_coi_mask_on",
    "superlet_attributes_on",
    "superlet_attribute_placement",
    "superlet_attribute_keys",
    "superlet_attr_normalize",
    "superlet_attr_freq_reduce",
    "superlet_attr_x_reduce",
    "superlet_attr_x_window_ms",
    "superlet_attr_freq_min_hz",
    "superlet_attr_freq_max_hz",
    "superlet_attr_show_band_guides",
    "superlet_attr_show_source_badge",
    "superlet_attr_phase_freq_hz",
    "display_subplots_horizontally",
    "y_axis_exponent_format",
}
_LEGACY_EXTRA_SNC_KEYS = {
    "zero_padding",
}


def coerce_snc_header_value(raw_value: str) -> Union[None, bool, float, str]:
    if raw_value == "None":
        return None
    if raw_value == "True":
        return True
    if raw_value == "False":
        return False
    if raw_value and raw_value[0] in "[{":
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            pass
    try:
        return float(raw_value)
    except ValueError:
        return raw_value


def default_snc_signal_meta() -> dict:
    return {
        "assumed_input": "Unknown",
        "default_integrations": 0,
        "time_unit": "ms",
        "time_unit_known": True,
    }


def normalize_snc_signal_meta(meta: Optional[dict]) -> dict:
    out = default_snc_signal_meta()
    if isinstance(meta, dict):
        for key in ("assumed_input", "default_integrations", "time_unit", "time_unit_known"):
            if key in meta:
                out[key] = meta[key]

    out["assumed_input"] = str(out.get("assumed_input", "Unknown") or "Unknown")
    out["default_integrations"] = int(out.get("default_integrations", 0) or 0)
    out["time_unit"] = str(out.get("time_unit", "ms") or "ms")
    out["time_unit_known"] = bool(out.get("time_unit_known", True))
    return out


def _is_compatible_legacy_snc_header(
    missing_keys: set[str],
    extra_keys: set[str],
) -> bool:
    return missing_keys.issubset(_LEGACY_OPTIONAL_SNC_KEYS) and extra_keys.issubset(_LEGACY_EXTRA_SNC_KEYS)


def parse_snc_text(text: str) -> tuple[list[dict], list[str], list, list[dict]]:
    lines = text.splitlines()
    try:
        raw_sep = next(i for i, line in enumerate(lines) if line.strip() == "****** raw signals ******")
    except StopIteration as exc:
        raise ValueError("SNC file does not contain raw signal table") from exc

    header_lines = lines[:raw_sep]
    settings_map: dict[str, Union[None, bool, float, str]] = {}
    recognized_settings_in_order: list[Union[None, bool, float, str]] = []
    signal_metadata_map: dict[str, dict] = {}
    for raw in header_lines:
        if ": " not in raw:
            continue

        key, part = raw.split(": ", 1)
        if key == "signal_metadata_json":
            try:
                parsed_meta = json.loads(part)
            except json.JSONDecodeError as exc:
                raise ValueError("SNC signal metadata block could not be parsed") from exc
            if isinstance(parsed_meta, dict):
                signal_metadata_map = parsed_meta
            continue

        coerced = coerce_snc_header_value(part)
        settings_map[key] = coerced
        if key in SNC_UI_SETTING_KEYS:
            recognized_settings_in_order.append(coerced)

    if settings_map:
        missing_keys = {key for key in SNC_UI_SETTING_KEYS if key not in settings_map}
        extra_keys = {key for key in settings_map if key not in SNC_UI_SETTING_KEYS}

        # Only a small known legacy header variant is normalized silently. Anything
        # else is treated as incomplete so the UI can warn instead of silently
        # mixing file data with defaults.
        if missing_keys and not _is_compatible_legacy_snc_header(missing_keys, extra_keys):
            settings = recognized_settings_in_order
        else:
            settings = build_snc_ui_settings_list(settings_map)
    else:
        settings = []

    table_text = "\n".join(lines[raw_sep + 1:]).strip()
    if not table_text:
        raise ValueError("SNC file does not contain raw signal table")

    header_line = lines[raw_sep + 1] if raw_sep + 1 < len(lines) else ""
    if "\t" in header_line:
        df_all = pd.read_csv(io.StringIO(table_text), sep="\t")
    else:
        df_all = pd.read_csv(io.StringIO(table_text), sep=r"\s+")
    pairs = [df_all.columns[i : i + 2] for i in range(0, len(df_all.columns), 2)]

    out_list: list[dict] = []
    names: list[str] = []
    meta_list: list[dict] = []
    for pair in pairs:
        label = pair[0][2:]
        names.append(label)
        out_list.append(pd.DataFrame(df_all.loc[:, pair]).to_dict())
        meta = normalize_snc_signal_meta(signal_metadata_map.get(label))
        meta["time_unit"] = "ms"
        meta["time_unit_known"] = True
        meta_list.append(meta)

    return out_list, names, settings, meta_list


def serialize_snc_text(
    raw_signals,
    selected_filenames,
    settings_map: dict,
    signal_assumptions,
) -> str:
    lines = []
    for key in SNC_UI_SETTING_KEYS:
        value = settings_map.get(key)
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            rendered = value
        lines.append(f"{key}: {rendered}")

    signal_metadata = {}
    for item in signal_assumptions or []:
        name = item.get("name") or item.get("display_name")
        if not name:
            continue
        meta = {
            key: value
            for key, value in item.items()
            if key not in {"name", "display_name"}
        }
        meta["time_unit"] = "ms"
        meta["time_unit_known"] = True
        signal_metadata[str(name)] = meta
    lines.append(
        "signal_metadata_json: "
        + json.dumps(signal_metadata, ensure_ascii=False, separators=(",", ":"))
    )
    lines.append("****** raw signals ******")

    df_out = pd.DataFrame()
    for i, rs in enumerate(raw_signals):
        df = pd.DataFrame(rs)
        if {"time", "amp"}.issubset(df.columns):
            df = df.loc[:, ["time", "amp"]]
        df.columns = [f"t_{selected_filenames[i]}", f"s_{selected_filenames[i]}"]
        df_out = pd.concat([df_out.reset_index(drop=True), df.reset_index(drop=True)], axis=1)

    return "\n".join(lines) + "\n" + df_out.to_csv(sep="\t", index=False)


def normalize_snc_settings_for_ui(settings: list | None) -> list:
    defaults = get_snc_ui_defaults_list()
    defaults_map = get_snc_ui_defaults_map()

    normalized = list(settings) if settings else list(defaults)
    if len(normalized) < len(SNC_UI_SETTING_KEYS):
        normalized = list(normalized) + defaults[len(normalized):]
    elif len(normalized) > len(SNC_UI_SETTING_KEYS):
        normalized = list(normalized[: len(SNC_UI_SETTING_KEYS)])

    moving_window_idx = SNC_UI_SETTING_KEYS.index("moving_window_size")
    moving_window_value = normalized[moving_window_idx]
    if moving_window_value is None or float(moving_window_value) < 0 or float(moving_window_value) > 3.0:
        normalized[moving_window_idx] = defaults_map["moving_window_size"]

    downsample_factor_idx = SNC_UI_SETTING_KEYS.index("downsample_factor")
    downsample_factor_value = normalized[downsample_factor_idx]
    if downsample_factor_value is None or float(downsample_factor_value) < 1:
        normalized[downsample_factor_idx] = defaults_map["downsample_factor"]

    slt_mode_idx = SNC_UI_SETTING_KEYS.index("slt_mode")
    if normalized[slt_mode_idx] not in {"fixed", "adaptive"}:
        normalized[slt_mode_idx] = defaults_map["slt_mode"]

    slt_set_mode_idx = SNC_UI_SETTING_KEYS.index("superlet_set_mode")
    if normalized[slt_set_mode_idx] not in {"multiplicative", "additive"}:
        normalized[slt_set_mode_idx] = defaults_map["superlet_set_mode"]

    order_slt_idx = SNC_UI_SETTING_KEYS.index("order_slt")
    order_slt_value = normalized[order_slt_idx]
    if order_slt_value is None or float(order_slt_value) < 1:
        normalized[order_slt_idx] = defaults_map["order_slt"]

    for key in ("signal_window_taper_ms", "signal_window_padding_ms"):
        idx = SNC_UI_SETTING_KEYS.index(key)
        value = normalized[idx]
        if value is None or float(value) < 0:
            normalized[idx] = defaults_map[key]

    generic_marker_idx = SNC_UI_SETTING_KEYS.index("generic_marker_ms")
    generic_marker_value = normalized[generic_marker_idx]
    if generic_marker_value is not None and float(generic_marker_value) < 0:
        normalized[generic_marker_idx] = defaults_map["generic_marker_ms"]

    log_floor_idx = SNC_UI_SETTING_KEYS.index("cmap_SLT_log_floor_exp")
    log_floor_value = normalized[log_floor_idx]
    if log_floor_value is None or not np.isfinite(float(log_floor_value)):
        normalized[log_floor_idx] = defaults_map["cmap_SLT_log_floor_exp"]

    attr_placement_idx = SNC_UI_SETTING_KEYS.index("superlet_attribute_placement")
    if normalized[attr_placement_idx] not in {"signal", "below_slt"}:
        normalized[attr_placement_idx] = defaults_map["superlet_attribute_placement"]

    for key in ("superlet_attr_freq_reduce", "superlet_attr_x_reduce"):
        idx = SNC_UI_SETTING_KEYS.index(key)
        if normalized[idx] not in {"mean", "median"}:
            normalized[idx] = defaults_map[key]

    for key in ("superlet_attr_zero_baseline", "display_subplots_horizontally"):
        idx = SNC_UI_SETTING_KEYS.index(key)
        normalized[idx] = bool(normalized[idx])

    y_axis_exponent_idx = SNC_UI_SETTING_KEYS.index("y_axis_exponent_format")
    if normalized[y_axis_exponent_idx] not in {"none", "E", "power", "B", "SI"}:
        normalized[y_axis_exponent_idx] = defaults_map["y_axis_exponent_format"]

    attr_keys_idx = SNC_UI_SETTING_KEYS.index("superlet_attribute_keys")
    attr_keys_value = normalized[attr_keys_idx]
    if isinstance(attr_keys_value, str):
        attr_keys_value = [attr_keys_value]
    if not isinstance(attr_keys_value, list):
        attr_keys_value = list(defaults_map["superlet_attribute_keys"])
    normalized[attr_keys_idx] = [str(item) for item in attr_keys_value if item not in (None, "")]

    for key in ("superlet_attr_x_window_ms", "superlet_attr_freq_min_hz", "superlet_attr_freq_max_hz", "superlet_attr_phase_freq_hz"):
        idx = SNC_UI_SETTING_KEYS.index(key)
        value = normalized[idx]
        if value is None or float(value) < 0:
            normalized[idx] = defaults_map[key]

    for key in ("superlet_attr_show_band_guides", "superlet_attr_show_source_badge"):
        idx = SNC_UI_SETTING_KEYS.index(key)
        normalized[idx] = bool(normalized[idx])

    return normalized
