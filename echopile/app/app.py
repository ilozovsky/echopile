from __future__ import annotations

from pathlib import Path

from dash import Dash, _dash_renderer
import dash_bootstrap_components as dbc
import plotly.io as pio

from ..config import APP_TITLE, PLOTLY_TEMPLATE
from ..ui_components import build_layout
from .profiles import resolve_profile


def build_app(profile=None):
    profile_obj = resolve_profile(profile)
    pio.templates.default = PLOTLY_TEMPLATE  # use plain Plotly (no theme)
    package_dir = Path(__file__).resolve().parents[1]
    app = Dash(
        external_stylesheets=[dbc.themes.JOURNAL],
        assets_folder=str(package_dir / 'assets'),
    )
    app._echopile_profile = profile_obj.name
    app.title = APP_TITLE
    app._favicon = 'favicon.ico'
    _dash_renderer._set_react_version('18.2.0')
    app.layout = build_layout()
    # Import after app/layout exist so Dash callback decorators can register.
    from .callbacks import handlers  # noqa: F401
    return app
