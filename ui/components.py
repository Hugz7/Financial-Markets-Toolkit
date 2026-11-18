"""
ui/components.py — Reusable presentation components.

Views compose these instead of writing inline HTML/CSS. All text passed in is
HTML-escaped, so data from external feeds can't inject markup.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, Literal, Optional

import plotly.graph_objects as go
import streamlit as st

from ui.theme import C

Tone = Literal["default", "pos", "neg", "warn", "accent", "muted"]

_CSS_PATH = Path(__file__).with_name("styles.css")


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _cls(tone: Optional[str]) -> str:
    return f" fm-{tone}" if tone and tone != "default" else ""


# ── Global ────────────────────────────────────────────────────────────────────

def inject_styles() -> None:
    """Load ui/styles.css once per run (call from the entry point)."""
    _html(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>")


def require(condition: bool, message: str) -> None:
    """Show an error and stop rendering the page if `condition` is false."""
    if not condition:
        st.error(message, icon=":material/error:")
        st.stop()


# ── Headings ──────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    eb = f"<div class='fm-eyebrow'>{escape(eyebrow)}</div>" if eyebrow else ""
    sub = f"<div class='fm-subtitle'>{escape(subtitle)}</div>" if subtitle else ""
    _html(f"<div class='fm-header'>{eb}<h1 class='fm-title'>{escape(title)}</h1>{sub}</div>")


def section(title: str, caption: str | None = None) -> None:
    cap = f"<span>{escape(caption)}</span>" if caption else ""
    _html(f"<div class='fm-section'><div class='fm-h' role='heading' aria-level='2'>"
          f"{escape(title)}</div>{cap}</div>")


# ── Stats ─────────────────────────────────────────────────────────────────────

@dataclass
class Stat:
    """One KPI tile. `tone` colours the value; `delta` is a signed number shown under it."""
    label: str
    value: str
    hint: str | None = None
    tone: Tone = "default"
    delta: float | None = None
    delta_fmt: str = "{:+.2f}%"
    dot: str | None = None   # optional series colour swatch next to the label
    small: bool = False


def stat_grid(stats: Iterable[Stat], columns: int = 4) -> None:
    cards = []
    for s in stats:
        dot = f"<span class='fm-dot' style='background:{s.dot}'></span>" if s.dot else ""
        hint = f"<div class='fm-stat-hint'>{escape(s.hint)}</div>" if s.hint else ""
        delta = ""
        if s.delta is not None and s.delta == s.delta:
            tone = "pos" if s.delta > 0 else "neg" if s.delta < 0 else "muted"
            delta = f"<div class='fm-stat-delta fm-{tone}'>{escape(s.delta_fmt.format(s.delta))}</div>"
        size = " sm" if s.small else ""
        cards.append(
            f"<div class='fm-stat'><div class='fm-stat-label'>{dot}{escape(s.label)}</div>"
            f"<div class='fm-stat-value{size}{_cls(s.tone)}'>{escape(s.value)}</div>{delta}{hint}</div>"
        )
    _html(f"<div class='fm-stats' style='grid-template-columns:repeat({columns},minmax(0,1fr))'>"
          + "".join(cards) + "</div>")


# ── Messages ──────────────────────────────────────────────────────────────────

def callout(body: str, title: str | None = None,
            tone: Literal["info", "pos", "neg", "warn", "neutral"] = "info") -> None:
    """A quiet inline note — model descriptions, assumptions, caveats."""
    t = f"<b>{escape(title)}</b>&nbsp; " if title else ""
    tone_cls = "" if tone == "info" else f" {tone}"
    _html(f"<div class='fm-callout{tone_cls}'><div>{t}{escape(body)}</div></div>")


def empty_state(title: str, body: str) -> None:
    _html(f"<div class='fm-empty'><b>{escape(title)}</b>{escape(body)}</div>")


def badge(text: str, tone: Literal["default", "pos", "neg", "warn", "accent"] = "default") -> str:
    """Return badge HTML (for composing inside other markup)."""
    tone_cls = "" if tone == "default" else f" {tone}"
    return f"<span class='fm-badge{tone_cls}'>{escape(text)}</span>"


def badges(items: Iterable[tuple[str, str]]) -> None:
    _html(" ".join(badge(t, tone) for t, tone in items))


# ── Charts ────────────────────────────────────────────────────────────────────

def chart(fig: go.Figure, height: int = 400, key: str | None = None,
          title: str | None = None) -> None:
    """Render a Plotly figure with the app template (registered in ui.theme)."""
    fig.update_layout(template="fmt", height=height)
    if title is not None:
        fig.update_layout(title_text=title)
    if not (fig.layout.title and fig.layout.title.text):
        fig.update_layout(margin=dict(t=40))  # legend band only
    st.plotly_chart(fig, theme=None, width="stretch", key=key,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def hline_zero(fig: go.Figure) -> None:
    fig.add_hline(y=0, line_color=C.axis, line_width=1)


# ── Market monitor ────────────────────────────────────────────────────────────

def quote_tiles(quotes: Iterable[dict]) -> None:
    """quotes: dicts with label, symbol, price_str, pct (float, may be NaN)."""
    tiles = []
    for q in quotes:
        pct = q["pct"]
        if pct == pct:
            tone = "pos" if pct > 0 else "neg" if pct < 0 else "muted"
            arrow = "▲" if pct > 0 else "▼" if pct < 0 else ""
            chg = f"<span class='fm-quote-chg fm-{tone}'>{arrow} {pct:+.2f}%</span>"
        else:
            chg = "<span class='fm-quote-chg fm-muted'>—</span>"
        tiles.append(
            "<div class='fm-quote'><div class='fm-quote-top'>"
            f"<span class='fm-quote-name'>{escape(q['label'])}</span>"
            f"<span class='fm-quote-sym'>{escape(q['symbol'])}</span></div>"
            f"<div class='fm-quote-px'>{escape(q['price_str'])}</div>{chg}</div>"
        )
    _html("<div class='fm-quotes'>" + "".join(tiles) + "</div>")


def news_grid(articles: Iterable[dict]) -> None:
    """articles: dicts with source, title, link, summary, img, age."""
    cards = []
    for a in articles:
        link = a.get("link") or "#"
        if not link.startswith(("http://", "https://")):
            link = "#"
        img = a.get("img")
        img_html = (f"<img class='fm-news-img' loading='lazy' src='{escape(img, quote=True)}' alt=''>"
                    if img and img.startswith(("http://", "https://")) else "")
        summary = f"<div class='fm-news-sum'>{escape(a['summary'])}</div>" if a.get("summary") else ""
        cards.append(
            f"<a class='fm-news-card' href='{escape(link, quote=True)}' target='_blank' rel='noopener noreferrer'>"
            f"{img_html}<div class='fm-news-body'>"
            f"<div class='fm-news-meta'><span class='fm-news-src'>{escape(a['source'])}</span>"
            f"<span>{escape(a.get('age', ''))}</span></div>"
            f"<div class='fm-news-title'>{escape(a['title'])}</div>{summary}</div></a>"
        )
    _html("<div class='fm-news'>" + "".join(cards) + "</div>")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar_footer(text: str) -> None:
    _html(f"<div class='fm-foot'>{escape(text)}</div>")
