"""
services/news.py — The week's top business stories, with the publisher's own photos.

Sources are newsrooms whose RSS feeds carry their own images: The New York Times,
The Guardian and the BBC. "Top stories of the week" are ranked by:
  1. coverage — how many different outlets ran the story (clustered by headline overlap),
  2. editorial prominence — position in each outlet's feed,
  3. recency within the last 7 days.
Only stories with a publisher-supplied photo are kept. Ranking is pure (rank_stories)
and unit-tested; fetching is cached.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import feedparser
import streamlit as st

# outlet → feeds (several sections per outlet; an outlet counts once for coverage)
OUTLETS: dict[str, tuple[str, ...]] = {
    "The New York Times": (
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    ),
    "The Guardian": (
        "https://www.theguardian.com/business/rss",
        "https://www.theguardian.com/business/economics/rss",
    ),
    "BBC News": (
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ),
}
WINDOW_DAYS = 7
TOP_N = 8

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9$€£%]+(?:'[a-z]+)?")
_STOP = set("""a an the and or but of to in on for with at by from as is are was were be been it its
this that these those his her their our your my after before over under into about amid against
says said say new how why what who will would could can may might more most than as up down out
off just not no yes all any some us uk eu he she they we you i vs per via again still now
""".split())


@dataclass
class Article:
    outlet: str
    title: str
    link: str
    summary: str
    img: str | None
    pub: dt.datetime
    rank: int                      # position in its feed (0 = top)
    tokens: frozenset = field(default_factory=frozenset)


@dataclass
class Story:
    lead: Article
    outlets: list[str]
    score: float


def _tokens(text: str) -> frozenset:
    return frozenset(w for w in _WORD_RE.findall(text.lower()) if len(w) > 2 and w not in _STOP)


def _best_image(entry) -> str | None:
    """Largest publisher image in the entry (media:content / media:thumbnail)."""
    cands = []
    for attr in ("media_content", "media_thumbnail"):
        for m in getattr(entry, attr, None) or []:
            url = m.get("url")
            if url and url.startswith("https://"):
                try:
                    w = int(m.get("width") or 0)
                except ValueError:
                    w = 0
                cands.append((w, url))
    if not cands:
        return None
    url = max(cands)[1]
    # BBC ships 240px thumbnails; its image service serves the same picture at 976px.
    return re.sub(r"(ichef\.bbci\.co\.uk/(?:ace/standard|news))/240/", r"\1/976/", url)


def _parse(outlet: str, url: str, now: dt.datetime) -> list[Article]:
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    out = []
    for i, e in enumerate(feed.entries[:40]):
        stamp = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        if not stamp:
            continue
        pub = dt.datetime(*stamp[:6], tzinfo=dt.timezone.utc)
        title = (getattr(e, "title", "") or "").strip()
        if not title:
            continue
        summary = _TAG_RE.sub("", getattr(e, "summary", "") or "").strip()
        out.append(Article(outlet=outlet, title=title, link=getattr(e, "link", ""),
                           summary=summary[:260], img=_best_image(e), pub=pub, rank=i,
                           tokens=_tokens(title)))
    return out


def _similar(a: Article, b: Article) -> bool:
    if not a.tokens or not b.tokens:
        return False
    inter = len(a.tokens & b.tokens)
    jaccard = inter / len(a.tokens | b.tokens)
    return jaccard >= 0.34 or (inter >= 3 and jaccard >= 0.2)


def rank_stories(articles: list[Article], now: dt.datetime, top_n: int = TOP_N,
                 window_days: int = WINDOW_DAYS) -> list[Story]:
    """Cluster articles into stories and return the top ones that have a photo."""
    cutoff = now - dt.timedelta(days=window_days)
    recent = sorted((a for a in articles if a.pub >= cutoff), key=lambda a: (a.rank, -a.pub.timestamp()))

    clusters: list[list[Article]] = []
    for a in recent:
        for c in clusters:
            if any(_similar(a, b) for b in c):
                c.append(a)
                break
        else:
            clusters.append([a])

    stories = []
    for c in clusters:
        with_img = [a for a in c if a.img]
        if not with_img:
            continue
        outlets = sorted({a.outlet for a in c})
        best_rank = min(a.rank for a in c)
        newest = max(a.pub for a in c)
        age_days = (now - newest).total_seconds() / 86400
        score = (3.0 * len(outlets)                 # cross-outlet coverage
                 + 2.0 / (1 + best_rank / 3)        # editorial prominence
                 + 1.0 * max(0.0, 1 - age_days / window_days))  # recency
        lead = min(with_img, key=lambda a: (a.rank, -a.pub.timestamp()))
        stories.append(Story(lead=lead, outlets=outlets, score=score))
    stories.sort(key=lambda s: s.score, reverse=True)
    return stories[:top_n]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_top_stories() -> list[Story]:
    now = dt.datetime.now(dt.timezone.utc)
    articles = [a for outlet, urls in OUTLETS.items() for u in urls for a in _parse(outlet, u, now)]
    # the same article can appear in two sections of one outlet
    seen, unique = set(), []
    for a in sorted(articles, key=lambda a: a.rank):
        key = (a.outlet, a.link or a.title)
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return rank_stories(unique, now)


def time_ago(pub: dt.datetime) -> str:
    mins = int((dt.datetime.now(dt.timezone.utc) - pub).total_seconds() // 60)
    if mins < 2:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    return f"{hrs}h ago" if hrs < 24 else f"{hrs // 24}d ago"
