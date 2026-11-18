"""views/market_monitor.py — Live market snapshot and financial news."""

import datetime as dt

import streamlit as st

from services.market_data import WATCHLIST, fetch_quotes, format_price
from services.news import NEWS_SOURCES, fetch_news, time_ago
from ui.components import callout, empty_state, news_grid, page_header, quote_tiles, section


def render():
    page_header(
        "Market Monitor",
        "Cross-asset snapshot and the latest financial headlines from the past 48 hours.",
        eyebrow="Markets",
    )

    left, right = st.columns([4, 1], vertical_alignment="bottom")
    left.caption(f"Quotes refresh every 2 min · news every 5 min · "
                 f"{dt.datetime.now().strftime('%d %b %Y, %H:%M')}")
    if right.button("Refresh", icon=":material/refresh:", width="stretch"):
        fetch_quotes.clear()
        fetch_news.clear()
        st.rerun()

    # ── Quotes ──
    section("Snapshot", "Last close · change vs previous close")
    with st.spinner("Loading quotes…"):
        quotes = fetch_quotes(tuple(t.symbol for t in WATCHLIST))
    if all(q["price"] != q["price"] for q in quotes.values()):
        callout("Yahoo Finance did not return any quotes. Check the network connection, "
                "then press Refresh.", title="Live quotes unavailable", tone="warn")
    quote_tiles(
        {"label": t.label, "symbol": t.symbol,
         "price_str": format_price(quotes[t.symbol]["price"], t.symbol),
         "pct": quotes[t.symbol]["pct"]}
        for t in WATCHLIST
    )

    # ── News ──
    section("Headlines", "Last 48 hours · newest first")
    sources = list(NEWS_SOURCES)
    selected = st.pills("Sources", sources, selection_mode="multi", default=sources,
                        label_visibility="collapsed", key="mm_sources")
    with_images = st.toggle("Only articles with images", value=True, key="mm_img")

    with st.spinner("Loading headlines…"):
        articles = fetch_news()

    shown = [a for a in articles
             if a["source"] in (selected or []) and (a["img"] or not with_images)][:18]
    if not shown:
        empty_state("No headlines to show",
                    "The feeds returned nothing for this filter. Widen the source selection or refresh.")
        return

    news_grid({**a, "age": time_ago(a["pub"])} for a in shown)
