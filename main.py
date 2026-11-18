"""
main.py — Financial Markets Toolkit entry point.

Run with:  streamlit run main.py

Layers
  models/    pure pricing maths (no Streamlit, no I/O) — unit-tested
  services/  data access: market data, news, persistence (cached)
  ui/        design tokens, Plotly template, reusable components
  views/     one module per page, each exposing render()
"""

from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Markets Toolkit",
    page_icon=":material/candlestick_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.components import inject_styles, sidebar_footer  # noqa: E402
from views import (  # noqa: E402
    exotic_pricer, forwards, market_monitor, monte_carlo, payoff_analyzer,
    roadmap, swaps, vol_smile, yield_curve,
)


def _page(module, title: str, icon: str, slug: str, default: bool = False) -> st.Page:
    return st.Page(module.render, title=title, icon=f":material/{icon}:",
                   url_path=slug, default=default)


PAGES = {
    "Markets": [
        _page(market_monitor, "Market Monitor", "monitoring", "markets", default=True),
    ],
    "Options": [
        _page(payoff_analyzer, "Payoff Analyzer", "stacked_line_chart", "payoff"),
        _page(exotic_pricer, "Exotic Pricer", "function", "exotics"),
        _page(vol_smile, "Volatility Smile", "ssid_chart", "vol-smile"),
    ],
    "Rates & Forwards": [
        _page(yield_curve, "Yield Curve", "show_chart", "yield-curve"),
        _page(swaps, "Swaps", "swap_horiz", "swaps"),
        _page(forwards, "Forwards", "trending_up", "forwards"),
    ],
    "Simulation": [
        _page(monte_carlo, "Monte Carlo", "scatter_plot", "monte-carlo"),
    ],
    "Project": [
        _page(roadmap, "Roadmap", "checklist", "roadmap"),
    ],
}

ASSETS = Path(__file__).parent / "assets"

inject_styles()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))
nav = st.navigation(PAGES, position="sidebar", expanded=True)
nav.run()

with st.sidebar:
    sidebar_footer("Python · Streamlit · NumPy · SciPy · Plotly\nPrices are indicative; not investment advice.")
