import base64
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from echopile.app import build_app  # noqa: E402
from echopile.app.callbacks import handlers as callbacks  # noqa: E402
from echopile.core import io_readers  # noqa: E402
from echopile.core import signal_processing  # noqa: E402
from echopile.core.processing_pipeline import process_signals  # noqa: E402
from echopile.core.settings_defaults import SNC_UI_SETTING_KEYS, build_snc_ui_settings_list  # noqa: E402
from echopile.core.snc_io import coerce_snc_header_value  # noqa: E402


FIXTURE = ROOT / "examples" / "Vel (Z_component) (big probe)_F_2000.snc"


def make_data_uri_from_path(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:text/plain;base64,{encoded}"


def load_fixture_settings() -> list:
    settings_map = {}
    for raw in FIXTURE.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "****** raw signals ******":
            break
        if ": " not in raw:
            continue
        key, part = raw.split(": ", 1)
        if key == "signal_metadata_json":
            continue
        settings_map[key] = coerce_snc_header_value(part)
    return build_snc_ui_settings_list(settings_map)


def build_processing_summary():
    content = make_data_uri_from_path(FIXTURE)
    df_list, loaded_names, _, _settings, meta_list = io_readers.parse_contents(content, FIXTURE.name, 1)
    settings_by_key = dict(zip(SNC_UI_SETTING_KEYS, load_fixture_settings()))
    raw_signals = []
    for item in df_list:
        df = pd.DataFrame(item).rename(
            columns=lambda c: "time" if c.startswith("t_") else ("amp" if c.startswith("s_") else c)
        )
        raw_signals.append(df.to_dict())

    result = process_signals(
        raw_signals,
        loaded_names,
        meta_list,
        settings_by_key["a0"],
        settings_by_key["lim_time_max"],
        settings_by_key["detrend_on"],
        settings_by_key["detrend_tick"],
        settings_by_key["shift_on"],
        settings_by_key["flip_polarity"],
        settings_by_key["peak_distance"],
        settings_by_key["peak_width_min"],
        settings_by_key["peak_width_max"],
        settings_by_key["peak_prominence_min"],
        settings_by_key["length_on"],
        settings_by_key["wavespeed"],
        settings_by_key["integration_mode"],
        settings_by_key["integration_method"],
        settings_by_key["integration_low_frequency_hz"],
        settings_by_key["integration_zero_baseline"],
        settings_by_key["filter_switch"],
        settings_by_key["filter_tick"],
        settings_by_key["forward_backward_filter"],
        settings_by_key["filter_cutoff_lp"],
        settings_by_key["filter_cutoff_hp"],
        settings_by_key["filter_order"],
        settings_by_key["moving_window_size"],
        settings_by_key["spline_smoothing"],
        settings_by_key["downsample_factor"],
        settings_by_key["downsample_aa"],
    )

    signal = result["signal"]
    spectrum = result["spectrum"]
    peaks = result["peaks"]
    av_signal = result["av_signal"]
    return {
        "loaded_names": loaded_names,
        "settings_subset": {
            "a0": settings_by_key["a0"],
            "lim_time_max": settings_by_key["lim_time_max"],
            "length_on": settings_by_key["length_on"],
            "wavespeed": settings_by_key["wavespeed"],
            "integration_mode": settings_by_key["integration_mode"],
            "integration_method": settings_by_key["integration_method"],
        },
        "processed_count": len(signal[0]),
        "x_min": signal[1],
        "x_max": signal[2],
        "first_trace_len": len(signal[0][0]["time"]),
        "first_trace_time_head": [round(float(v), 9) for v in list(signal[0][0]["time"].values())[:5]],
        "first_trace_amp_head": [round(float(v), 9) for v in list(signal[0][0]["amp"].values())[:5]],
        "first_trace_amp_tail": [round(float(v), 9) for v in list(signal[0][0]["amp"].values())[-5:]],
        "peaks_pos_x": [round(float(v), 9) for v in peaks[0][0]],
        "peaks_neg_x": [round(float(v), 9) for v in peaks[1][0]],
        "spectrum_len": len(spectrum[0][0]),
        "spectrum_freq_head": [round(float(v), 9) for v in spectrum[0][0][:5]],
        "spectrum_amp_head": [round(float(v), 9) for v in spectrum[1][0][:5]],
        "av_signal_len": len(av_signal[0]),
        "notifications": result["notifications"],
    }


class RefactorRegressionTests(unittest.TestCase):
    def test_fixture_snc_parses_expected_settings_and_metadata(self):
        content = make_data_uri_from_path(FIXTURE)
        out_list, loaded_names, style, settings, meta_list = io_readers.parse_contents(content, FIXTURE.name, 1)
        settings = load_fixture_settings()

        self.assertEqual(style, {"display": "block"})
        self.assertEqual(loaded_names, ["Vel (Z_component) (big probe)_F_2000"])
        self.assertEqual(len(settings), len(SNC_UI_SETTING_KEYS))
        self.assertEqual(meta_list[0]["time_unit"], "ms")
        self.assertTrue(meta_list[0]["time_unit_known"])
        self.assertEqual(list(out_list[0].keys()), [
            "t_Vel (Z_component) (big probe)_F_2000",
            "s_Vel (Z_component) (big probe)_F_2000",
        ])

    def test_fixture_processing_matches_golden_baseline(self):
        summary = build_processing_summary()

        self.assertEqual(summary["loaded_names"], ["Vel (Z_component) (big probe)_F_2000"])
        self.assertEqual(summary["settings_subset"], {
            "a0": 0.19,
            "lim_time_max": 7.75,
            "length_on": True,
            "wavespeed": 4000.0,
            "integration_mode": "Auto",
            "integration_method": "regularized_fd",
        })
        self.assertEqual(summary["processed_count"], 1)
        self.assertAlmostEqual(summary["x_min"], -1.200000000000003)
        self.assertAlmostEqual(summary["x_max"], 15.480000000000796)
        self.assertEqual(summary["first_trace_len"], 835)
        self.assertEqual(summary["first_trace_time_head"], [-1.2, -1.18, -1.16, -1.14, -1.12])
        self.assertEqual(summary["first_trace_amp_head"], [0.0, -0.0, 0.0, -0.0, 0.0])
        self.assertEqual(summary["first_trace_amp_tail"], [-0.085068807, -0.087787523, -0.090363638, -0.092405719, -0.093570248])
        self.assertEqual(summary["peaks_pos_x"], [0.0, 5.86, 11.72])
        self.assertEqual(summary["peaks_neg_x"], [2.16, 7.68])
        self.assertEqual(summary["spectrum_len"], 751)
        self.assertEqual(summary["spectrum_freq_head"], [0.0, 66.622251832, 133.244503664, 199.866755496, 266.489007328])
        self.assertEqual(summary["spectrum_amp_head"], [0.0043593, 0.017241045, 0.012687363, 0.010731792, 0.01913872])
        self.assertEqual(summary["av_signal_len"], 0)
        self.assertEqual(summary["notifications"], [])

    def test_callback_processing_uses_pipeline_result_shape(self):
        summary_from_callback = callbacks.process_signal(
            *self._build_callback_args()
        )
        self.assertEqual(len(summary_from_callback), 5)
        self.assertEqual(summary_from_callback[-1], [])

    def test_build_app_import_path_still_works(self):
        app = build_app()
        app._setup_server()
        self.assertEqual(app.title, "echopile | Pile Integrity Analysis")
        self.assertEqual(getattr(app, "_echopile_profile"), "local")
        self.assertGreater(len(app.callback_map), 0)

    def _build_callback_args(self):
        content = make_data_uri_from_path(FIXTURE)
        df_list, loaded_names, _, _settings, meta_list = io_readers.parse_contents(content, FIXTURE.name, 1)
        settings_by_key = dict(zip(SNC_UI_SETTING_KEYS, load_fixture_settings()))
        raw_signals = []
        for item in df_list:
            df = pd.DataFrame(item).rename(
                columns=lambda c: "time" if c.startswith("t_") else ("amp" if c.startswith("s_") else c)
            )
            raw_signals.append(df.to_dict())

        return (
            raw_signals,
            loaded_names,
            meta_list,
            settings_by_key["a0"],
            settings_by_key["lim_time_max"],
            settings_by_key["detrend_on"],
            settings_by_key["detrend_tick"],
            settings_by_key["shift_on"],
            settings_by_key["flip_polarity"],
            settings_by_key["peak_distance"],
            settings_by_key["peak_width_min"],
            settings_by_key["peak_width_max"],
            settings_by_key["peak_prominence_min"],
            settings_by_key["length_on"],
            settings_by_key["wavespeed"],
            settings_by_key["integration_mode"],
            settings_by_key["integration_method"],
            settings_by_key["integration_low_frequency_hz"],
            settings_by_key["integration_zero_baseline"],
            settings_by_key["filter_switch"],
            settings_by_key["filter_tick"],
            settings_by_key["forward_backward_filter"],
            settings_by_key["filter_cutoff_lp"],
            settings_by_key["filter_cutoff_hp"],
            settings_by_key["filter_order"],
            settings_by_key["moving_window_size"],
            settings_by_key["spline_smoothing"],
            settings_by_key["downsample_factor"],
            settings_by_key["downsample_aa"],
        )


if __name__ == "__main__":
    unittest.main()
