"""services/news.py — Financial news aggregated from public RSS feeds (cached)."""

from __future__ import annotations

import datetime as dt
import re

import feedparser
import streamlit as st

NEWS_SOURCES: dict[str, str] = {
    "Reuters": "https://feeds.reuters.com/reuters/businessNews",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "AP News": "https://feeds.apnews.com/rss/apf-business",
    "The Guardian": "https://www.theguardian.com/business/economics/rss",
    "Barron's": "https://www.barrons.com/market-data/feeds/rss",
    "Investing.com": "https://www.investing.com/rss/news_14.rss",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _thumbnail(entry) -> str | None:
    for attr in ("media_content", "media_thumbnail"):
        items = getattr(entry, attr, None)
        if items and isinstance(items, list) and items[0].get("url"):
            return items[0]["url"]
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href", "")
        if "image" in enc.get("type", "") or href.endswith((".jpg", ".jpeg", ".png", ".webp")):
            return href
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(max_age_hours: int = 48, per_source: int = 15) -> list[dict]:
    """Merged articles from every source, newest first, within `max_age_hours`."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=max_age_hours)
    articles: list[dict] = []
    for name, url in NEWS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:per_source]:
            pub = now
            if getattr(entry, "published_parsed", None):
                try:
                    pub = dt.datetime(*entry.published_parsed[:6], tzinfo=dt.timezone.utc)
                except Exception:
                    pass
            if pub < cutoff:
                continue
            summary = _TAG_RE.sub("", getattr(entry, "summary", "") or "").strip()
            articles.append({
                "source": name,
                "title": getattr(entry, "title", "Untitled"),
                "link": getattr(entry, "link", "#"),
                "pub": pub,
                "summary": summary[:220],
                "img": _thumbnail(entry),
            })
    articles.sort(key=lambda a: a["pub"], reverse=True)
    return articles


def time_ago(pub: dt.datetime) -> str:
    mins = int((dt.datetime.now(dt.timezone.utc) - pub).total_seconds() // 60)
    if mins < 2:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    return f"{hrs}h ago" if hrs < 24 else f"{hrs // 24}d ago"
