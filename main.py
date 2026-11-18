"""
main.py — Financial Markets Toolkit entry point.

Run with:  streamlit run main.py

Layers
  navigation.py  page registry (sections, slugs, icons)
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
    initial_sidebar_state="auto",  # desktop: top nav; phones: nav drawer starts closed
)

import navigation  # noqa: E402
from ui.components import inject_styles, page_footer  # noqa: E402

ASSETS = Path(__file__).parent / "assets"

inject_styles()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))
nav = st.navigation(navigation.build(), position="top")
nav.run()

page_footer("Markets Toolkit · Python, Streamlit, NumPy, SciPy, Plotly. "
            "Prices are indicative and for education only; not investment advice.")
