import base64
import sys
import unittest
from pathlib import Path

import numpy as np
from dash import no_update

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from echopile.core import processing_pipeline  # noqa: E402
from echopile.core import slt_analysis  # noqa: E402
from echopile.core import io_readers  # noqa: E402
from echopile.app.callbacks import handlers as callbacks  # noqa: E402

legacy_callbacks = callbacks


def make_data_uri(text: str) -> str:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"data:text/plain;base64,{encoded}"


def layout_axis(fig, axis_ref: str, axis_letter: str):
    axis_ref = str(axis_ref or axis_letter)
    axis_name = f"{axis_letter}axis" if axis_ref == axis_letter else f"{axis_letter}axis{axis_ref[1:]}"
    return getattr(fig.layout, axis_name)


class SncRoundTripTests(unittest.TestCase):
    def _build_session(self):
        names = ["ZBL1[1 (processed)]", "Trace 1"]
        raw_signals = [
            {"time": {0: 0.0, 1: 1.0, 2: 2.0}, "amp": {0: 1.5, 1: 2.5, 2: 3.5}},
            {"time": {0: 0.0, 1: 2.0, 2: 4.0}, "amp": {0: 4.5, 1: 5.5, 2: 6.5}},
        ]
        signal_assumptions = [
            {
                "name": names[0],
                "display_name": names[0],
                "assumed_input": "Acceleration",
                "default_integrations": 1,
                "time_unit": "ms",
                "time_unit_known": True,
            },
            {
                "name": names[1],
                "display_name": names[1],
                "assumed_input": "Velocity",
                "default_integrations": 0,
                "time_unit": "us",
                "time_unit_known": False,
            },
        ]
        download = callbacks.download_file(
            1,
            raw_signals,
            names,
            a0=101,
            lim_time_max=102,
            detrend_on=True,
            detrend_tick=False,
            shift_on=True,
            flip_polarity=False,
            peak_distance=107,
            peak_width_min=108,
            peak_width_max=109,
            peak_prominence_min=110,
            length_on=True,
            wavespeed=112,
            main_plot_width_pct=113,
            main_plot_height_px=114,
            downsample_factor=1.0,
            downsample_aa=True,
            filter_switch=False,
            forward_backward_filter=True,
            filter_cutoff_lp=119,
            filter_cutoff_hp=120,
            filter_order=121,
            spectrum_autozoom_x=True,
            moving_window_size=0.5,
            spline_smoothing=10.0,
            length_marker=124,
            reflection=125,
            generic_marker_ms=12.5,
            generic_marker_label="defect",
            show_markers=True,
            simplify_plot=False,
            reverse_axis=False,
            signal_window_on=True,
            signal_window_taper_ms=0.75,
            signal_window_padding_ms=0.5,
            time_unit_override="ms",
            integration_mode="x2",
            integration_method="regularized_fd",
            integration_low_frequency_hz=10.0,
            integration_zero_baseline=True,
            signal_assumptions=signal_assumptions,
            superlet_plot=True,
            slt_mode="adaptive",
            superlet_set_mode="multiplicative",
            superlet_phase_combination="circular",
            superlet_coi_mask_on=True,
            freq_SLT_min=131,
            freq_SLT_max=132,
            freq_SLT_no=133,
            c_1=2.0,
            k_sd=5.0,
            support_sd=8.0,
            order_slt=4.0,
            order_min=1.0,
            order_max=5.0,
            SLT_output="Arg",
            cmap_SLT="Cividis",
            cmap_SLT_min=137,
            cmap_SLT_max=138,
            cmap_SLT_log=True,
            cmap_SLT_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["power", "phase"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="median",
            superlet_attr_x_window_ms=1.25,
            superlet_attr_freq_min_hz=250.0,
            superlet_attr_freq_max_hz=1500.0,
            superlet_attr_show_band_guides=True,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=900.0,
            filter_draw=True,
            show_legend=False,
            filter_tick=True,
            display_subplots_horizontally=False,
            y_axis_exponent_format="power",
        )
        return names, make_data_uri(download["content"])

    def test_new_snc_round_trip_preserves_settings_names_and_metadata(self):
        names, content = self._build_session()

        out_list, loaded_names, _, settings, meta_list = io_readers.parse_contents(content, "session.snc", 1)
        self.assertEqual(loaded_names, names)
        self.assertEqual(list(out_list[0].keys()), [f"t_{names[0]}", f"s_{names[0]}"])
        settings_by_key = dict(zip(io_readers.SNC_UI_SETTING_KEYS, settings))
        self.assertEqual(settings_by_key["time_unit_override"], "ms")
        self.assertEqual(settings_by_key["integration_mode"], "x2")
        self.assertEqual(settings_by_key["integration_method"], "regularized_fd")
        self.assertEqual(settings_by_key["integration_low_frequency_hz"], 10.0)
        self.assertTrue(settings_by_key["integration_zero_baseline"])
        self.assertTrue(settings_by_key["signal_window_on"])
        self.assertEqual(settings_by_key["signal_window_taper_ms"], 0.75)
        self.assertEqual(settings_by_key["signal_window_padding_ms"], 0.5)
        self.assertEqual(settings_by_key["generic_marker_ms"], 12.5)
        self.assertEqual(settings_by_key["generic_marker_label"], "defect")
        self.assertTrue(settings_by_key["cmap_SLT_log"])
        self.assertEqual(settings_by_key["cmap_SLT_log_floor_exp"], -6.0)
        self.assertTrue(settings_by_key["superlet_coi_mask_on"])
        self.assertTrue(settings_by_key["superlet_attributes_on"])
        self.assertEqual(settings_by_key["superlet_attribute_placement"], "below_slt")
        self.assertEqual(settings_by_key["superlet_attribute_keys"], ["power", "phase"])
        self.assertTrue(settings_by_key["superlet_attr_normalize"])
        self.assertEqual(settings_by_key["superlet_attr_freq_reduce"], "mean")
        self.assertEqual(settings_by_key["superlet_attr_x_reduce"], "median")
        self.assertEqual(settings_by_key["superlet_attr_x_window_ms"], 1.25)
        self.assertEqual(settings_by_key["superlet_attr_freq_min_hz"], 250.0)
        self.assertEqual(settings_by_key["superlet_attr_freq_max_hz"], 1500.0)
        self.assertTrue(settings_by_key["superlet_attr_show_band_guides"])
        self.assertTrue(settings_by_key["superlet_attr_show_source_badge"])
        self.assertEqual(settings_by_key["superlet_attr_phase_freq_hz"], 900.0)
        self.assertFalse(settings_by_key["display_subplots_horizontally"])
        self.assertEqual(settings_by_key["y_axis_exponent_format"], "power")
        self.assertEqual(meta_list[0]["assumed_input"], "Acceleration")
        self.assertEqual(meta_list[0]["default_integrations"], 1)
        self.assertEqual(meta_list[1]["assumed_input"], "Velocity")
        self.assertTrue(all(item["time_unit"] == "ms" for item in meta_list))
        self.assertTrue(all(item["time_unit_known"] is True for item in meta_list))

        loaded_settings = callbacks.load_settings([content], None, ["session.snc"], [0])
        self.assertEqual(list(loaded_settings[:-1]), settings)
        self.assertEqual(loaded_settings[-1], [])

        stored = callbacks.store_raw_signals_selected_filenames(
            [content],
            names,
            "s",
            ["session.snc"],
            [0],
        )
        assumptions = stored[3]
        self.assertTrue(all(item["time_unit"] == "ms" for item in assumptions))
        self.assertTrue(all(item["time_unit_known"] is True for item in assumptions))
        time_unit_style = callbacks.update_integration_assumptions(assumptions, "Auto")[2]
        self.assertEqual(time_unit_style.get("display"), "none")

    def test_old_snc_header_without_time_unit_override_warns_as_incomplete(self):
        old_text = "\n".join(
            [
                "a0: 2.0",
                "lim_time_max: 100.0",
                "normalize_on: True",
                "detrend_on: False",
                "detrend_tick: True",
                "shift_on: False",
                "peak_distance: 10.0",
                "peak_width_min: 1.0",
                "peak_width_max: 20.0",
                "peak_prominence_min: 0.5",
                "length_on: False",
                "wavespeed: 3900.0",
                "filter_switch: True",
                "forward_backward_filter: True",
                "zero_padding: False",
                "filter_cutoff_lp: 5000.0",
                "filter_cutoff_hp: None",
                "filter_order: 4.0",
                "moving_window_size: 3.0",
                "spline_smoothing: 0.0",
                "length_marker: 12.0",
                "reflection: 1.0",
                "show_markers: True",
                "reverse_axis: False",
                "integration_mode: Auto",
                "superlet_plot: True",
                "freq_SLT_min: 1.0",
                "freq_SLT_max: 10.0",
                "freq_SLT_no: 20.0",
                "c_1: 3.0",
                "order_min: 1.0",
                "order_max: 5.0",
                "adaptive_SLT: False",
                "SLT_output: Power",
                "cmap_SLT: Viridis",
                "cmap_SLT_min: None",
                "cmap_SLT_max: None",
                "filter_draw: False",
                "show_legend: True",
                "filter_tick: True",
                "****** raw signals ******",
                "t_trace\ts_trace",
                "0\t1",
                "1\t2",
            ]
        )
        content = make_data_uri(old_text)
        settings = io_readers.parse_contents(content, "old.snc", 1)[3]
        self.assertLess(len(settings), len(io_readers.SNC_UI_SETTING_KEYS))

        loaded = callbacks.load_settings([content], None, ["old.snc"], [0])
        self.assertTrue(all(value is no_update for value in loaded[:-1]))
        self.assertTrue(loaded[-1])
        self.assertIn("incomplete", loaded[-1][0]["message"].lower())

    def test_truncated_snc_settings_are_ignored_with_warning(self):
        truncated_text = "\n".join(
            [
                "a0: 2.0",
                "lim_time_max: 100.0",
                "****** raw signals ******",
                "t_trace\ts_trace",
                "0\t1",
                "1\t2",
            ]
        )
        content = make_data_uri(truncated_text)
        settings = io_readers.parse_contents(content, "truncated.snc", 1)[3]
        self.assertEqual(settings, [2.0, 100.0])

        loaded = callbacks.load_settings([content], None, ["truncated.snc"], [0])
        self.assertTrue(all(value is no_update for value in loaded[:-1]))
        self.assertTrue(loaded[-1])
        self.assertIn("incomplete", loaded[-1][0]["message"].lower())

    def test_log_colorscale_and_average_only_control_callbacks(self):
        visible_style = callbacks.toggle_slt_log_colorscale_control("Power")
        self.assertNotEqual(visible_style.get("display"), "none")

        hidden_style = callbacks.toggle_slt_log_colorscale_control("Arg")
        self.assertEqual(hidden_style.get("display"), "none")

        averaging_style, smoothing_style = callbacks.toggle_average_only_controls(["trace"])
        self.assertEqual(averaging_style.get("display"), "none")
        self.assertEqual(smoothing_style.get("display"), "none")

        averaging_style, smoothing_style = callbacks.toggle_average_only_controls(["trace1", "trace2"])
        self.assertNotEqual(averaging_style.get("display"), "none")
        self.assertNotEqual(smoothing_style.get("display"), "none")

        taper_style, padding_style = callbacks.toggle_signal_window_controls(True)
        self.assertNotEqual(taper_style.get("display"), "none")
        self.assertNotEqual(padding_style.get("display"), "none")

        taper_style, padding_style = callbacks.toggle_signal_window_controls(False)
        self.assertEqual(taper_style.get("display"), "none")
        self.assertEqual(padding_style.get("display"), "none")

        log_floor_style = callbacks.toggle_slt_log_floor_row(True, "Power")
        self.assertNotEqual(log_floor_style.get("display"), "none")

        log_floor_style = callbacks.toggle_slt_log_floor_row(True, "Arg")
        self.assertEqual(log_floor_style.get("display"), "none")

    def test_signal_window_unit_conversion_callbacks(self):
        self.assertEqual(callbacks.store_signal_window_taper_ms(2.0, True, 4000.0), 1.0)
        self.assertEqual(callbacks.store_signal_window_padding_ms(3.5, False, 4000.0), 3.5)
        self.assertEqual(callbacks.store_superlet_attr_window_ms(4.0, False, 4000.0), 4.0)
        self.assertEqual(callbacks.store_superlet_attr_window_ms(None, False, 4000.0), 0.0)

    def test_right_edge_taper_and_temporary_padding_do_not_extend_final_signal(self):
        df = processing_pipeline._apply_right_edge_taper(
            processing_pipeline.pd.DataFrame(
                {
                    "time": np.arange(6, dtype=float),
                    "amp": np.ones(6, dtype=float),
                }
            ),
            taper_ms=3.0,
        )
        np.testing.assert_allclose(df["amp"].to_numpy()[:3], np.ones(3))
        self.assertLess(df["amp"].iloc[-2], 1.0)
        self.assertEqual(df["amp"].iloc[-1], 0.0)

        raw_signals = [
            {
                "time": {idx: float(idx) for idx in range(64)},
                "amp": {idx: float(np.sin(idx / 6.0)) for idx in range(64)},
            }
        ]
        result = processing_pipeline.process_signals(
            raw_signals=raw_signals,
            selected=["trace"],
            signal_assumptions=[{"time_unit": "ms", "time_unit_known": True, "default_integrations": 0, "assumed_input": "Unknown"}],
            a0=0.2,
            lim_t=40.0,
            detrend_on=False,
            detrend_after_amp=False,
            shift_on=False,
            flip_polarity=False,
            pk_dist=1,
            pk_wmin=1,
            pk_wmax=None,
            pk_prom=0.0,
            to_length=False,
            wavespeed=4000.0,
            integration_mode="Off",
            integration_method="regularized_fd",
            integration_low_frequency_hz=10.0,
            integration_zero_baseline=False,
            filt_on=True,
            filter_before_amp=False,
            fwd_bwd=True,
            f_lp=150.0,
            f_hp=5.0,
            f_ord=2,
            mov_win=0.0,
            spline_smooth=0.0,
            signal_window_on=True,
            signal_window_taper_ms=5.0,
            signal_window_padding_ms=4.0,
            d_user=1,
            aa_on=True,
        )
        processed = processing_pipeline.pd.DataFrame(result["signal"][0][0])
        self.assertGreaterEqual(float(processed["time"].min()), 0.0)
        self.assertLessEqual(float(processed["time"].max()), 40.0)

    def test_coi_edge_half_width_matches_reference_logic_for_fixed_and_adaptive_modes(self):
        fixed = legacy_callbacks._coi_edge_half_samples(
            frequencies=np.array([10.0, 20.0]),
            sample_freq=1000.0,
            slt_mode="fixed",
            superlet_set_mode="multiplicative",
            c_1=2.0,
            k_sd=5.0,
            support_sd=8.0,
            order_slt=4.0,
            order_min=1.0,
            order_max=4.0,
        )
        np.testing.assert_array_equal(fixed, np.array([640, 320]))

        adaptive = legacy_callbacks._coi_edge_half_samples(
            frequencies=np.array([10.0, 20.0, 30.0]),
            sample_freq=1000.0,
            slt_mode="adaptive",
            superlet_set_mode="multiplicative",
            c_1=2.0,
            k_sd=5.0,
            support_sd=8.0,
            order_slt=4.0,
            order_min=1.0,
            order_max=4.0,
        )
        np.testing.assert_array_equal(adaptive, np.array([160, 240, 214]))

    def test_coi_nan_mask_masks_edges_and_lowest_rows(self):
        matrix = np.arange(40, dtype=float).reshape(4, 10)
        masked = legacy_callbacks._apply_coi_nan_mask(
            matrix,
            np.array([1, 2, 3, 1]),
            mask_lowest_rows=2,
            smooth_sigma_rows=0.0,
        )

        self.assertTrue(np.isnan(masked[0]).all())
        self.assertTrue(np.isnan(masked[1]).all())
        self.assertTrue(np.isnan(masked[2, :3]).all())
        self.assertTrue(np.isnan(masked[2, -3:]).all())
        self.assertEqual(masked[2, 5], matrix[2, 5])
        self.assertTrue(np.isnan(masked[3, 0]))
        self.assertTrue(np.isnan(masked[3, -1]))
        self.assertEqual(masked[3, 5], matrix[3, 5])

    def test_prepare_slt_heatmap_data_handles_coi_mask_and_log_limits(self):
        spec = np.ones((4, 10), dtype=np.complex128)
        plot_data = legacy_callbacks._prepare_slt_heatmap_data(
            spec=spec,
            slt_out="Power",
            log_colorscale=True,
            log_floor_exp=-6.0,
            coi_mask_on=True,
            cmin=None,
            cmax=None,
            lang="EN",
            to_length=False,
            x_unit="ms",
            t=np.arange(10, dtype=float),
            foi=np.array([50.0, 100.0, 150.0, 200.0]),
            sample_freq=1000.0,
            coi_settings={
                "slt_mode": "fixed",
                "superlet_set_mode": "multiplicative",
                "c_1": 2.0,
                "k_sd": 5.0,
                "support_sd": 8.0,
                "order_slt": 1.0,
                "order_min": 1.0,
                "order_max": 1.0,
            },
            source_name="trace",
        )

        self.assertTrue(np.isnan(plot_data["z"][:2]).all())
        self.assertTrue(np.isfinite(plot_data["vmin"]))
        self.assertTrue(np.isfinite(plot_data["vmax"]))
        self.assertIn("log10(Power)", plot_data["colorbar_title"])

    def test_build_slt_attribute_curves_supports_multi_select_and_phase(self):
        spec = np.ones((3, 12), dtype=np.complex128)
        spec[1, :] = 2.0 + 0.0j
        spec[2, :] = np.exp(1j * np.linspace(0.0, np.pi, 12))

        result = legacy_callbacks._build_slt_attribute_curves(
            spec=spec,
            x_values=np.arange(12, dtype=float),
            frequencies=np.array([100.0, 200.0, 300.0]),
            sample_freq=1000.0,
            metric_keys=["power", "phase"],
            normalize_on=True,
            zero_baseline_on=False,
            freq_reduce="mean",
            x_reduce="mean",
            x_window_ms=2.0,
            band_min_hz=90.0,
            band_max_hz=220.0,
            phase_freq_hz=290.0,
            coi_mask_on=False,
            coi_settings=None,
        )

        self.assertEqual([curve["key"] for curve in result["curves"]], ["power", "phase"])
        self.assertTrue(result["has_phase"])
        self.assertTrue(result["has_non_phase"])
        self.assertTrue(result["non_phase_normalized"])
        self.assertTrue(all(len(curve["x"]) == 12 and len(curve["y"]) == 12 for curve in result["curves"]))
        self.assertEqual(result["curves"][0]["axis"], "value")
        self.assertEqual(result["curves"][1]["axis"], "phase")

    def test_build_slt_attribute_curves_breaks_phase_near_wrap_only(self):
        phase_deg = np.array([179.0, -179.0, 120.0, -120.0, 170.0, -170.0], dtype=float)
        spec = np.exp(1j * np.deg2rad(phase_deg))[None, :]

        result = legacy_callbacks._build_slt_attribute_curves(
            spec=spec,
            x_values=np.arange(phase_deg.size, dtype=float),
            frequencies=np.array([300.0], dtype=float),
            sample_freq=1000.0,
            metric_keys=["phase"],
            normalize_on=False,
            zero_baseline_on=True,
            freq_reduce="mean",
            x_reduce="mean",
            x_window_ms=0.0,
            band_min_hz=None,
            band_max_hz=None,
            phase_freq_hz=300.0,
            coi_mask_on=False,
            coi_settings=None,
        )

        y = result["curves"][0]["y"]
        self.assertTrue(np.isnan(y[1]))
        self.assertFalse(np.isnan(y[3]))
        self.assertFalse(np.isnan(y[5]))

    def test_plot_signal_places_generic_marker_and_draws_band_guides(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data,
            av_signal,
            peaks,
            4000.0,
            None,
            None,
            3.0,
            "defect",
            False,
            False,
            False,
            filenames,
            {"trace1": "#336699"},
            compute_store,
            True,
            False,
            "Power",
            "Viridis",
            None,
            None,
            True,
            -6.0,
            True,
            "below_slt",
            ["power"],
            True,
            True,
            "mean",
            "mean",
            0.0,
            40.0,
            120.0,
            True,
            True,
            100.0,
            True,
            True,
            False,
            100.0,
            600,
            "EN",
        )[0]

        shapes = list(graph.figure.layout.shapes)
        self.assertTrue(any(abs(float(shape["x0"]) - 3.0) < 1e-9 and shape["type"] == "line" for shape in shapes))
        horizontal = [shape for shape in shapes if shape["type"] == "line" and abs(float(shape["y0"]) - float(shape["y1"])) < 1e-9]
        self.assertTrue(any(abs(float(shape["y0"]) - 40.0) < 1e-9 for shape in horizontal))
        self.assertTrue(any(abs(float(shape["y0"]) - 120.0) < 1e-9 for shape in horizontal))

    def test_plot_signal_draws_phase_frequency_guide_line_on_slt(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=True,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=True,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["power", "phase"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=True,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        horizontal = [
            shape for shape in graph.figure.layout.shapes
            if shape["type"] == "line" and abs(float(shape["y0"]) - float(shape["y1"])) < 1e-9
        ]
        self.assertTrue(any(abs(float(shape["y0"]) - 40.0) < 1e-9 for shape in horizontal))
        self.assertTrue(any(abs(float(shape["y0"]) - 120.0) < 1e-9 for shape in horizontal))
        self.assertTrue(any(abs(float(shape["y0"]) - 100.0) < 1e-9 for shape in horizontal))
        heatmap = next(trace for trace in graph.figure.data if trace.type == "heatmap")
        self.assertEqual(heatmap.colorbar.tickmode, "auto")
        self.assertEqual(int(heatmap.colorbar.nticks), 5)
        self.assertEqual(heatmap.colorbar.title.side, "top")
        self.assertEqual(heatmap.colorbar.yanchor, "middle")
        axis_name = "yaxis" if heatmap.yaxis == "y" else f"yaxis{heatmap.yaxis[1:]}"
        y_domain = tuple(getattr(graph.figure.layout, axis_name).domain)
        xaxis_name = "xaxis" if heatmap.xaxis == "x" else f"xaxis{heatmap.xaxis[1:]}"
        x_domain = tuple(getattr(graph.figure.layout, xaxis_name).domain)
        self.assertEqual(heatmap.colorbar.lenmode, "pixels")
        expected_len = 0.95 * float(graph.figure.layout.height) * (float(y_domain[1]) - float(y_domain[0]))
        self.assertAlmostEqual(float(heatmap.colorbar.len), expected_len)
        self.assertAlmostEqual(float(heatmap.colorbar.y), 0.5 * (float(y_domain[0]) + float(y_domain[1])))
        self.assertAlmostEqual(float(heatmap.colorbar.x), float(x_domain[1]) + 0.022)

    def test_build_slt_attribute_curves_single_bound_min_uses_slice_metadata(self):
        spec = np.array(
            [
                [1.0 + 0.0j, 1.0 + 0.0j, 1.0 + 0.0j],
                [2.0 + 0.0j, 2.0 + 0.0j, 2.0 + 0.0j],
                [10.0 + 0.0j, 10.0 + 0.0j, 10.0 + 0.0j],
            ],
            dtype=complex,
        )
        payload = slt_analysis.build_slt_attribute_curves(
            spec=spec,
            x_values=np.array([0.0, 1.0, 2.0]),
            frequencies=np.array([10.0, 20.0, 40.0]),
            sample_freq=1000.0,
            metric_keys=["amp"],
            normalize_on=False,
            zero_baseline_on=False,
            freq_reduce="mean",
            x_reduce="mean",
            x_window_ms=0.0,
            band_min_hz=18.0,
            band_max_hz=None,
            phase_freq_hz=20.0,
            coi_mask_on=False,
            coi_settings=None,
        )

        curve = payload["curves"][0]
        np.testing.assert_allclose(curve["y"], np.array([2.0, 2.0, 2.0]))
        self.assertEqual(curve["source_kind"], "slice")
        self.assertAlmostEqual(float(curve["source_frequency_hz"]), 20.0)
        self.assertIsNone(curve["source_band_min_hz"])
        self.assertIsNone(curve["source_band_max_hz"])

    def test_build_slt_attribute_curves_single_bound_max_uses_slice_metadata(self):
        spec = np.array(
            [
                [1.0 + 0.0j, 1.0 + 0.0j, 1.0 + 0.0j],
                [2.0 + 0.0j, 2.0 + 0.0j, 2.0 + 0.0j],
                [10.0 + 0.0j, 10.0 + 0.0j, 10.0 + 0.0j],
            ],
            dtype=complex,
        )
        payload = slt_analysis.build_slt_attribute_curves(
            spec=spec,
            x_values=np.array([0.0, 1.0, 2.0]),
            frequencies=np.array([10.0, 20.0, 40.0]),
            sample_freq=1000.0,
            metric_keys=["amp"],
            normalize_on=False,
            zero_baseline_on=False,
            freq_reduce="median",
            x_reduce="mean",
            x_window_ms=0.0,
            band_min_hz=None,
            band_max_hz=35.0,
            phase_freq_hz=20.0,
            coi_mask_on=False,
            coi_settings=None,
        )

        curve = payload["curves"][0]
        np.testing.assert_allclose(curve["y"], np.array([10.0, 10.0, 10.0]))
        self.assertEqual(curve["source_kind"], "slice")
        self.assertAlmostEqual(float(curve["source_frequency_hz"]), 40.0)

    def test_plot_signal_uses_direct_title_badge_and_hidden_legend_for_single_non_phase_subplot(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=False,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["amp"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        amp_trace = next(trace for trace in graph.figure.data if str(trace.name) == "Amp")
        amp_axis = layout_axis(graph.figure, amp_trace.yaxis, "y")
        self.assertFalse(bool(amp_trace.showlegend))
        self.assertEqual(amp_axis.title.text, "Amp (norm.)")
        badge = next(annotation for annotation in graph.figure.layout.annotations if str(annotation.text).startswith("band "))
        self.assertRegex(str(badge.text), r"^band .+-.+ Hz$")

    def test_plot_signal_uses_slice_badge_for_single_bound_non_phase_subplot(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=False,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["amp"],
            superlet_attr_normalize=False,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="median",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=None,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        amp_trace = next(trace for trace in graph.figure.data if str(trace.name) == "Amp")
        amp_axis = layout_axis(graph.figure, amp_trace.yaxis, "y")
        self.assertEqual(amp_axis.title.text, "Amp")
        badge = next(annotation for annotation in graph.figure.layout.annotations if str(annotation.text).startswith("slice "))
        self.assertRegex(str(badge.text), r"^slice .+ Hz$")

    def test_plot_signal_hides_single_metric_badge_when_switch_is_off(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=False,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["amp"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=False,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        self.assertFalse(any(str(annotation.text).startswith(("band ", "slice ")) for annotation in graph.figure.layout.annotations))

    def test_plot_signal_places_standalone_phase_on_left_axis_of_attribute_subplot(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=True,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=True,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["phase"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=True,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        phase_trace = next(trace for trace in graph.figure.data if str(trace.name).startswith("Phase @"))
        phase_axis = layout_axis(graph.figure, phase_trace.yaxis, "y")
        self.assertFalse(bool(phase_trace.showlegend))
        self.assertEqual(graph.figure.layout.yaxis4.title.text, "Phase, °")
        self.assertEqual(tuple(float(value) for value in phase_axis.range), (-180.0, 180.0))
        self.assertEqual(tuple(float(value) for value in phase_axis.tickvals), (-180.0, -90.0, 0.0, 90.0, 180.0))
        badge = next(annotation for annotation in graph.figure.layout.annotations if str(annotation.text).startswith("slice "))
        self.assertRegex(str(badge.text), r"^slice .+ Hz$")
        self.assertFalse(hasattr(graph.figure.layout, "yaxis5"))

    def test_plot_signal_uses_fixed_phase_ticks_for_signal_overlay(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=False,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="signal",
            superlet_attribute_keys=["phase"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        self.assertEqual(graph.figure.layout.yaxis2.title.text, "Phase, deg")
        self.assertEqual(tuple(float(value) for value in graph.figure.layout.yaxis2.range), (-180.0, 180.0))
        self.assertEqual(tuple(float(value) for value in graph.figure.layout.yaxis2.tickvals), (-180.0, -90.0, 0.0, 90.0, 180.0))

    def test_plot_signal_keeps_mixed_phase_axis_unflipped_on_attribute_subplot(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=True,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["power", "phase"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=600,
            lang="EN",
        )[0]

        self.assertEqual(graph.figure.layout.yaxis5.title.text, "Phase, deg")
        self.assertEqual(tuple(float(value) for value in graph.figure.layout.yaxis5.range), (-180.0, 180.0))
        self.assertEqual(tuple(float(value) for value in graph.figure.layout.yaxis5.tickvals), (-180.0, -90.0, 0.0, 90.0, 180.0))

    def test_plot_signal_horizontal_mode_uses_single_row_with_matched_x_axes(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float((i % 7) - 3) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=3.0,
            generic_marker_label="defect",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=True,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=True,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["power"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=True,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=True,
            show_legend=True,
            horizontal_subplots=True,
            plot_width_pct=100.0,
            plot_height_px=250,
            lang="EN",
        )[0]
        self.assertEqual(int(graph.figure.layout.height), 250)
        self.assertEqual(graph.figure.layout.xaxis.title.text, "Depth, m")
        self.assertEqual(graph.figure.layout.xaxis2.title.text, "Depth, m")
        self.assertEqual(graph.figure.layout.xaxis3.title.text, "Depth, m")
        self.assertEqual(graph.figure.layout.xaxis2.matches, "x")
        self.assertEqual(graph.figure.layout.xaxis3.matches, "x")

        heatmap = next(trace for trace in graph.figure.data if trace.type == "heatmap")
        slt_domain = tuple(float(v) for v in graph.figure.layout.xaxis2.domain)
        attr_domain = tuple(float(v) for v in graph.figure.layout.xaxis3.domain)
        self.assertGreater(float(heatmap.colorbar.x), slt_domain[1])
        self.assertGreater(float(heatmap.colorbar.x), attr_domain[1])
        self.assertEqual(heatmap.colorbar.title.side, "top")

    def test_y_axis_exponent_format_is_applied_to_time_and_spectrum_plots(self):
        signal = {"time": {i: float(i) for i in range(24)}, "amp": {i: float(10 ** i) for i in range(24)}}
        data = [[signal], 0.0, 46.0]
        av_signal = [[], []]
        filenames = ["trace1"]
        peaks = [[[], []], [[], []]]

        compute_store = callbacks.compute_slt_result(
            data,
            av_signal,
            filenames,
            True,
            True,
            True,
            4000.0,
            False,
            0.0,
            "adaptive",
            "multiplicative",
            "circular",
            10.0,
            300.0,
            16,
            3.0,
            5.0,
            8.0,
            4.0,
            1.0,
            5.0,
        )
        time_graph = callbacks.plot_signal(
            data=data,
            av_signal=av_signal,
            peaks=peaks,
            wavespeed=4000.0,
            length_marker=None,
            reflection=None,
            generic_marker_ms=None,
            generic_marker_label="",
            show_markers=False,
            simplify_plot=False,
            reverse_axis=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            compute_store=compute_store,
            superlet_plot=False,
            superlet_coi_mask_on=False,
            slt_out="Power",
            cmap_name="Viridis",
            cmin=None,
            cmax=None,
            cmap_log=False,
            cmap_log_floor_exp=-6.0,
            superlet_attributes_on=False,
            superlet_attribute_placement="below_slt",
            superlet_attribute_keys=["power"],
            superlet_attr_normalize=True,
            superlet_attr_zero_baseline=True,
            superlet_attr_freq_reduce="mean",
            superlet_attr_x_reduce="mean",
            superlet_attr_x_window_ms=0.0,
            superlet_attr_freq_min_hz=40.0,
            superlet_attr_freq_max_hz=120.0,
            superlet_attr_show_band_guides=False,
            superlet_attr_show_source_badge=True,
            superlet_attr_phase_freq_hz=100.0,
            to_length=False,
            show_legend=True,
            horizontal_subplots=False,
            plot_width_pct=100.0,
            plot_height_px=250,
            lang="EN",
            y_axis_exponent_format="power",
        )[0]
        self.assertEqual(time_graph.figure.layout.yaxis.exponentformat, "power")

        spectrum = [
            [np.array([1.0, 10.0, 100.0])],
            [np.array([1.0, 1000.0, 1000000.0])],
            [np.array([1.0, 10.0, 100.0])],
            [np.array([1.0, 1000.0, 1000000.0])],
            None,
            None,
        ]
        spectrum_graph = callbacks.plot_spectrum(
            spectrum=spectrum,
            filter_switch=False,
            filter_draw=False,
            filenames=filenames,
            color_map={"trace1": "#336699"},
            spectrum_autozoom_x=True,
            show_legend=True,
            lang="EN",
            y_axis_exponent_format="power",
        )[0]
        self.assertEqual(spectrum_graph.figure.layout.yaxis.exponentformat, "power")


if __name__ == "__main__":
    unittest.main()
