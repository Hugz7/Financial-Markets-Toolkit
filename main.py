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
from services.market_data import sp500_history, weekly_ohlc  # noqa: E402
from ui.components import inject_styles, page_footer  # noqa: E402


def market_art() -> dict:
    """The site's design curve is the real S&P 500: last year of daily closes behind
    every title, last two years of weekly candles along the bottom. Falls back to the
    procedural artwork when no data (live or cached) is available."""
    df, _source = sp500_history()
    if df is None:
        return {}
    year = df["Close"].tail(252)
    step = max(1, len(year) // 160)
    series = tuple(round(float(v), 2) for v in year.iloc[::step])
    if series[-1] != round(float(year.iloc[-1]), 2):
        series += (round(float(year.iloc[-1]), 2),)
    chg = (year.iloc[-1] / year.iloc[0] - 1) * 100
    label = f"S&P 500 · 1Y {chg:+.1f}% · {year.iloc[-1]:,.0f}"
    candles = tuple(tuple(round(float(x), 2) for x in row)
                    for row in weekly_ohlc(df)[["Open", "High", "Low", "Close", "Volume"]].itertuples(index=False))
    return {"candles": candles, "hero_series": series, "hero_label": label}

ASSETS = Path(__file__).parent / "assets"

inject_styles(**market_art())
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))
nav = st.navigation(navigation.build(), position="top")
nav.run()

page_footer("Markets Toolkit · Python, Streamlit, NumPy, SciPy, Plotly. "
            "Prices are indicative and for education only; not investment advice.")
