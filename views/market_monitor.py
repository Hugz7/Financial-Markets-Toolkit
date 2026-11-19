"""views/market_monitor.py — Live dashboard: ticker tape, S&P 500 spotlight,
cross-asset tiles with sparklines, leaders & laggards, and the week's top stories."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.market_data import (HORIZONS, WATCHLIST, changes, fetch_watchlist, format_price,
                                  nyse_status, sp500_history)
from services.news import fetch_top_stories, time_ago
from ui.components import (Stat, callout, chart, empty_state, live_status, news_grid,
                           page_header, quote_tiles, section, stat_grid, ticker_tape)
from ui.formatting import num
from ui.theme import C, rgba

RANGES = {"1M": 21, "3M": 63, "6M": 126, "YTD": None, "1Y": 252, "5Y": 1260}


def render():
    page_header(
        "Market Monitor",
        "The S&P 500, a cross-asset snapshot and the week's top business stories. Quotes refresh every minute.",
        eyebrow="Markets",
    )
    _live_strip()
    _sp500_spotlight()
    _cross_asset()
    _top_stories()


def _rows() -> list[dict]:
    hist = fetch_watchlist(tuple(t.symbol for t in WATCHLIST))
    rows = []
    for t in WATCHLIST:
        s = hist.get(t.symbol, pd.Series(dtype=float))
        last = float(s.iloc[-1]) if len(s) else float("nan")
        rows.append({"t": t, "series": s, "last": last, "chg": changes(s) if len(s) > 1 else
                     {k: float("nan") for k in HORIZONS}})
    return rows


# ── Live strip: session status + ticker tape (re-runs on its own every 60 s) ──

@st.fragment(run_every="60s")
def _live_strip():
    rows = _rows()
    have_data = any(r["last"] == r["last"] for r in rows)
    is_open, clock = nyse_status()
    top_l, top_r = st.columns([4, 1], vertical_alignment="center")
    with top_l:
        live_status(is_open, clock, dt.datetime.now().strftime("%H:%M:%S"))
    if top_r.button("Refresh", icon=":material/refresh:", width="stretch", key="mm_refresh"):
        fetch_watchlist.clear()
        sp500_history.clear()
        fetch_top_stories.clear()
        st.rerun(scope="app")

    if not have_data:
        callout("Yahoo Finance did not return any prices. Check the internet connection, then press Refresh.",
                title="Live market data unavailable", tone="warn")
        return
    ticker_tape({"label": r["t"].label, "price_str": format_price(r["last"], r["t"].symbol),
                 "pct": r["chg"]["1D"]} for r in rows)


# ── Cross-asset tiles + leaders & laggards (re-runs on its own every 60 s) ───

@st.fragment(run_every="60s")
def _cross_asset():
    rows = _rows()
    if not any(r["last"] == r["last"] for r in rows):
        return
    section("Cross-asset", "Equities, volatility, rates, FX, commodities and crypto")
    horizon = st.segmented_control("Horizon", list(HORIZONS), default="1D", key="mm_horizon",
                                   label_visibility="collapsed") or "1D"
    quote_tiles({"label": r["t"].label, "symbol": r["t"].symbol,
                 "price_str": format_price(r["last"], r["t"].symbol),
                 "pct": r["chg"][horizon], "horizon": horizon,
                 "spark": [float(v) for v in r["series"].tail(22)]} for r in rows)

    ranked = sorted((r for r in rows if r["chg"][horizon] == r["chg"][horizon]),
                    key=lambda r: r["chg"][horizon])
    if ranked:
        vals = [r["chg"][horizon] for r in ranked]
        fig = go.Figure(go.Bar(
            x=vals, y=[r["t"].label for r in ranked], orientation="h",
            marker=dict(color=[C.pos if v >= 0 else C.neg for v in vals], cornerradius=6),
            text=[f"{v:+.2f}%" for v in vals], textposition="outside", cliponaxis=False,
            textfont=dict(color=C.text_2, size=11),
            hovertemplate="<b>%{y}</b><br>%{x:+.2f}%<extra></extra>",
        ))
        fig.update_layout(hovermode="closest", showlegend=False, bargap=0.35,
                          xaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor=C.axis),
                          yaxis=dict(showgrid=False))
        chart(fig, height=430, title=f"Leaders and laggards · {horizon}")


# ── S&P 500 spotlight ─────────────────────────────────────────────────────────

def _sp500_spotlight():
    df, source = sp500_history()
    section("S&P 500", "The benchmark for US large caps")
    if df is None:
        empty_state("S&P 500 history unavailable",
                    "It loads from Yahoo Finance and is cached locally after the first successful download.")
        return
    if source == "cache":
        callout("Showing the last downloaded S&P 500 history; live data is unavailable right now.", tone="neutral")

    rng = st.segmented_control("Range", list(RANGES), default="1Y", key="mm_range",
                               label_visibility="collapsed") or "1Y"
    close = df["Close"]
    if rng == "YTD":
        view = close[close.index >= pd.Timestamp(close.index[-1].year, 1, 1)]
    else:
        view = close.tail(RANGES[rng] + 1)
    view = view if len(view) > 1 else close.tail(2)

    last, first = float(view.iloc[-1]), float(view.iloc[0])
    chg = (last / first - 1) * 100
    year = close.tail(252)
    hi52, lo52 = float(year.max()), float(year.min())
    dd = (last / hi52 - 1) * 100
    rets = np.log(close).diff().tail(21).dropna()
    rv = float(rets.std() * np.sqrt(252) * 100) if len(rets) > 5 else float("nan")
    day = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100

    stat_grid([
        Stat("Level", num(last, 2), delta=day, delta_fmt="{:+.2f}% today"),
        Stat(f"Change · {rng}", f"{chg:+.2f}%", tone="pos" if chg >= 0 else "neg"),
        Stat("52-week high", num(hi52, 0), hint=f"{dd:+.1f}% from high"),
        Stat("52-week low", num(lo52, 0), hint=f"{(last / lo52 - 1) * 100:+.1f}% above low"),
        Stat("Realised vol · 1M", f"{rv:.1f}%" if rv == rv else "—", hint="annualised, daily closes"),
    ], columns=5)

    col = C.pos if chg >= 0 else C.neg
    lo, hi = float(view.min()), float(view.max())
    pad = (hi - lo) * 0.08 or 1
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=view.index, y=view.values, mode="lines", name="S&P 500",
        line=dict(color=col, width=2.4), fill="tozeroy", fillcolor=rgba(col, 0.10),
        hovertemplate="%{x|%d %b %Y}<br><b>%{y:,.2f}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[view.index[-1]], y=[last], mode="markers", showlegend=False, hoverinfo="skip",
        marker=dict(size=11, color=col, line=dict(width=3, color=C.bg)),
    ))
    fig.add_hline(y=first, line_dash="dot", line_color=C.axis, line_width=1)
    fig.update_layout(showlegend=False, hovermode="x",
                      yaxis=dict(range=[lo - pad, hi + pad], tickformat=",.0f", side="right"),
                      xaxis=dict(showgrid=False))
    chart(fig, height=420, key=f"sp500_{rng}")


# ── Top stories ───────────────────────────────────────────────────────────────

def _top_stories():
    section("Top stories of the week", "Ranked by coverage across The New York Times, The Guardian and the BBC")
    with st.spinner("Loading the week's stories…"):
        stories = fetch_top_stories()
    if not stories:
        empty_state("No stories to show",
                    "The news feeds could not be reached. Check the internet connection, then press Refresh.")
        return
    news_grid({
        "source": s.lead.outlet, "title": s.lead.title, "link": s.lead.link,
        "summary": s.lead.summary, "img": s.lead.img, "age": time_ago(s.lead.pub),
        "also": [o for o in s.outlets if o != s.lead.outlet],
    } for s in stories)
