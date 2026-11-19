"""
ui/components.py — Reusable presentation components.

Views compose these instead of writing inline HTML/CSS. All text passed in is
HTML-escaped, so data from external feeds can't inject markup. Visual styling
lives in ui/styles.css; the only inline style here is `--i`, the stagger index
that drives the entrance animation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Iterable, Literal, Optional

import plotly.graph_objects as go
import streamlit as st

from ui.backdrop import candles_svg, hero_line_svg, market_tile_svg, svg_data_uri
from ui.theme import C

Tone = Literal["default", "pos", "neg", "warn", "accent", "muted"]

_CSS_PATH = Path(__file__).with_name("styles.css")
_PANEL_SEQ = "_fm_panel_seq"


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _cls(tone: Optional[str]) -> str:
    return f" fm-{tone}" if tone and tone != "default" else ""


# ── Global ────────────────────────────────────────────────────────────────────

_HERO = "_fm_hero_series"   # (closes, label) of the real index, set per run by main.py


@lru_cache(maxsize=4)
def _backdrop_css(candles: tuple | None) -> str:
    """CSS carrying the market artwork: real S&P 500 weekly candles when available
    (static, full-width, slow sway), else the procedural seamless tile (scrolling)."""
    if candles:
        uri = svg_data_uri(candles_svg(list(candles)))
        return (f':root {{ --fm-market-tile: url("{uri}"); }}\n'
                '[data-testid="stAppViewContainer"]::before { left: -3%; right: -3%; '
                'background-size: 100% 100%; background-repeat: no-repeat; '
                'animation: fm-sway 70s ease-in-out infinite alternate; }')
    return f':root {{ --fm-market-tile: url("{svg_data_uri(market_tile_svg())}"); }}'


def inject_styles(candles: tuple | None = None,
                  hero_series: tuple[float, ...] | None = None, hero_label: str | None = None) -> None:
    """Load ui/styles.css and the market artwork; reset per-run counters.

    candles: weekly (open, high, low, close, volume) rows for the background horizon.
    hero_series / hero_label: closes drawn behind every page title, and their caption.
    """
    st.session_state[_PANEL_SEQ] = 0
    st.session_state[_HERO] = (hero_series, hero_label)
    _html(f"<style>{_backdrop_css(candles)}\n{_CSS_PATH.read_text(encoding='utf-8')}</style>")


def require(condition: bool, message: str) -> None:
    """Show an error and stop rendering the page if `condition` is false."""
    if not condition:
        st.error(message, icon=":material/error:")
        st.stop()


# ── Layout ────────────────────────────────────────────────────────────────────

def panel():
    """A glass-material panel for grouping inputs: `with panel(): ...`.

    Each panel gets a run-stable key so styles.css can target it via its
    `st-key-fmpanel-*` class (bordered containers expose no other hook).
    """
    n = st.session_state.get(_PANEL_SEQ, 0) + 1
    st.session_state[_PANEL_SEQ] = n
    return st.container(border=True, key=f"fmpanel-{n}")


# ── Headings ──────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    """Hero block: gradient eyebrow, large gradient headline, soft subtitle."""
    eb = f"<div class='fm-eyebrow'>{escape(eyebrow)}</div>" if eyebrow else ""
    sub = f"<p class='fm-subtitle'>{escape(subtitle)}</p>" if subtitle else ""
    series, label = st.session_state.get(_HERO, (None, None))
    svg, dx, dy = hero_line_svg(title, series=series)
    tag = (f"<span class='fm-hero-tag' style='top:{dy:.1f}%'>{escape(label)}</span>"
           if series and label else "")
    art = (f"<div class='fm-hero-art' aria-hidden='true'>{svg}"
           f"<span class='fm-hero-dot' style='left:{dx:.1f}%;top:{dy:.1f}%'></span>{tag}</div>")
    _html(f"<header class='fm-hero'>{art}{eb}<h1 class='fm-title'>{escape(title)}</h1>{sub}</header>")


def section(title: str, caption: str | None = None) -> None:
    """Two-tone section headline in the Apple style: 'Title. Grey continuation.'"""
    head = title if title.endswith((".", "?", "!")) else f"{title}."
    if caption:
        caption = caption[0].upper() + caption[1:]
    cap = f" <span class='fm-h-sub'>{escape(caption)}</span>" if caption else ""
    _html(f"<div class='fm-section fm-reveal'><div class='fm-h' role='heading' aria-level='2'>"
          f"{escape(head)}{cap}</div></div>")


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
    for i, s in enumerate(stats):
        dot = f"<span class='fm-dot' style='background:{s.dot}'></span>" if s.dot else ""
        hint = f"<div class='fm-stat-hint'>{escape(s.hint)}</div>" if s.hint else ""
        delta = ""
        if s.delta is not None and s.delta == s.delta:
            tone = "pos" if s.delta > 0 else "neg" if s.delta < 0 else "muted"
            delta = f"<div class='fm-stat-delta fm-{tone}'>{escape(s.delta_fmt.format(s.delta))}</div>"
        size = " sm" if s.small else ""
        cards.append(
            f"<div class='fm-stat' style='--i:{i}'><div class='fm-stat-label'>{dot}{escape(s.label)}</div>"
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
    _html(f"<div class='fm-callout{tone_cls}'><span class='fm-callout-dot'></span>"
          f"<div>{t}{escape(body)}</div></div>")


def empty_state(title: str, body: str) -> None:
    _html(f"<div class='fm-empty'><div class='fm-empty-orb'></div>"
          f"<b>{escape(title)}</b><span>{escape(body)}</span></div>")


def badge(text: str, tone: Literal["default", "pos", "neg", "warn", "accent"] = "default") -> str:
    """Return badge HTML (for composing inside other markup)."""
    tone_cls = "" if tone == "default" else f" {tone}"
    return f"<span class='fm-badge{tone_cls}'>{escape(text)}</span>"


def badges(items: Iterable[tuple[str, str]]) -> None:
    _html("<div class='fm-badges'>" + " ".join(badge(t, tone) for t, tone in items) + "</div>")


# ── Charts ────────────────────────────────────────────────────────────────────

def chart(fig: go.Figure, height: int = 400, key: str | None = None,
          title: str | None = None) -> None:
    """Render a Plotly figure with the app template (registered in ui.theme)."""
    fig.update_layout(template="fmt", height=height)
    if title is not None:
        fig.update_layout(title_text=title)
    if not (fig.layout.title and fig.layout.title.text):
        fig.update_layout(margin=dict(t=56))  # legend band only
    st.plotly_chart(fig, theme=None, width="stretch", key=key,
                    config={"displaylogo": False, "displayModeBar": "hover",
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def hline_zero(fig: go.Figure) -> None:
    fig.add_hline(y=0, line_color=C.axis, line_width=1)


# ── Market monitor ────────────────────────────────────────────────────────────

def _pct_html(pct: float, cls: str) -> str:
    if pct != pct:
        return f"<span class='{cls} fm-muted'>—</span>"
    tone = "pos" if pct > 0 else "neg" if pct < 0 else "muted"
    arrow = "▲" if pct > 0 else "▼" if pct < 0 else ""
    return f"<span class='{cls} fm-{tone}'>{arrow} {pct:+.2f}%</span>"


def sparkline_svg(values: list[float], up: bool | None = None, w: int = 120, h: int = 34) -> str:
    """Tiny inline line + soft area for a quote tile (no axes)."""
    vals = [v for v in values if v == v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = [(i / (len(vals) - 1) * w, 3 + (1 - (v - lo) / span) * (h - 6)) for i, v in enumerate(vals)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    up = vals[-1] >= vals[0] if up is None else up
    col = "var(--fm-pos)" if up else "var(--fm-neg)"
    return (f"<svg class='fm-spark' viewBox='0 0 {w} {h}' preserveAspectRatio='none' aria-hidden='true'>"
            f"<path d='{d} L{w},{h} L0,{h} Z' fill='{col}' fill-opacity='0.12'/>"
            f"<path d='{d}' fill='none' stroke='{col}' stroke-width='1.6' stroke-linejoin='round' "
            f"vector-effect='non-scaling-stroke'/></svg>")


def quote_tiles(quotes: Iterable[dict]) -> None:
    """quotes: dicts with label, symbol, price_str, pct (float, may be NaN),
    and optionally `spark` (list of closes) and `horizon` (e.g. '1W')."""
    tiles = []
    for i, q in enumerate(quotes):
        spark = sparkline_svg(q.get("spark") or [], up=(q["pct"] >= 0) if q["pct"] == q["pct"] else None)
        hz = f"<span class='fm-quote-hz'>{escape(q.get('horizon', ''))}</span>" if q.get("horizon") else ""
        tiles.append(
            f"<div class='fm-quote' style='--i:{i}'><div class='fm-quote-top'>"
            f"<span class='fm-quote-name'>{escape(q['label'])}</span>"
            f"<span class='fm-quote-sym'>{escape(q['symbol'])}</span></div>"
            f"<div class='fm-quote-px'>{escape(q['price_str'])}</div>"
            f"<div class='fm-quote-row'>{_pct_html(q['pct'], 'fm-quote-chg')}{hz}</div>{spark}</div>"
        )
    _html("<div class='fm-quotes'>" + "".join(tiles) + "</div>")


def ticker_tape(items: Iterable[dict]) -> None:
    """Endlessly scrolling tape: dicts with label, price_str, pct. Pauses on hover."""
    cells = "".join(
        f"<span class='fm-tape-item'><b>{escape(t['label'])}</b>"
        f"<span class='fm-tape-px'>{escape(t['price_str'])}</span>{_pct_html(t['pct'], 'fm-tape-chg')}</span>"
        for t in items
    )
    if not cells:
        return
    # content duplicated so the -50% translate loops seamlessly
    _html(f"<div class='fm-tape' aria-label='Market ticker'><div class='fm-tape-track'>"
          f"<div class='fm-tape-run'>{cells}</div><div class='fm-tape-run' aria-hidden='true'>{cells}</div>"
          f"</div></div>")


def live_status(is_open: bool, clock: str, updated: str) -> None:
    state = ("<span class='fm-live open'><i></i>NYSE open</span>" if is_open
             else "<span class='fm-live'><i></i>NYSE closed</span>")
    _html(f"<div class='fm-status'>{state}<span>{escape(clock)}</span>"
          f"<span>Updated {escape(updated)}</span></div>")


def _safe_url(url: str | None) -> str | None:
    return url if url and url.startswith("https://") else None


def news_grid(articles: Iterable[dict]) -> None:
    """Ranked stories: the first is a wide lead card, the rest a grid.

    articles: dicts with source, title, link, summary, img, age, rank, also (other outlets)."""
    cards = []
    for i, a in enumerate(articles):
        link = _safe_url(a.get("link")) or "#"
        img = _safe_url(a.get("img"))
        img_html = (f"<div class='fm-news-media'><img class='fm-news-img' loading='lazy' "
                    f"referrerpolicy='no-referrer' src='{escape(img, quote=True)}' alt=''></div>"
                    if img else "")
        summary = f"<div class='fm-news-sum'>{escape(a['summary'])}</div>" if a.get("summary") else ""
        also = (f"<div class='fm-news-also'>Also covered by {escape(', '.join(a['also']))}</div>"
                if a.get("also") else "")
        lead = " lead" if i == 0 else ""
        cards.append(
            f"<a class='fm-news-card fm-reveal{lead}' style='--i:{i % 4}' href='{escape(link, quote=True)}' "
            f"target='_blank' rel='noopener noreferrer'>"
            f"{img_html}<div class='fm-news-body'>"
            f"<div class='fm-news-meta'><span class='fm-news-rank'>{i + 1:02d}</span>"
            f"<span class='fm-news-src'>{escape(a['source'])}</span>"
            f"<span class='fm-news-age'>{escape(a.get('age', ''))}</span></div>"
            f"<div class='fm-news-title'>{escape(a['title'])}</div>{summary}{also}</div></a>"
        )
    _html("<div class='fm-news'>" + "".join(cards) + "</div>")


# ── Flashcards ────────────────────────────────────────────────────────────────

_LEVEL_TONE = {"easy": ("Easy", "pos"), "medium": ("Medium", "warn"), "hard": ("Hard", "neg")}


def flashcard(card_id: str, question: str, answer: str, *, eyebrow: str, counter: str,
              points: Iterable[str] = (), status: str | None = None, level: str | None = None) -> None:
    """A 3D flip card. Clicking (or Space on the focused card) flips it client-side:
    a visually hidden checkbox drives the rotation, so no rerun is needed.
    `status` is 'known' or 'review'; `level` is 'easy' / 'medium' / 'hard'. Both show
    as badges on each face."""
    cid = escape(card_id, quote=True)
    tag = badge(*_LEVEL_TONE[level]) if level in _LEVEL_TONE else ""
    if status == "known":
        tag += " " + badge("Known", "pos")
    elif status == "review":
        tag += " " + badge("To review", "warn")
    pts = "".join(f"<li>{escape(p)}</li>" for p in points)
    pts_html = f"<ul class='fm-card-points'>{pts}</ul>" if pts else ""
    # Keyed container: a new card mounts fresh DOM, so it starts question-side up
    # and replays the deal-in animation (otherwise React reuses the checked input).
    tag = f"<span class='fm-card-tags'>{tag}</span>" if tag else ""
    with st.container(key=f"fmcard-{card_id}"):
        _flashcard_markup(cid, question, answer, eyebrow, counter, tag, pts_html)


def _flashcard_markup(cid, question, answer, eyebrow, counter, tag, pts_html) -> None:
    _html(
        f"<div class='fm-deck'>"
        f"<input type='checkbox' id='fc-{cid}' class='fm-flip-toggle' aria-label='Reveal answer'>"
        f"<label for='fc-{cid}' class='fm-flip'><div class='fm-flip-inner'>"
        f"<div class='fm-face fm-front'>"
        f"<div class='fm-card-top'><span class='fm-card-eyebrow'>{escape(eyebrow)}</span>"
        f"<span class='fm-card-count'>{escape(counter)}</span></div>"
        f"<div class='fm-card-q'>{escape(question)}</div>"
        f"<div class='fm-card-foot'>{tag}<span class='fm-card-hint'>Tap to reveal the answer</span></div>"
        f"</div>"
        f"<div class='fm-face fm-back'>"
        f"<div class='fm-card-top'><span class='fm-card-eyebrow'>Answer</span>"
        f"<span class='fm-card-count'>{escape(counter)}</span></div>"
        f"<div class='fm-card-a'>{escape(answer)}</div>{pts_html}"
        f"<div class='fm-card-foot'>{tag}<span class='fm-card-hint'>Tap to flip back</span></div>"
        f"</div></div></label></div>"
    )


# ── Footer ────────────────────────────────────────────────────────────────────

def page_footer(text: str) -> None:
    """Fine-print footer under every page, separated by a hairline."""
    _html(f"<footer class='fm-foot'>{escape(text)}</footer>")
