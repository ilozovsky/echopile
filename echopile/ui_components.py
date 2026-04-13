"""UI layout components for echopile."""

from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from .help_texts import HELP_TEXTS
from .translations import translate
from .core.settings_defaults import get_snc_ui_defaults_map
from .config import (
    LAYOUT_LANG_DEFAULT,
    SETTINGS_ROW_STYLE,
    SLIDER_SETTINGS_ROW_STYLE,
    DMC_SLIDER_STYLES,
    DMC_SLIDER_WRAPPER_STYLE,
)


UI_DEFAULTS = get_snc_ui_defaults_map()


def _help_icon(help_text):
    return dmc.Tooltip(
        label=help_text,
        multiline=True,
        w=260,
        withArrow=True,
        withinPortal=True,
        zIndex=10000,
        styles={
            "tooltip": {
                "backgroundColor": "#FFFFFF",
                "color": "#2C3440",
                "border": "1px solid #D7DEE8",
                "boxShadow": "0 8px 22px rgba(25, 35, 52, 0.12)",
                "fontSize": "13px",
                "lineHeight": "1.5",
                "padding": "8px 10px",
            }
        },
        transitionProps={"transition": "fade", "duration": 120},
        children=html.Span(
            DashIconify(icon="mdi:information-outline", width=14),
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "lineHeight": "1",
                "color": "#7A8797",
                "cursor": "help",
                "marginLeft": "6px",
                "verticalAlign": "baseline",
            },
        ),
    )

def _controls(lang: str) -> html.Div:
    return html.Div(
        [
            dcc.Store(id="signal_raw"),
            dcc.Store(id="signal"),
            dcc.Store(id="peaks"),
            dcc.Store(id="spectrum"),
            dcc.Store(id="filename-store"),
            dcc.Store(id="selected-filenames-store"),
            dcc.Store(id="selected-filenames-color-store"),
            dcc.Store(id="signal-assumptions-store"),
            dcc.Store(id="compute-result-store"),
            dcc.Store(id="signal-end-ms-store", data=UI_DEFAULTS["lim_time_max"]),
            dcc.Store(id="av-win-ms-store", data=UI_DEFAULTS["moving_window_size"]),
            dcc.Store(id="signal-window-taper-ms-store", data=UI_DEFAULTS["signal_window_taper_ms"]),
            dcc.Store(id="signal-window-padding-ms-store", data=UI_DEFAULTS["signal_window_padding_ms"]),
            dcc.Store(id="superlet-attr-x-window-ms-store", data=UI_DEFAULTS["superlet_attr_x_window_ms"]),
            dcc.Store(id="av_signal"),

            dbc.Row(
                [
                    html.Div(
                        dcc.Upload(
                            id="upload-data",
                            children=dmc.Button(
                                translate("Load", lang),
                                id="btn-upload",
                                variant="gradient",
                                gradient={"from": "indigo", "to": "cyan"},
                                fullWidth=True,
                                leftSection=DashIconify(
                                    icon="si:hammer-alt-duotone", width=20
                                ),
                            ),
                            multiple=True,
                            accept=".sgy,.txt,.csv,.snc",
                        ),
                        style={"width": "50%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dmc.Button(
                                translate("Save", lang),
                                id="btn-download",
                                variant="gradient",
                                gradient={"from": "teal", "to": "lime", "deg": 105},
                                fullWidth=True,
                                leftSection=DashIconify(
                                    icon="material-symbols-light:save-outline",
                                    width=25,
                                ),
                            ),
                            dcc.Download(id="download"),
                        ],
                        style={"width": "50%", "display": "inline-block"},
                    ),
                ],
                style=SLIDER_SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        [
                            html.Div(
                                dbc.Label(translate("Filenames", lang), id="filenames-label"),
                                style={
                                    "width": "35%",
                                    "display": "inline-block",
                                    "vertical-align": "top",
                                },
                            ),
                            html.Div(
                                dmc.CheckboxGroup(id="checkbox-group", children=None),
                                style={"width": "65%", "display": "inline-block"},
                            ),
                        ],
                        style={"width": "60%", "display": "none"},
                        id="files-select-div",
                    )
                ],
                style=SLIDER_SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Amplification", lang), id="amplification-label"),
                                _help_icon(HELP_TEXTS["amplification"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        dmc.Slider(
                            min=0,
                            max=1,
                            step=0.01,
                            precision=2,
                            value=UI_DEFAULTS["a0"],
                            id="amp-slider",
                            className="ep-main-slider",
                            marks=None,
                            color="cyan",
                            size="xs",
                            styles=DMC_SLIDER_STYLES,
                            style=DMC_SLIDER_WRAPPER_STYLE,
                            updatemode="mouseup",
                            labelAlwaysOn=True,
                        ),
                        style={
                            "width": "65%",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                            "padding": "0px 0px 0px 0px",
                        },
                    ),
                ],
                style=SLIDER_SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Signal end, m", lang), id="signal-length-label"),
                                _help_icon(HELP_TEXTS["signal_end"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        id="time-slider-container",
                        children=dmc.Slider(
                            min=0,
                            step=0.1,
                            precision=1,
                            value=0.0,
                            id="time-slider",
                            className="ep-main-slider",
                            marks=None,
                            color="cyan",
                            size="xs",
                            styles=DMC_SLIDER_STYLES,
                            style=DMC_SLIDER_WRAPPER_STYLE,
                            updatemode="mouseup",
                            labelAlwaysOn=True,
                        ),
                        style={
                            "width": "65%",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                            "padding": "0px 0px 0px 0px",
                        },
                    ),
                ],
                style=SLIDER_SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Averaging window size, ms", lang), id="averaging-window-label"),
                                _help_icon(HELP_TEXTS["averaging_window"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        id="av-win-slider-container",
                        children=dmc.Slider(
                            min=0,
                            max=3,
                            step=0.01,
                            precision=2,
                            value=UI_DEFAULTS["moving_window_size"],
                            id="av-win-slider",
                            className="ep-main-slider",
                            marks=[
                                {"value": 0, "label": "OFF"},
                                {"value": 1, "label": "1.0"},
                                {"value": 2, "label": "2.0"},
                                {"value": 3, "label": "3.0"},
                            ],
                            color="cyan",
                            size="xs",
                            styles=DMC_SLIDER_STYLES,
                            style=DMC_SLIDER_WRAPPER_STYLE,
                            updatemode="mouseup",
                            showLabelOnHover=True,
                        ),
                        style={
                            "width": "65%",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                            "padding": "0px 0px 0px 0px",
                        },
                    ),
                ],
                id="averaging-window-row",
                style=SLIDER_SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Smoothing", lang), id="smoothing-label"),
                                _help_icon(HELP_TEXTS["smoothing"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        dmc.Slider(
                            min=0,
                            max=300,
                            step=1,
                            precision=0,
                            value=UI_DEFAULTS["spline_smoothing"],
                            id="smoothing-slider",
                            className="ep-main-slider",
                            marks=[
                                {"value": 0, "label": "OFF"},
                                {"value": 75, "label": "75"},
                                {"value": 150, "label": "150"},
                                {"value": 225, "label": "225"},
                                {"value": 300, "label": "300"},
                            ],
                            color="cyan",
                            size="xs",
                            styles=DMC_SLIDER_STYLES,
                            style=DMC_SLIDER_WRAPPER_STYLE,
                            updatemode="mouseup",
                            showLabelOnHover=True,
                        ),
                        style={
                            "width": "65%",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                            "padding": "0px 0px 0px 0px",
                        },
                    ),
                ],
                id="smoothing-row",
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Wave speed, m/s", lang), id="wavespeed-label"),
                                _help_icon(HELP_TEXTS["wave_speed"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        dmc.Slider(
                            min=2000,
                            max=6000,
                            step=50,
                            precision=0,
                            value=UI_DEFAULTS["wavespeed"],
                            id="wavespeed-slider",
                            className="ep-main-slider",
                            marks=None,
                            color="cyan",
                            size="xs",
                            styles=DMC_SLIDER_STYLES,
                            style=DMC_SLIDER_WRAPPER_STYLE,
                            updatemode="mouseup",
                            labelAlwaysOn=True,
                        ),
                        style={
                            "width": "50%",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                            "padding": "0px 0px 0px 0px",
                        },
                    ),
                    html.Div(
                        dmc.NumberInput(
                            id="wavespeed-input",
                            size="xs",
                            step=1,
                            hideControls=True,
                            min=2000,
                            max=6000,
                            value=UI_DEFAULTS["wavespeed"],
                        ),
                        style={"width": "15%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Pile length marker, m", lang), id="length-marker-label"),
                                _help_icon(HELP_TEXTS["pile_length_marker"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Input(id="length-marker", type="number", min=0, step=0.01, value=UI_DEFAULTS["length_marker"]),
                        style={"width": "20%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Generic marker, m", lang), id="generic-marker-label"),
                                _help_icon(HELP_TEXTS["generic_marker"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Input(id="generic-marker-input", type="number", min=0, step=0.01, value=UI_DEFAULTS["generic_marker_ms"]),
                        id="generic-marker-container",
                        style={"width": "20%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label("Generic marker label", id="generic-marker-text-label"),
                                _help_icon(HELP_TEXTS["generic_marker_label"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Input(
                            id="generic-marker-text",
                            type="text",
                            value=UI_DEFAULTS["generic_marker_label"],
                            debounce=True,
                            placeholder="optional",
                        ),
                        style={"width": "45%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Show legend", lang), id="show-legend-label"),
                                _help_icon(HELP_TEXTS["show_legend"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Switch(id="show-legend-switch", value=UI_DEFAULTS["show_legend"]),
                        style={"width": "45%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dmc.Paper(
                [
            dbc.Row(
                html.Div(
                    [
                        dbc.Switch(id="superlet-switch", value=UI_DEFAULTS["superlet_plot"]),
                        html.Div(
                            [
                                dbc.Label(translate("Superlet", lang), id="superlet-label", style={"display": "inline-block", "marginBottom": 0}),
                                _help_icon(HELP_TEXTS["superlet_main"]),
                            ],
                            style={"display": "flex", "alignItems": "baseline"},
                        ),
                    ],
                    style={
                        "display": "inline-flex",
                        "alignItems": "center",
                        "gap": "10px",
                        "padding": "2px 0 2px 6px",
                    },
                ),
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Display", lang), id="slt-output-label", style={"display": "inline-block"}),
                                _help_icon(HELP_TEXTS["slt_output"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                    ),
                    html.Div(
                        dmc.SegmentedControl(
                            id="SLT_output",
                            value=UI_DEFAULTS["SLT_output"],
                            fullWidth=True,
                            data=[
                                {"value": "Power", "label": translate("Power", lang)},
                                {"value": "Abs", "label": translate("Amp", lang)},
                                {"value": "Arg", "label": translate("Phase", lang)},
                                {"value": "Re", "label": translate("Re", lang)},
                                {"value": "Im", "label": translate("Im", lang)},
                            ],
                        ),
                        style={"width": "65%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),



            dbc.Row(
                [
                    html.Div(
                        [
                            dbc.Input(id="freq_SLT_min", type="number", min=0.001, step="any", value=UI_DEFAULTS["freq_SLT_min"]),
                            html.Div(
                                [
                                    dbc.FormText(translate("Minimal freq", lang), id="freq-slt-min-label", style={"display": "inline-block"}),
                                    _help_icon(HELP_TEXTS["freq_slt_min"]),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="freq_SLT_max", type="number", min=0.001, step="any", value=UI_DEFAULTS["freq_SLT_max"]),
                            html.Div(
                                [
                                    dbc.FormText(translate("Maximal freq", lang), id="freq-slt-max-label", style={"display": "inline-block"}),
                                    _help_icon(HELP_TEXTS["freq_slt_max"]),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="freq_SLT_no", type="number", min=1, step=1, value=UI_DEFAULTS["freq_SLT_no"]),
                            html.Div(
                                [
                                    dbc.FormText(translate("Number of freqs", lang), id="freq-slt-no-label", style={"display": "inline-block"}),
                                    _help_icon(HELP_TEXTS["freq_slt_no"]),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        style={"width": "33%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        [
                            dbc.Input(id="c_1", type="number", min=1, step="any", value=UI_DEFAULTS["c_1"]),
                            html.Div([dbc.FormText(translate("Base cycles", lang), id="cycles-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["base_cycles"])], style={"display": "flex", "alignItems": "center"}),
                        ],
                        id="cycles-col",
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="order_slt", type="number", min=1, step=1, value=UI_DEFAULTS["order_slt"]),
                            html.Div([dbc.FormText(translate("Order", lang), id="order-slt-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["order_fixed"])], style={"display": "flex", "alignItems": "center"}),
                        ],
                        id="order-slt-col",
                        style={"width": "50%", "display": "none"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="order_min", type="number", min=1, step="any", value=UI_DEFAULTS["order_min"]),
                            html.Div([dbc.FormText(translate("Min order", lang), id="order-min-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["order_min"])], style={"display": "flex", "alignItems": "center"}),
                        ],
                        id="order-min-col",
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="order_max", type="number", min=1, step="any", value=UI_DEFAULTS["order_max"]),
                            html.Div([dbc.FormText(translate("Max order", lang), id="order-max-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["order_max"])], style={"display": "flex", "alignItems": "center"}),
                        ],
                        id="order-max-col",
                        style={"width": "33%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Colorscale", lang), id="colorscale-label", style={"display": "inline-block"}),
                                _help_icon(HELP_TEXTS["colorscale"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Select(
                            id="cmap_SLT",
                            value=UI_DEFAULTS["cmap_SLT"],
                            size="sm",
                            options=[
                                {"value": "Default", "label": "Default"},
                                {"value": "Turbo", "label": "Turbo"},
                                {"value": "Greys", "label": "Greys"},
                                {"value": "RdBu_r", "label": "Red-Blue"},
                                {"value": "Spectral", "label": "Spectral"},
                                {"value": "Spectral_r", "label": "Spectral_r"},
                                {"value": "RdYlGn", "label": "RdYlGn"},
                                {"value": "RdYlGn_r", "label": "RdYlGn_r"},
                                {"value": "balance", "label": "balance"},
                                {"value": "curl", "label": "curl"},
                                {"value": "Tealrose", "label": "Tealrose"},
                                {"value": "Portland", "label": "Portland"},
                                {"value": "Temps", "label": "Temps"},
                                {"value": "Twilight", "label": "Twilight"},
                                {"value": "IceFire", "label": "IceFire"},
                                {"value": "Phase", "label": "Phase"},
                                {"value": "mrybm", "label": "mrybm"},
                                {"value": "nipy_spectral", "label": "Nipy spectral"},
                                {"value": "colorscale_phase", "label": "Phase colorscale"},
                            ],
                            style={"marginBottom": 1},
                        ),
                        style={"width": "67%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label(translate("Log colorscale", lang), id="log-colorscale-label"),
                                _help_icon(HELP_TEXTS["log_colorscale"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dbc.Switch(id="cmap_SLT_log", value=UI_DEFAULTS["cmap_SLT_log"]),
                        style={"width": "45%", "display": "inline-block"},
                    ),
                ],
                id="slt-log-colorscale-row",
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label("Log floor exponent", id="slt-log-floor-exp-label"),
                                _help_icon(HELP_TEXTS["slt_log_floor_exp"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "55%", "display": "inline-block"},
                    ),
                    html.Div(
                        dmc.NumberInput(
                            id="cmap_SLT_log_floor_exp",
                            size="xs",
                            step=1,
                            decimalScale=0,
                            fixedDecimalScale=False,
                            value=UI_DEFAULTS["cmap_SLT_log_floor_exp"],
                        ),
                        style={"width": "20%", "display": "inline-block"},
                    ),
                ],
                id="slt-log-floor-row",
                style={**SETTINGS_ROW_STYLE, "display": "none"},
            ),

            dbc.Row(
                [
                    html.Div(style={"width": "33%", "display": "inline-block"}),
                    html.Div(
                        [
                            dbc.Input(id="cmap_SLT_min", type="number", value=UI_DEFAULTS["cmap_SLT_min"]),
                            dbc.FormText(translate("Low limit", lang), id="cmap-min-label"),
                        ],
                        style={"width": "33%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="cmap_SLT_max", type="number", value=UI_DEFAULTS["cmap_SLT_max"]),
                            dbc.FormText(translate("High limit", lang), id="cmap-max-label"),
                        ],
                        style={"width": "33%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),
                ],
                withBorder=True,
                radius="md",
                p="sm",
                shadow="xs",
                style={
                    "borderColor": "#DDE6F0",
                    "backgroundColor": "#FAFBFD",
                    "marginTop": "6px",
                    "marginBottom": "6px",
                },
            ),

            dmc.Paper(
                [
                    dbc.Row(
                        html.Div(
                            [
                                dbc.Switch(id="superlet-attributes-switch", value=UI_DEFAULTS["superlet_attributes_on"]),
                                html.Div(
                                    [
                                        dbc.Label("1D SLT metrics", id="superlet-attributes-label", style={"display": "inline-block", "marginBottom": 0}),
                                        _help_icon(HELP_TEXTS["superlet_attributes"]),
                                    ],
                                    style={"display": "flex", "alignItems": "baseline"},
                                ),
                            ],
                            style={
                                "display": "inline-flex",
                                "alignItems": "center",
                                "gap": "10px",
                                "padding": "2px 0 2px 6px",
                            },
                        ),
                        style=SETTINGS_ROW_STYLE,
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                html.Div(
                                    [
                                        dbc.Label("Plot location", id="superlet-attr-placement-label", style={"display": "inline-block"}),
                                        _help_icon(HELP_TEXTS["superlet_attribute_placement"]),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                                style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                            ),
                            html.Div(
                                dmc.SegmentedControl(
                                    id="superlet-attribute-placement",
                                    value=UI_DEFAULTS["superlet_attribute_placement"],
                                    fullWidth=True,
                                    data=[
                                        {"label": "Signal", "value": "signal"},
                                        {"label": "Below SLT", "value": "below_slt"},
                                    ],
                                ),
                                style={"width": "65%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-placement-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                html.Div(
                                    [
                                        dbc.Label("Metrics", id="superlet-attr-keys-label", style={"display": "inline-block"}),
                                        _help_icon(HELP_TEXTS["superlet_attribute_keys"]),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                                style={"width": "35%", "display": "inline-block", "verticalAlign": "top"},
                            ),
                            html.Div(
                                dmc.MultiSelect(
                                    id="superlet-attribute-keys",
                                    value=UI_DEFAULTS["superlet_attribute_keys"],
                                    data=[
                                        {"value": "power", "label": "Power"},
                                        {"value": "log_power", "label": "log10(Power)"},
                                        {"value": "amp", "label": "Amp"},
                                        {"value": "log_amp", "label": "log10(Amp)"},
                                        {"value": "re", "label": "Re"},
                                        {"value": "im", "label": "Im"},
                                        {"value": "phase", "label": "Phase"},
                                    ],
                                    placeholder="Choose one or more metrics",
                                    clearable=False,
                                    searchable=False,
                                    comboboxProps={"withinPortal": False, "position": "bottom-start"},
                                    w="100%",
                                ),
                                style={"width": "65%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-keys-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                [
                                    dbc.Switch(id="superlet-attr-normalize-switch", value=UI_DEFAULTS["superlet_attr_normalize"]),
                                    html.Div(
                                        [
                                            dbc.Label("Normalize to max", id="superlet-attr-normalize-label", style={"marginBottom": 0}),
                                            _help_icon(HELP_TEXTS["superlet_attr_normalize"]),
                                        ],
                                        style={"display": "flex", "alignItems": "baseline"},
                                    ),
                                ],
                                style={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                    "gap": "10px",
                                    "padding": "2px 0 2px 6px",
                                },
                            ),
                        ],
                        id="superlet-attr-normalize-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                [
                                    dbc.Switch(id="superlet-attr-zero-baseline-switch", value=UI_DEFAULTS["superlet_attr_zero_baseline"]),
                                    html.Div(
                                        [
                                            dbc.Label("Zero baseline", style={"marginBottom": 0}),
                                            _help_icon(HELP_TEXTS["zero_baseline"]),
                                        ],
                                        style={"display": "flex", "alignItems": "baseline"},
                                    ),
                                ],
                                style={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                    "gap": "10px",
                                    "padding": "2px 0 2px 6px",
                                },
                            ),
                        ],
                        id="superlet-attr-zero-baseline-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                html.Div(
                                    [
                                        dbc.Label("Band reducer", id="superlet-attr-freq-reduce-label", style={"display": "inline-block"}),
                                        _help_icon(HELP_TEXTS["superlet_attr_freq_reduce"]),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                                style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                            ),
                            html.Div(
                                dmc.SegmentedControl(
                                    id="superlet-attr-freq-reduce",
                                    value=UI_DEFAULTS["superlet_attr_freq_reduce"],
                                    fullWidth=True,
                                    data=[
                                        {"label": "Mean", "value": "mean"},
                                        {"label": "Median", "value": "median"},
                                    ],
                                ),
                                style={"width": "65%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-freq-reduce-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                html.Div(
                                    [
                                        dbc.Label("Curve averaging, m", id="superlet-attr-window-label"),
                                        _help_icon(HELP_TEXTS["superlet_attr_x_window"]),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                                style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                            ),
                            html.Div(
                                dmc.NumberInput(
                                    id="superlet-attr-window-input",
                                    size="xs",
                                    min=0,
                                    step=0.01,
                                    decimalScale=2,
                                    fixedDecimalScale=False,
                                    value=float(UI_DEFAULTS["superlet_attr_x_window_ms"]) * float(UI_DEFAULTS["wavespeed"]) / 2000.0,
                                ),
                                id="superlet-attr-window-container",
                                style={"width": "20%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-window-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                html.Div(
                                    [
                                        dbc.Label("Curve reducer", id="superlet-attr-x-reduce-label", style={"display": "inline-block"}),
                                        _help_icon(HELP_TEXTS["superlet_attr_x_reduce"]),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                                style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                            ),
                            html.Div(
                                dmc.SegmentedControl(
                                    id="superlet-attr-x-reduce",
                                    value=UI_DEFAULTS["superlet_attr_x_reduce"],
                                    fullWidth=True,
                                    data=[
                                        {"label": "Mean", "value": "mean"},
                                        {"label": "Median", "value": "median"},
                                    ],
                                ),
                                style={"width": "65%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-x-reduce-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                [
                                    dbc.Input(id="superlet-attr-band-min-hz", type="number", min=0.001, step="any", value=UI_DEFAULTS["superlet_attr_freq_min_hz"]),
                                    dbc.FormText("Band min, Hz", id="superlet-attr-band-min-label"),
                                ],
                                style={"width": "50%", "display": "inline-block"},
                            ),
                            html.Div(
                                [
                                    dbc.Input(id="superlet-attr-band-max-hz", type="number", min=0.001, step="any", value=UI_DEFAULTS["superlet_attr_freq_max_hz"]),
                                    dbc.FormText("Band max, Hz", id="superlet-attr-band-max-label"),
                                ],
                                style={"width": "50%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-band-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                [
                                    dbc.Input(id="superlet-attr-phase-freq-hz", type="number", min=0.001, step="any", value=UI_DEFAULTS["superlet_attr_phase_freq_hz"]),
                                    dbc.FormText("Phase frequency, Hz", id="superlet-attr-phase-freq-label"),
                                ],
                                style={"width": "50%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-phase-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                dbc.Label("Show band on SLT", id="superlet-attr-band-guides-label"),
                                style={"width": "55%", "display": "inline-block"},
                            ),
                            html.Div(
                                dbc.Switch(id="superlet-attr-show-band-guides-switch", value=UI_DEFAULTS["superlet_attr_show_band_guides"]),
                                style={"width": "45%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-band-guides-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                    dbc.Row(
                        [
                            html.Div(
                                dbc.Label("Show source badge", id="superlet-attr-source-badge-label"),
                                style={"width": "55%", "display": "inline-block"},
                            ),
                            html.Div(
                                dbc.Switch(id="superlet-attr-show-source-badge-switch", value=UI_DEFAULTS["superlet_attr_show_source_badge"]),
                                style={"width": "45%", "display": "inline-block"},
                            ),
                        ],
                        id="superlet-attr-source-badge-row",
                        style={**SETTINGS_ROW_STYLE, "display": "none"},
                    ),
                ],
                withBorder=True,
                radius="md",
                p="sm",
                shadow="xs",
                style={
                    "borderColor": "#E0E7F3",
                    "backgroundColor": "#FCFDFF",
                    "marginTop": "12px",
                    "marginBottom": "6px",
                },
            ),
            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label("Text file time unit", id="time-unit-override-label"),
                                _help_icon(HELP_TEXTS["text_file_time_unit"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "vertical-align": "top"},
                    ),
                    html.Div(
                        dmc.SegmentedControl(
                            id="time-unit-override",
                            value=UI_DEFAULTS["time_unit_override"],
                            fullWidth=True,
                            data=[
                                {"label": "s", "value": "s"},
                                {"label": "ms", "value": "ms"},
                                {"label": "us", "value": "us"},
                            ],
                        ),
                        style={"width": "65%", "display": "inline-block"},
                    ),
                ],
                id="time-unit-row",
                style={**SETTINGS_ROW_STYLE, "display": "none"},
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label("Assumed signal type", id="assumed-signal-type-label"),
                                _help_icon(HELP_TEXTS["assumed_signal_type"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "vertical-align": "top"},
                    ),
                    html.Div(
                        [
                            dbc.FormText(id="assumed-input-summary"),
                            html.Div(id="assumed-input-details"),
                        ],
                        style={"width": "65%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),

            dbc.Row(
                [
                    html.Div(
                        html.Div(
                            [
                                dbc.Label("Integration", id="integration-label"),
                                _help_icon(HELP_TEXTS["integration"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "35%", "display": "inline-block", "vertical-align": "top"},
                    ),
                    html.Div(
                        dmc.SegmentedControl(
                            id="integration-mode",
                            value=UI_DEFAULTS["integration_mode"],
                            fullWidth=True,
                            data=[
                                {"label": "Auto", "value": "Auto"},
                                {"label": "Off", "value": "Off"},
                                {"label": "x1", "value": "x1"},
                                {"label": "x2", "value": "x2"},
                            ],
                        ),
                        style={"width": "65%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),
            dbc.Row(
                [
                    html.Div(
                        [
                            dbc.Input(id="main-plot-width", type="number", min=50, max=100, step=1, value=UI_DEFAULTS["main_plot_width_pct"]),
                            dbc.FormText(translate("Main plot width, %", lang), id="main-plot-width-label"),
                        ],
                        style={"width": "50%", "display": "inline-block"},
                    ),
                    html.Div(
                        [
                            dbc.Input(id="main-plot-height", type="number", min=50, max=1200, step=10, value=UI_DEFAULTS["main_plot_height_px"]),
                            dbc.FormText("Subplot height, px", id="main-plot-height-label"),
                        ],
                        style={"width": "50%", "display": "inline-block"},
                    ),
                ],
                style=SETTINGS_ROW_STYLE,
            ),
            dbc.Row(
                html.Div(
                    dmc.Button(
                        translate("Reset settings to defaults", lang),
                        id="btn-reset-defaults",
                        variant="default",
                        color="gray",
                        fullWidth=True,
                        leftSection=DashIconify(
                            icon="material-symbols-light:settings-backup-restore-rounded",
                            width=22,
                        ),
                        styles={
                            "root": {
                                "backgroundColor": "#FFFFFF",
                                "border": "1px solid #D7DEE8",
                                "color": "#334155",
                            }
                        },
                    ),
                    style={"width": "100%", "display": "inline-block"},
                ),
                style=SETTINGS_ROW_STYLE,
            ),
            dbc.Row(
                html.Div(
                    [
                        html.Div(
                            translate("Advanced settings", lang),
                            id="advanced-settings-label",
                            style={
                                "backgroundColor": "#FFF1F4",
                                "border": "1px solid #F3CCD7",
                                "borderRadius": "8px",
                                "padding": "10px 14px",
                                "fontWeight": 600,
                                "marginTop": "14px",
                                "marginBottom": "8px",
                            },
                        ),
                        html.Div(
                            [
                                        dbc.Row(
                                            html.Div(
                                                dmc.Group(
                                                    [
                                                        DashIconify(
                                                            icon="mdi:translate",
                                                            width=20,
                                                        ),
                                                        dmc.SegmentedControl(
                                                            id="lang-segment",
                                                            value="EN",
                                                            data=[
                                                                {"label": "RU", "value": "RU"},
                                                                {"label": "EN", "value": "EN"},
                                                            ],
                                                            size="xs",
                                                        ),
                                                    ],
                                                    gap="xs",
                                                ),
                                                style={
                                                    "width": "100%",
                                                    "display": "flex",
                                                    "justifyContent": "flex-end",
                                                },
                                            ),
                                            style=SETTINGS_ROW_STYLE,
                                        ),
                                        dmc.Paper(
                                            [
                                                dbc.Row(
                                                    html.Div(
                                                        dmc.Text(
                                                            translate("Signal settings", lang), fw=500, id="signal-settings-label"
                                                        ),
                                                        style={"width": "99%"},
                                                    ),
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Downsampling (factor)", lang), id="downsample-label"),
                                                                    _help_icon(HELP_TEXTS["downsampling"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.NumberInput(
                                                                id="downsample-factor",
                                                                size="xs",
                                                                step=1,
                                                                min=1,
                                                                value=UI_DEFAULTS["downsample_factor"],
                                                            ),
                                                            style={"width": "20%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Checkbox(
                                                                label=translate("Anti-alias filter", lang),
                                                                id="downsample-aa",
                                                                value=UI_DEFAULTS["downsample_aa"],
                                                            ),
                                                            style={"width": "45%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label(translate("Sampling (in/out)", lang), id="sampling-in-out-label"),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dbc.FormText(id="downsample-fs-info"),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label(translate("Factors", lang), id="factors-label"),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dbc.FormText(id="downsample-factor-info"),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    id="downsample-factor-row",
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                            [
                                                                dbc.Label("Integration method"),
                                                                _help_icon(HELP_TEXTS["integration_method"]),
                                                            ],
                                                            style={"display": "flex", "alignItems": "center"},
                                                        ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dbc.Select(
                                                                id="integration-method",
                                                                value=UI_DEFAULTS["integration_method"],
                                                                options=[
                                                                    {"label": "Regularized frequency-domain", "value": "regularized_fd"},
                                                                    {"label": "Time-domain cumulative trapezoid", "value": "cumulative_trapezoid"},
                                                                ],
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label("Low-frequency suppression, Hz"),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.NumberInput(
                                                                id="integration-lowfreq-hz",
                                                                size="xs",
                                                                step=1,
                                                                min=0.1,
                                                                value=UI_DEFAULTS["integration_low_frequency_hz"],
                                                            ),
                                                            style={"width": "20%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    id="integration-lowfreq-row",
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label(
                                                                translate("Convert time to length", lang), id="convert-time-label"
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="length-switch", value=UI_DEFAULTS["length_on"]
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate("Window signal for processing", lang),
                                                                        id="signal-window-switch-label",
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["signal_window"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="signal-window-switch",
                                                                value=UI_DEFAULTS["signal_window_on"],
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate("Right-edge taper, m", lang),
                                                                        id="signal-window-taper-label",
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["signal_window_taper"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.NumberInput(
                                                                id="signal-window-taper-input",
                                                                size="xs",
                                                                min=0,
                                                                step=0.01,
                                                                decimalScale=2,
                                                                fixedDecimalScale=False,
                                                                value=float(UI_DEFAULTS["signal_window_taper_ms"]) * float(UI_DEFAULTS["wavespeed"]) / 2000.0,
                                                            ),
                                                            id="signal-window-taper-container",
                                                            style={"width": "20%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    id="signal-window-taper-row",
                                                    style={**SETTINGS_ROW_STYLE, "display": "none"},
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate("Symmetric padding, m", lang),
                                                                        id="signal-window-padding-label",
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["signal_window_padding"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.NumberInput(
                                                                id="signal-window-padding-input",
                                                                size="xs",
                                                                min=0,
                                                                step=0.01,
                                                                decimalScale=2,
                                                                fixedDecimalScale=False,
                                                                value=float(UI_DEFAULTS["signal_window_padding_ms"]) * float(UI_DEFAULTS["wavespeed"]) / 2000.0,
                                                            ),
                                                            id="signal-window-padding-container",
                                                            style={"width": "20%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    id="signal-window-padding-row",
                                                    style={**SETTINGS_ROW_STYLE, "display": "none"},
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Detrend signal", lang), id="detrend-label"),
                                                                    _help_icon(HELP_TEXTS["detrend"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="detrend-switch",
                                                                value=UI_DEFAULTS["detrend_on"],
                                                                disabled=False,
                                                            ),
                                                            style={
                                                                "width": "10%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Checkbox(
                                                                label=translate(
                                                                    "After amplification",
                                                                    lang,
                                                                ),
                                                                id="detrend-tick",
                                                                value=UI_DEFAULTS["detrend_tick"],
                                                                disabled=False,
                                                            ),
                                                            style={
                                                                "width": "55%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label("Zero baseline"),
                                                                    _help_icon(HELP_TEXTS["zero_baseline"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={
                                                                "width": "35%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="integration-zero-baseline-switch",
                                                                value=UI_DEFAULTS["integration_zero_baseline"],
                                                            ),
                                                            style={
                                                                "width": "50%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate(
                                                                            "Shift signal along time-axis",
                                                                            lang,
                                                                        ), id="shift-label"
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["shift_signal"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={
                                                                "width": "35%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="shift-switch", value=UI_DEFAULTS["shift_on"]
                                                            ),
                                                            style={
                                                                "width": "65%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate("Flip signal polarity", lang)
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["flip_polarity"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={
                                                                "width": "35%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="flip-polarity-switch", value=UI_DEFAULTS["flip_polarity"]
                                                            ),
                                                            style={
                                                                "width": "65%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                            ],
                                            withBorder=True,
                                            radius="md",
                                            p="sm",
                                            shadow="xs",
                                            style={
                                                "borderColor": "#DCE6F5",
                                                "backgroundColor": "#F4F8FF",
                                                "marginBottom": "10px",
                                            },
                                        ),
                                        dmc.Paper(
                                            [
                                                dbc.Row(
                                                    html.Div(
                                                        dmc.Text("Visualization", fw=500, id="visualization-settings-label"),
                                                        style={"width": "99%"},
                                                    ),
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Multiple reflections, m", lang), id="multiple-reflections-label"),
                                                                    _help_icon(HELP_TEXTS["multiple_reflections"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "55%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Input(
                                                                id="multiple-reflections", type="number", min=0, step=0.01, value=UI_DEFAULTS["reflection"]
                                                            ),
                                                            style={"width": "20%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(
                                                                        translate("Reverse y-axis", lang), id="reverse-axis-label"
                                                                    ),
                                                                    _help_icon(HELP_TEXTS["reverse_y_axis"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="reverse-axis-switch", value=UI_DEFAULTS["reverse_axis"]
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Show markers", lang), id="show-markers-label"),
                                                                    _help_icon(HELP_TEXTS["show_markers"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="show-markers-switch", value=UI_DEFAULTS["show_markers"]
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Simplify signal plot", lang), id="simplify-plot-label"),
                                                                    _help_icon(HELP_TEXTS["simplify_plot"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="simplify-plot-switch", value=UI_DEFAULTS["simplify_plot"]
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label("Display subplots horizontally", id="horizontal-subplots-label"),
                                                            style={"width": "50%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="horizontal-subplots-switch",
                                                                value=UI_DEFAULTS["display_subplots_horizontally"],
                                                            ),
                                                            style={"width": "50%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label("Y-axis exponent format", id="y-axis-exponent-format-label"),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.SegmentedControl(
                                                                id="y-axis-exponent-format",
                                                                value=UI_DEFAULTS["y_axis_exponent_format"],
                                                                fullWidth=True,
                                                                data=[
                                                                    {"label": "None", "value": "none"},
                                                                    {"label": "E", "value": "E"},
                                                                    {"label": "power", "value": "power"},
                                                                    {"label": "B", "value": "B"},
                                                                    {"label": "Si", "value": "SI"},
                                                                ],
                                                            ),
                                                            style={"width": "65%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                            ],
                                            withBorder=True,
                                            radius="md",
                                            p="sm",
                                            shadow="xs",
                                            style={
                                                "borderColor": "#E8E1F6",
                                                "backgroundColor": "#FBF8FF",
                                                "marginBottom": "10px",
                                            },
                                        ),
                                        dmc.Paper(
                                            [
                                                dbc.Row(
                                                    html.Div(
                                                        html.Div(
                                                            [
                                                                dmc.Text(
                                                                    translate("Advanced filter settings", lang),
                                                                    fw=500,
                                                                    id="advanced-filter-settings-label",
                                                                ),
                                                                _help_icon(HELP_TEXTS["advanced_filter_settings"]),
                                                            ],
                                                            style={"display": "flex", "alignItems": "center"},
                                                        ),
                                                        style={"width": "99%"},
                                                    ),
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label(
                                                                translate("Forward-backward filtering", lang),
                                                                id="forward-backward-filter-switch-label",
                                                            ),
                                                            style={
                                                                "width": "35%",
                                                                "display": "inline-block",
                                                                "vertical-align": "top",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="forward-backward-filter-switch",
                                                                value=UI_DEFAULTS["forward_backward_filter"],
                                                            ),
                                                            style={
                                                                "width": "65%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            dbc.Label(
                                                                translate("Show filter frequency response", lang),
                                                                id="filter-draw-switch-label",
                                                            ),
                                                            style={
                                                                "width": "35%",
                                                                "display": "inline-block",
                                                                "vertical-align": "top",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dbc.Switch(
                                                                id="filter-draw-switch",
                                                                value=UI_DEFAULTS["filter_draw"],
                                                            ),
                                                            style={
                                                                "width": "65%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                            ],
                                            withBorder=True,
                                            radius="md",
                                            p="sm",
                                            shadow="xs",
                                            style={
                                                "borderColor": "#DDEBDC",
                                                "backgroundColor": "#F4FBF3",
                                                "marginBottom": "10px",
                                            },
                                        ),
                                        dmc.Paper(
                                            [
                                                dbc.Row(
                                                    html.Div(
                                                        dmc.Text(
                                                            translate("SLT settings", lang), fw=500, id="slt-settings-label"
                                                        ),
                                                        style={"width": "99%"},
                                                    ),
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("SLT mode", lang), id="slt-mode-label", style={"display": "inline-block"}),
                                                                    _help_icon(HELP_TEXTS["slt_mode"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.SegmentedControl(
                                                                id="slt-mode",
                                                                value=UI_DEFAULTS["slt_mode"],
                                                                fullWidth=True,
                                                                data=[
                                                                    {"label": translate("Fixed", lang), "value": "fixed"},
                                                                    {"label": translate("Adaptive", lang), "value": "adaptive"},
                                                                ],
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Cycle scaling", lang), id="cycle-scaling-label", style={"display": "inline-block"}),
                                                                    _help_icon(HELP_TEXTS["cycle_scaling"]),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.SegmentedControl(
                                                                id="superlet-set-mode",
                                                                value=UI_DEFAULTS["superlet_set_mode"],
                                                                fullWidth=True,
                                                                data=[
                                                                    {"label": translate("Multiplicative", lang), "value": "multiplicative"},
                                                                    {"label": translate("Additive", lang), "value": "additive"},
                                                                ],
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            [
                                                                dbc.Input(id="k_sd", type="number", min=0.1, step=0.1, value=UI_DEFAULTS["k_sd"]),
                                                                html.Div([dbc.FormText(["k", html.Sub("sd"), " (Gaussian width)"], id="ksd-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["k_sd"])], style={"display": "flex", "alignItems": "center"}),
                                                            ],
                                                            style={"width": "50%", "display": "inline-block"},
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Input(id="support_sd", type="number", min=0.1, step=0.1, value=UI_DEFAULTS["support_sd"]),
                                                                html.Div([dbc.FormText(translate("support_sd", lang), id="support-sd-label", style={"display": "inline-block"}), _help_icon(HELP_TEXTS["support_sd"])], style={"display": "flex", "alignItems": "center"}),
                                                            ],
                                                            style={"width": "50%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            html.Div(
                                                                [
                                                                    dbc.Label(translate("Phase mode", lang), id="slt-phase-handling-label", style={"display": "inline-block"}),
                                                                    _help_icon(
                                                                        html.Span(
                                                                            [
                                                                                "How phase is combined across superlet orders. ",
                                                                                html.B("Standard"),
                                                                                " follows the original superlet combination. ",
                                                                                html.B("Unwrapped"),
                                                                                " first makes phase continuous across orders, then combines the orders. ",
                                                                                html.B("Circular"),
                                                                                " combines phase directions as weighted unit vectors in the complex plane. This mainly affects Re, Im and Phase.",
                                                                            ]
                                                                        )
                                                                    ),
                                                                ],
                                                                style={"display": "flex", "alignItems": "center"},
                                                            ),
                                                            style={"width": "35%", "display": "inline-block", "verticalAlign": "middle"},
                                                        ),
                                                        html.Div(
                                                            dmc.SegmentedControl(
                                                                id="superlet-phase-combination",
                                                                value=UI_DEFAULTS["superlet_phase_combination"],
                                                                fullWidth=True,
                                                                data=[
                                                                    {"label": "Standard", "value": "standard"},
                                                                    {"label": "Unwrapped", "value": "unwrapped"},
                                                                    {"label": "Circular", "value": "circular"},
                                                                ],
                                                            ),
                                                            style={"width": "65%", "display": "inline-block"},
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            [
                                                                dbc.Switch(id="superlet-coi-mask-switch", value=UI_DEFAULTS["superlet_coi_mask_on"]),
                                                                html.Div(
                                                                    [
                                                                        dbc.Label(translate("Edge mask (COI)", lang), id="superlet-coi-mask-label", style={"marginBottom": 0}),
                                                                        _help_icon(HELP_TEXTS["superlet_coi_mask"]),
                                                                    ],
                                                                    style={"display": "flex", "alignItems": "baseline"},
                                                                ),
                                                            ],
                                                            style={
                                                                "display": "inline-flex",
                                                                "alignItems": "center",
                                                                "gap": "10px",
                                                                "padding": "2px 0 2px 6px",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                            ],
                                            withBorder=True,
                                            radius="md",
                                            p="sm",
                                            shadow="xs",
                                            style={
                                                "borderColor": "#DDE6F0",
                                                "backgroundColor": "#FAFBFD",
                                                "marginBottom": "10px",
                                            },
                                        ),
                                        dmc.Paper(
                                            [
                                                dbc.Row(
                                                    html.Div(
                                                        html.Div(
                                                            [
                                                                dmc.Text(
                                                                    translate(
                                                                        "Local extrema settings", lang
                                                                    ),
                                                                    fw=500,
                                                                    id="local-extrema-label",
                                                                ),
                                                                _help_icon(HELP_TEXTS["local_extrema_settings"]),
                                                            ],
                                                            style={"display": "flex", "alignItems": "center"},
                                                        ),
                                                        style={"width": "99%"},
                                                    ),
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                                dbc.Row(
                                                    [
                                                        html.Div(
                                                            [
                                                                dbc.Input(
                                                                    id="peak-distance",
                                                                    type="number",
                                                                    min=1,
                                                                    step=1,
                                                                    value=UI_DEFAULTS["peak_distance"],
                                                                ),
                                                                dbc.FormText(
                                                                    translate(
                                                                        "Min. distance between peaks, in samples",
                                                                        lang,
                                                                    ), id="peak-distance-label"
                                                                ),
                                                            ],
                                                            style={
                                                                "width": "25%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Input(
                                                                    id="peak-width-min",
                                                                    type="number",
                                                                    min=1,
                                                                    step=1,
                                                                    value=UI_DEFAULTS["peak_width_min"],
                                                                ),
                                                                dbc.FormText(
                                                                    translate(
                                                                        "Min. width of peaks, in samples",
                                                                        lang,
                                                                    ), id="peak-width-min-label"
                                                                ),
                                                            ],
                                                            style={
                                                                "width": "25%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Input(
                                                                    id="peak-width-max",
                                                                    type="number",
                                                                    min=1,
                                                                    step=1,
                                                                    value=UI_DEFAULTS["peak_width_max"],
                                                                ),
                                                                dbc.FormText(
                                                                    translate(
                                                                        "Max. width of peaks, in samples",
                                                                        lang,
                                                                    ), id="peak-width-max-label"
                                                                ),
                                                            ],
                                                            style={
                                                                "width": "25%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Input(
                                                                    id="peak-prominence-min",
                                                                    type="number",
                                                                    min=0,
                                                                    step=0.01,
                                                                    value=UI_DEFAULTS["peak_prominence_min"],
                                                                ),
                                                                dbc.FormText(
                                                                    translate("Min. prominence of peaks", lang), id="peak-prominence-label"
                                                                ),
                                                            ],
                                                            style={
                                                                "width": "25%",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style=SETTINGS_ROW_STYLE,
                                                ),
                                            ],
                                            withBorder=True,
                                            radius="md",
                                            p="sm",
                                            shadow="xs",
                                            style={
                                                "borderColor": "#EBCDE5",
                                                "backgroundColor": "#FFF4FB",
                                                "marginBottom": "10px",
                                            },
                                        ),
                            ],
                        ),
                    ],
                    style={"width": "100%"},
                ),
                style=SETTINGS_ROW_STYLE,
            ),
        ],
        style={"padding": 5},
        className="mb-3",
    )

def _controls_filter(lang: str) -> html.Div:
    return html.Div(
        dmc.Paper(
            [
                dbc.Row(
                    html.Div(
                        html.Div(
                            [
                                dmc.Text(
                                    translate("Filter settings", lang),
                                    fw=500,
                                    id="filter-settings-label",
                                ),
                                _help_icon(HELP_TEXTS["filter_settings"]),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        style={"width": "100%"},
                    ),
                    style=SETTINGS_ROW_STYLE,
                ),
                dbc.Row(
                    [
                        html.Div(
                            [
                                dbc.Switch(id="filter-switch", value=UI_DEFAULTS["filter_switch"]),
                                dbc.Label(
                                    translate("Enable filter", lang),
                                    id="enable-filter-label",
                                    style={"marginBottom": 0},
                                ),
                            ],
                            style={
                                "width": "33.33%",
                                "display": "inline-flex",
                                "alignItems": "center",
                                "gap": "10px",
                                "padding": "2px 0 2px 6px",
                            },
                        ),
                        html.Div(
                            dbc.Checkbox(
                                label=translate("Apply before amplification", lang),
                                id="filter-tick",
                                value=UI_DEFAULTS["filter_tick"],
                            ),
                            style={"width": "33.33%", "display": "inline-block", "paddingTop": "9px"},
                        ),
                        html.Div(
                            [
                                dbc.Label(
                                    translate("Autozoom frequency axis", lang),
                                    id="autozoom-frequency-axis-label",
                                    style={"marginBottom": 0},
                                ),
                                dbc.Switch(
                                    id="spectrum-autozoom-x",
                                    value=UI_DEFAULTS["spectrum_autozoom_x"],
                                ),
                            ],
                            style={
                                "width": "33.33%",
                                "display": "inline-flex",
                                "alignItems": "center",
                                "justifyContent": "space-between",
                                "padding": "8px 6px 8px 6px",
                            },
                        ),
                    ],
                    style=SETTINGS_ROW_STYLE,
                ),
                dbc.Row(
                    [
                        html.Div(
                            [
                                dbc.Input(
                                    id="filter-cutoff_lp", type="number", min=1, step=1, value=UI_DEFAULTS["filter_cutoff_lp"]
                                ),
                                dbc.FormText(translate("Low-pass filter cutoff frequency, Hz", lang), id="low-pass-label"),
                            ],
                            style={"width": "34%", "display": "inline-block"},
                        ),
                        html.Div(
                            [
                                dbc.Input(
                                    id="filter-cutoff_hp", type="number", min=1, step=1, value=UI_DEFAULTS["filter_cutoff_hp"]
                                ),
                                dbc.FormText(translate("High-pass filter cutoff frequency, Hz", lang), id="high-pass-label"),
                            ],
                            style={"width": "33%", "display": "inline-block"},
                        ),
                        html.Div(
                            [
                                dbc.Input(id="filter-order", type="number", min=1, max=100, step=1, value=UI_DEFAULTS["filter_order"]),
                                dbc.FormText(translate("Filter order", lang), id="filter-order-label"),
                            ],
                            style={"width": "33%", "display": "inline-block"},
                        ),
                    ],
                    style=SETTINGS_ROW_STYLE,
                ),
                html.Div(
                    dbc.Row(
                        html.Div(
                            dmc.Text(
                                translate("Amplitude spectrum", lang),
                                fw=500,
                                id="amplitude-spectrum-label",
                            ),
                            style={"width": "100%"},
                        ),
                        style=SETTINGS_ROW_STYLE,
                    ),
                    id="amplitude-spectrum-label-wrap",
                    style={"display": "none", "marginTop": "18px"},
                ),
                html.Div(
                    id="spectrum_plot",
                    style={"width": "100%", "display": "block"},
                ),
                html.Div(
                    dmc.Button(
                        translate("Save spectrum plot as image", lang),
                        id="btn-save-spectrum-plot",
                        variant="default",
                        color="gray",
                        fullWidth=True,
                        leftSection=DashIconify(
                            icon="material-symbols-light:download-rounded",
                            width=22,
                        ),
                        styles={
                            "root": {
                                "backgroundColor": "#FFFFFF",
                                "border": "1px solid #D7DEE8",
                                "color": "#334155",
                            }
                        },
                    ),
                    id="btn-save-spectrum-plot-wrap",
                    style={"display": "none", "marginTop": "10px"},
                ),
            ],
            withBorder=True,
            radius="md",
            p="sm",
            shadow="xs",
            style={
                "borderColor": "#E5E7EB",
                "backgroundColor": "#FFFFFF",
                "marginBottom": "10px",
            },
        ),
        style={"width": "100%", "display": "block"},
    )

def _graphs(lang: str) -> html.Div:
    return html.Div(
        [
            dbc.Row(
                html.Div(
                    [
                        html.Div(
                            style={"width": "100%", "display": "inline-block"},
                            id="time_plot",
                        ),
                        html.Div(
                            dmc.Button(
                                translate("Save plot as image", lang),
                                id="btn-save-time-plot",
                                variant="default",
                                color="gray",
                                fullWidth=True,
                                leftSection=DashIconify(
                                    icon="material-symbols-light:download-rounded",
                                    width=22,
                                ),
                                styles={
                                    "root": {
                                        "backgroundColor": "#FFFFFF",
                                        "border": "1px solid #D7DEE8",
                                        "color": "#334155",
                                    }
                                },
                            ),
                            id="btn-save-time-plot-wrap",
                            style={"display": "none", "marginTop": "4px", "marginBottom": "8px"},
                        ),
                    ],
                    style={"width": "100%", "display": "inline-block"},
                )
            ),
            dbc.Row(
                html.Div(
                    _controls_filter(lang),
                    style={"width": "100%", "display": "block"},
                )
            ),
        ],
        style={"padding": 5},
        className="mb-3",
    )

def build_layout(lang: str = LAYOUT_LANG_DEFAULT) -> html.Div:
    return dmc.MantineProvider(
        dmc.AppShell(
            [   dmc.NotificationContainer(id="notify", position="top-right", limit=3),
                dmc.AppShellNavbar(
                    children=dmc.ScrollArea(
                        type="scroll",
                        scrollHideDelay=300,
                        scrollbarSize=8,
                        children=_controls(lang),
                    ),
                    pl=30,
                    pr=30,
                    pt=10,
                ),
                dmc.AppShellMain(children=_graphs(lang), ml=30, mr=30, mt=10),
            ],
            zIndex=1400,
            navbar={"width": "40%"},
        )
    )






