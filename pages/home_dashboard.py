"""
home_dashboard.py — Market Dashboard: live indices + financial news (last 48h).
"""

import streamlit as st
import datetime
import feedparser
import yfinance as yf

# ── News sources ──────────────────────────────────────────────────────────────
NEWS_SOURCES = [
    {
        "name": "Reuters",
        "color": "#FF8C00",
        "url": "https://feeds.reuters.com/reuters/businessNews",
    },
    {
        "name": "CNBC",
        "color": "#005594",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    },
    {
        "name": "MarketWatch",
        "color": "#00AC4E",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    },
    {
        "name": "Yahoo Finance",
        "color": "#6001D2",
        "url": "https://finance.yahoo.com/news/rssindex",
    },
    {
        "name": "AP News",
        "color": "#C8102E",
        "url": "https://feeds.apnews.com/rss/apf-business",
    },
    {
        "name": "The Guardian",
        "color": "#005689",
        "url": "https://www.theguardian.com/business/economics/rss",
    },
    {
        "name": "Barron's",
        "color": "#A67C00",
        "url": "https://www.barrons.com/market-data/feeds/rss",
    },
    {
        "name": "Investing.com",
        "color": "#E53935",
        "url": "https://www.investing.com/rss/news_14.rss",
    },
]

# ── Market tickers ────────────────────────────────────────────────────────────
MARKET_TICKERS = [
    ("S&P 500",    "^GSPC",    "#00E5FF"),
    ("NASDAQ",     "^IXIC",    "#38BDF8"),
    ("Dow Jones",  "^DJI",     "#A78BFA"),
    ("VIX",        "^VIX",     "#FF4D6D"),
    ("US 10Y",     "^TNX",     "#F0B429"),
    ("EUR/USD",    "EURUSD=X", "#10D48A"),
    ("Gold",       "GC=F",     "#F0B429"),
    ("WTI Oil",    "CL=F",     "#FB923C"),
    ("Bitcoin",    "BTC-USD",  "#FF8C00"),
]


# ── Cached data fetchers ──────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def fetch_market_data():
    """Fetch last close + % change for each ticker (cached 2 min)."""
    results = []
    symbols = [t[1] for t in MARKET_TICKERS]
    try:
        data = yf.download(symbols, period="5d", interval="1d",
                           progress=False, auto_adjust=True)["Close"]
        for label, sym, color in MARKET_TICKERS:
            try:
                series = data[sym].dropna()
                price = float(series.iloc[-1])
                prev  = float(series.iloc[-2])
                pct   = (price - prev) / prev * 100
            except Exception:
                price, pct = float("nan"), float("nan")
            results.append({"label": label, "symbol": sym, "color": color,
                             "price": price, "pct": pct})
    except Exception:
        for label, sym, color in MARKET_TICKERS:
            results.append({"label": label, "symbol": sym, "color": color,
                             "price": float("nan"), "pct": float("nan")})
    return results


@st.cache_data(ttl=300)
def fetch_news():
    """Fetch and merge news from all sources, keep last 48h (cached 5 min)."""
    import re
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=48)
    articles = []

    for src in NEWS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:15]:  # limit per source
                # Parse publication date
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub = datetime.datetime(*entry.published_parsed[:6],
                                                tzinfo=datetime.timezone.utc)
                    except Exception:
                        pass
                if pub is None:
                    pub = now  # fallback — include if date unknown

                if pub < cutoff:
                    continue  # skip articles older than 48h

                summary = getattr(entry, "summary", "") or ""
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 160:
                    summary = summary[:157] + "…"

                # ── Extract thumbnail image URL ──
                img_url = None
                # 1. media:content  (Yahoo Finance, etc.)
                mc = getattr(entry, "media_content", None)
                if mc and isinstance(mc, list) and mc[0].get("url"):
                    img_url = mc[0]["url"]
                # 2. media:thumbnail
                if not img_url:
                    mt = getattr(entry, "media_thumbnail", None)
                    if mt and isinstance(mt, list) and mt[0].get("url"):
                        img_url = mt[0]["url"]
                # 3. enclosures with image type  (Investing.com, etc.)
                if not img_url:
                    for enc in getattr(entry, "enclosures", []):
                        if "image" in enc.get("type", "") or enc.get("href", "").endswith(
                            (".jpg", ".jpeg", ".png", ".webp")
                        ):
                            img_url = enc.get("href")
                            break

                articles.append({
                    "source":  src["name"],
                    "color":   src["color"],
                    "title":   getattr(entry, "title", "No title"),
                    "link":    getattr(entry, "link", "#"),
                    "pub":     pub,
                    "summary": summary,
                    "img":     img_url,
                })
        except Exception:
            pass

    # Sort newest first
    articles.sort(key=lambda x: x["pub"], reverse=True)
    return articles


# ── Helpers ───────────────────────────────────────────────────────────────────

def _time_ago(pub: datetime.datetime) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - pub
    mins  = int(delta.total_seconds() / 60)
    if mins < 2:    return "Just now"
    if mins < 60:   return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:    return f"{hrs}h ago"
    return f"{hrs // 24}d ago"


def _pct_color(pct: float) -> str:
    if pct > 0:  return "#10D48A"
    if pct < 0:  return "#FF4D6D"
    return "#9BAEC8"


def _fmt_price(price: float, sym: str) -> str:
    if price != price:  # NaN
        return "—"
    if sym in ("^TNX", "EURUSD=X"):
        return f"{price:.4f}"
    if sym == "BTC-USD":
        return f"${price:,.0f}"
    return f"{price:,.2f}"


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    st.markdown("## Market Monitor")
    st.caption("Live market snapshot · Financial news from the last 48h")

    # ── Refresh button + timestamp ──
    col_ref, col_ts = st.columns([1, 5])
    with col_ref:
        if st.button("Refresh", key="dash_refresh"):
            st.cache_data.clear()
            st.rerun()
    with col_ts:
        st.caption(f"Auto-refresh: market every 2 min · news every 5 min  "
                   f"· {datetime.datetime.now().strftime('%d %b %Y  %H:%M')}")

    # ── Market Snapshot ──
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#00E5FF44,transparent);"
        "margin:8px 0 14px 0'></div>",
        unsafe_allow_html=True,
    )
    st.markdown("#### Market Snapshot")

    with st.spinner("Loading market data…"):
        market = fetch_market_data()

    cols = st.columns(len(market))
    for col, m in zip(cols, market):
        price_str = _fmt_price(m["price"], m["symbol"])
        pct = m["pct"]
        pct_str   = f"{pct:+.2f}%" if pct == pct else "—"
        pct_col   = _pct_color(pct)
        arrow     = "▲" if pct > 0 else ("▼" if pct < 0 else "")
        col.markdown(
            f"<div style='background:rgba(8,18,32,0.72);backdrop-filter:blur(12px);"
            f"-webkit-backdrop-filter:blur(12px);border:1px solid {m['color']}22;"
            f"border-top:2px solid {m['color']};border-radius:8px;padding:10px 12px;"
            f"text-align:center;box-shadow:0 2px 14px rgba(0,0,0,0.35)'>"
            f"<div style='color:#5A6A82;font-size:0.62rem;text-transform:uppercase;"
            f"letter-spacing:0.07em;font-weight:600;margin-bottom:4px'>{m['label']}</div>"
            f"<div style='color:{m['color']};font-size:1.05rem;font-weight:700;"
            f"font-variant-numeric:tabular-nums;letter-spacing:-0.01em'>{price_str}</div>"
            f"<div style='color:{pct_col};font-size:0.75rem;font-weight:600;margin-top:2px'>"
            f"{arrow} {pct_str}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── News Feed ──
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#1A2E45,transparent);"
        "margin:20px 0 14px 0'></div>",
        unsafe_allow_html=True,
    )
    st.markdown("#### Latest Financial News — 48h")

    # Source filter
    source_names = [s["name"] for s in NEWS_SOURCES]
    selected_sources = st.multiselect(
        "Filter by source",
        options=source_names,
        default=source_names,
        key="dash_sources",
        label_visibility="collapsed",
    )

    with st.spinner("Loading news…"):
        articles = fetch_news()

    filtered = [
        a for a in articles
        if a["source"] in selected_sources and a.get("img")
    ][:15]

    if not filtered:
        st.info("No recent articles with thumbnails found. Check your internet connection or click Refresh.")
        return

    st.caption(f"Showing {len(filtered)} articles with thumbnails · newest first")

    # ── 3-column news grid ──
    n_cols = 3
    rows = [filtered[i:i + n_cols] for i in range(0, len(filtered), n_cols)]

    for row in rows:
        cols = st.columns(n_cols)
        for col, art in zip(cols, row):
            time_str = _time_ago(art["pub"])
            src_color = art["color"]
            img_url   = art.get("img")

            # Thumbnail (always present — articles without images are filtered out)
            thumb_html = (
                f"<div style='width:calc(100% + 28px);height:140px;overflow:hidden;"
                f"border-radius:6px 6px 0 0;margin:-12px -14px 10px -14px'>"
                f"<img src='{img_url}' style='width:100%;height:100%;"
                f"object-fit:cover;display:block;filter:brightness(0.92)'>"
                f"</div>"
            )

            col.markdown(
                f"<a href='{art['link']}' target='_blank' style='text-decoration:none'>"
                f"<div style='background:rgba(8,18,32,0.70);backdrop-filter:blur(12px);"
                f"-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.07);"
                f"border-top:2px solid {src_color};border-radius:8px;padding:12px 14px;"
                f"margin-bottom:4px;box-shadow:0 4px 18px rgba(0,0,0,0.35);"
                f"transition:box-shadow 0.2s'>"
                + thumb_html +
                # Source + time
                f"<div style='display:flex;justify-content:space-between;"
                f"align-items:center;margin-bottom:6px'>"
                f"<span style='color:{src_color};font-size:0.63rem;font-weight:700;"
                f"text-transform:uppercase;letter-spacing:0.07em'>{art['source']}</span>"
                f"<span style='color:#3A4A5C;font-size:0.63rem'>{time_str}</span>"
                f"</div>"
                # Headline
                f"<div style='color:#D0DCE8;font-size:0.87rem;font-weight:600;"
                f"line-height:1.4;margin-bottom:6px'>{art['title']}</div>"
                # Summary
                + (
                    f"<div style='color:#5A6A82;font-size:0.75rem;line-height:1.5'>"
                    f"{art['summary']}</div>"
                    if art["summary"] else ""
                ) +
                # Read more
                f"<div style='color:{src_color};font-size:0.70rem;font-weight:600;"
                f"margin-top:10px;opacity:0.85'>Read article →</div>"
                f"</div></a>",
                unsafe_allow_html=True,
            )
        for _ in range(n_cols - len(row)):
            cols[len(row) + _].empty()
