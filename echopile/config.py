"""Central configuration for echopile."""

from __future__ import annotations
from typing import Dict, List, Tuple

# App
APP_TITLE: str = "echopile | Pile Integrity Analysis"
LAYOUT_LANG_DEFAULT: str = "EN"
DEBUG: bool = False
PLOTLY_TEMPLATE: str = "none"

# Upload limits
MAX_UPLOAD_FILE_MB: int = 5
MAX_UPLOAD_TOTAL_MB: int = 25
MAX_UPLOAD_FILE_BYTES: int = MAX_UPLOAD_FILE_MB * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES: int = MAX_UPLOAD_TOTAL_MB * 1024 * 1024

# Sizing
SPECTRUM_PLOT_HEIGHT_PX: int = 300

# Styling
LINECOLOR_TIMEPLOT: str = "black"
ALPHA_TRACE: float = 0.5

SETTINGS_ROW_STYLE: Dict[str, object] = {
    "padding-top": "5px",
    "padding-bottom": "5px",
    "padding-left": "5px",
    "padding-right": "5px",
}

SLIDER_SETTINGS_ROW_STYLE: Dict[str, object] = {
    **SETTINGS_ROW_STYLE,
    "display": "flex",
    "alignItems": "center",
}

DMC_SLIDER_STYLES: Dict[str, Dict[str, object]] = {
    "trackContainer": {"height": "3px"},
    "track": {"height": "3px", "backgroundColor": "#E7ECF2"},
    "bar": {"height": "3px", "backgroundColor": "#8FD8FF"},
    "thumb": {
        "width": "14px",
        "height": "14px",
        "border": "2px solid #8FD8FF",
        "backgroundColor": "#FFFFFF",
    },
    "mark": {
        "width": "5px",
        "height": "5px",
        "border": "1px solid #E1E6EE",
        "backgroundColor": "#FFFFFF",
        "marginTop": "-1px",
    },
    "markFilled": {
        "border": "1px solid #8FD8FF",
        "backgroundColor": "#FFFFFF",
    },
    "markLabel": {"fontSize": "12px", "color": "#8A94A3", "marginTop": "6px"},
    "label": {
        "fontSize": "12px",
        "backgroundColor": "#7B8088",
        "color": "#FFFFFF",
        "padding": "4px",
        "lineHeight": "1",
        "zIndex": 50,
    },
}

DMC_SLIDER_WRAPPER_STYLE: Dict[str, object] = {
    "padding": "2px 28px 20px 28px",
    "overflow": "visible",
}

# Palettes
LIST_COLORS: Tuple[str, ...] = (
    "#0C0908", "#2A3166", "#5626C4", "#10567E", "#C81D25", "#D56C2C", "#00AC6B",
    "#3CBCC3", "#F07E74", "#7F8688", "#0D9EDF", "#5DAA68", "#B89F5D", "#FCC133",
    "#eb4a51", "#0D9EDF", "#FCC133", "#0049FF", "#7F8688", "#5DAA68", "#B89F5D",
    "#5626C4", "#61082B", "#632695", "#AD4328", "#56642A", "#259B9A", "#0D9EDF",
    "#FCC133", "#0049FF", "#e60049", "#0bb4ff", "#50e991", "#e6d800", "#9b19f5",
    "#ffa300", "#dc0ab4", "#b3d4ff", "#00bfa0", "#2A3166", "#10567E", "#00AC6B",
    "#eb4a51", "#0D9EDF", "#FCC133", "#0049FF", "#7F8688", "#5DAA68", "#B89F5D",
    "#5626C4", "#61082B", "#632695", "#AD4328", "#56642A", "#259B9A", "#0D9EDF",
    "#FCC133", "#0049FF", "#e60049", "#0bb4ff", "#50e991", "#e6d800", "#9b19f5",
    "#ffa300", "#dc0ab4", "#b3d4ff",
)

COLORSCALE_PHASE: List[List[object]] = [
    # Wrapped phase map for [-180, 180].
    # Phase zero is intentionally narrow and bright.
    # The wrapped ends stay muted so they do not compete with the zero line.
    [0.00, "#67596f"],
    [0.07, "#314f7d"],
    [0.20, "#2e7fd1"],
    [0.38, "#67d7f0"],
    [0.492, "#eefcff"],
    [0.4985, "#fbfeff"],
    [0.50, "#ffffff"],
    [0.5015, "#fffdfb"],
    [0.508, "#fff2eb"],
    [0.62, "#ffb08a"],
    [0.80, "#ef6a6a"],
    [0.93, "#8b546c"],
    [1.00, "#67596f"],
]

CUSTOM_CMAP_COLORS: Tuple[Tuple[float, float, float], ...] = (
    (105/255, 34/255, 141/255),
    (13/255, 20/255, 101/255),
    (43/255, 72/255, 145/255),
    (105/255, 175/255, 207/255),
    (153/255, 255/255, 255/255),
    (188/255, 221/255, 122/255),
    (254/255, 255/255, 110/255),
    (255/255, 183/255, 48/255),
    (255/255, 125/255, 86/255),
    (171/255, 18/255, 18/255),
    (85/255, 23/255, 6/255),
)


