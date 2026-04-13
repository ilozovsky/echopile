"""Single source of truth for saved UI setting defaults."""

from __future__ import annotations


SNC_UI_SETTING_KEYS = [
    "a0", "lim_time_max", "detrend_on", "detrend_tick",
    "shift_on", "flip_polarity", "peak_distance", "peak_width_min", "peak_width_max", "peak_prominence_min",
    "length_on", "wavespeed", "main_plot_width_pct", "main_plot_height_px", "downsample_factor", "downsample_aa",
    "filter_switch", "forward_backward_filter",
    "filter_cutoff_lp", "filter_cutoff_hp", "filter_order", "spectrum_autozoom_x",
    "moving_window_size", "spline_smoothing",
    "length_marker", "reflection", "generic_marker_ms", "generic_marker_label", "show_markers", "simplify_plot", "reverse_axis",
    "signal_window_on", "signal_window_taper_ms", "signal_window_padding_ms",
    "superlet_plot", "slt_mode", "superlet_set_mode", "superlet_phase_combination", "superlet_coi_mask_on", "freq_SLT_min", "freq_SLT_max", "freq_SLT_no",
    "c_1", "k_sd", "support_sd", "order_slt", "order_min", "order_max", "SLT_output",
    "cmap_SLT", "cmap_SLT_min", "cmap_SLT_max", "cmap_SLT_log", "cmap_SLT_log_floor_exp",
    "superlet_attributes_on", "superlet_attribute_placement", "superlet_attribute_keys",
    "superlet_attr_normalize", "superlet_attr_zero_baseline", "superlet_attr_freq_reduce", "superlet_attr_x_reduce",
    "superlet_attr_x_window_ms", "superlet_attr_freq_min_hz", "superlet_attr_freq_max_hz", "superlet_attr_show_band_guides", "superlet_attr_show_source_badge", "superlet_attr_phase_freq_hz",
    "filter_draw",
    "show_legend", "filter_tick", "display_subplots_horizontally", "y_axis_exponent_format", "time_unit_override", "integration_mode",
    "integration_method", "integration_low_frequency_hz", "integration_zero_baseline",
]


SNC_UI_SETTING_DEFAULTS = {
    "a0": 0.0,
    "lim_time_max": None,
    "detrend_on": False,
    "detrend_tick": False,
    "shift_on": True,
    "flip_polarity": False,
    "peak_distance": 10.0,
    "peak_width_min": 1.0,
    "peak_width_max": None,
    "peak_prominence_min": 0.15,
    "length_on": True,
    "wavespeed": 4000.0,
    "main_plot_width_pct": 100.0,
    "main_plot_height_px": 250.0,
    "downsample_factor": 1.0,
    "downsample_aa": True,
    "filter_switch": False,
    "forward_backward_filter": True,
    "filter_cutoff_lp": None,
    "filter_cutoff_hp": 20.0,
    "filter_order": 20.0,
    "spectrum_autozoom_x": True,
    "moving_window_size": 0.4,
    "spline_smoothing": 50.0,
    "length_marker": None,
    "reflection": None,
    "generic_marker_ms": None,
    "generic_marker_label": "",
    "show_markers": True,
    "simplify_plot": False,
    "reverse_axis": False,
    "signal_window_on": False,
    "signal_window_taper_ms": 0.5,
    "signal_window_padding_ms": 0.25,
    "superlet_plot": True,
    "slt_mode": "adaptive",
    "superlet_set_mode": "multiplicative",
    "superlet_phase_combination": "circular",
    "superlet_coi_mask_on": False,
    "freq_SLT_min": 100.0,
    "freq_SLT_max": 20000.0,
    "freq_SLT_no": 100.0,
    "c_1": 2.0,
    "k_sd": 5.0,
    "support_sd": 8.0,
    "order_slt": 4.0,
    "order_min": 1.0,
    "order_max": 4.0,
    "SLT_output": "Re",
    "cmap_SLT": "Default",
    "cmap_SLT_min": None,
    "cmap_SLT_max": None,
    "cmap_SLT_log": False,
    "cmap_SLT_log_floor_exp": -6.0,
    "superlet_attributes_on": False,
    "superlet_attribute_placement": "below_slt",
    "superlet_attribute_keys": ["power"],
    "superlet_attr_normalize": True,
    "superlet_attr_zero_baseline": True,
    "superlet_attr_freq_reduce": "mean",
    "superlet_attr_x_reduce": "mean",
    "superlet_attr_x_window_ms": 0.0,
    "superlet_attr_freq_min_hz": 100.0,
    "superlet_attr_freq_max_hz": 5000.0,
    "superlet_attr_show_band_guides": False,
    "superlet_attr_show_source_badge": True,
    "superlet_attr_phase_freq_hz": 1000.0,
    "filter_draw": True,
    "show_legend": True,
    "filter_tick": True,
    "display_subplots_horizontally": False,
    "y_axis_exponent_format": "SI",
    "time_unit_override": "s",
    "integration_mode": "Auto",
    "integration_method": "regularized_fd",
    "integration_low_frequency_hz": 10.0,
    "integration_zero_baseline": True,
}


def get_snc_ui_defaults_map() -> dict:
    return dict(SNC_UI_SETTING_DEFAULTS)


def get_snc_ui_defaults_list() -> list:
    return [SNC_UI_SETTING_DEFAULTS[key] for key in SNC_UI_SETTING_KEYS]


def build_snc_ui_settings_list(settings_map: dict | None = None) -> list:
    settings_map = settings_map or {}
    return [settings_map.get(key, SNC_UI_SETTING_DEFAULTS[key]) for key in SNC_UI_SETTING_KEYS]
