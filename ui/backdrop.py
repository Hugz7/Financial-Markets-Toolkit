"""
ui/backdrop.py — Procedural market artwork for the page background.

Generates, deterministically:
  - market_tile_svg(): a seamless candlestick strip (OHLC + moving average +
    volume) that tiles horizontally, used as the scrolling "market horizon";
  - hero_line_svg(): a self-drawing price line placed behind each page title.

Pure functions returning SVG strings; no Streamlit, no I/O.
"""

from __future__ import annotations

import math
import random
import zlib
from urllib.parse import quote

TILE_W, TILE_H = 2400, 420


def _walk(rng: random.Random, n: int, vol: float, closed: bool) -> list[float]:
    """Gaussian random walk; if `closed`, drift is removed so it ends where it starts."""
    x = [0.0]
    for _ in range(n):
        x.append(x[-1] + rng.gauss(0, vol))
    if closed:
        x = [v - x[-1] * i / n for i, v in enumerate(x)]
    return x


def market_tile_svg(seed: int = 7, n: int = 96) -> str:
    """Seamless candlestick strip, TILE_W × TILE_H, monochrome with a blue MA."""
    rng = random.Random(seed)
    closes = _walk(rng, n, 1.0, closed=True)
    # gentle cycle so the horizon has shape, also closed over the tile
    closes = [c + 6 * math.sin(2 * math.pi * i / n) for i, c in enumerate(closes)]
    lo_v, hi_v = min(closes) - 3, max(closes) + 3
    top, bottom = 40, TILE_H - 110          # price band; volume lives below
    y = lambda v: bottom - (v - lo_v) / (hi_v - lo_v) * (bottom - top)  # noqa: E731

    step = TILE_W / n
    body_w = step * 0.46
    parts, ma_pts, window = [], [], []
    for i in range(n):
        o, c = closes[i], closes[i + 1]
        wick = abs(rng.gauss(0, 0.9)) + 0.4
        h, l_ = max(o, c) + wick, min(o, c) - abs(rng.gauss(0, 0.9)) - 0.4
        cx = i * step + step / 2
        up = c >= o
        fill = "#FFFFFF" if up else "none"
        parts.append(f"<line x1='{cx:.1f}' y1='{y(h):.1f}' x2='{cx:.1f}' y2='{y(l_):.1f}' "
                     f"stroke='#FFFFFF' stroke-width='1.2'/>")
        y_top, y_bot = y(max(o, c)), y(min(o, c))
        parts.append(f"<rect x='{cx - body_w / 2:.1f}' y='{y_top:.1f}' width='{body_w:.1f}' "
                     f"height='{max(y_bot - y_top, 1.5):.1f}' rx='1.5' fill='{fill}' "
                     f"stroke='#FFFFFF' stroke-width='1.2' fill-opacity='{0.85 if up else 0}'/>")
        vol = 18 + abs(c - o) * 22 + rng.random() * 26
        parts.append(f"<rect x='{cx - body_w / 2:.1f}' y='{TILE_H - 20 - vol:.1f}' width='{body_w:.1f}' "
                     f"height='{vol:.1f}' rx='1.5' fill='#FFFFFF' fill-opacity='0.35'/>")
        window.append(c)
        window = window[-8:]
        ma_pts.append(f"{cx:.1f},{y(sum(window) / len(window)):.1f}")

    ma = (f"<polyline points='{' '.join(ma_pts)}' fill='none' stroke='#0A84FF' "
          f"stroke-width='3' stroke-linejoin='round' stroke-linecap='round'/>")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{TILE_W}' height='{TILE_H}' "
            f"viewBox='0 0 {TILE_W} {TILE_H}'>{''.join(parts)}{ma}</svg>")


def candles_svg(ohlc: list[tuple[float, float, float, float, float]]) -> str:
    """Real candlesticks (open, high, low, close, volume) + 10-period MA + volume,
    drawn to stretch across the full width (preserveAspectRatio='none')."""
    n = len(ohlc)
    W, H = n * 24, TILE_H
    lows = [r[2] for r in ohlc]
    highs = [r[1] for r in ohlc]
    lo_v, hi_v = min(lows), max(highs)
    pad = (hi_v - lo_v) * 0.06
    lo_v, hi_v = lo_v - pad, hi_v + pad
    top, bottom = 30, H - 110
    y = lambda v: bottom - (v - lo_v) / (hi_v - lo_v) * (bottom - top)  # noqa: E731
    vmax = max(r[4] for r in ohlc) or 1
    parts, ma = [], []
    for i, (o, h, l_, c, v) in enumerate(ohlc):
        cx, bw = i * 24 + 12, 11
        up = c >= o
        parts.append(f"<line x1='{cx}' y1='{y(h):.1f}' x2='{cx}' y2='{y(l_):.1f}' stroke='#FFFFFF' stroke-width='1.2'/>")
        yt, yb = y(max(o, c)), y(min(o, c))
        parts.append(f"<rect x='{cx - bw / 2}' y='{yt:.1f}' width='{bw}' height='{max(yb - yt, 1.5):.1f}' rx='1.5' "
                     f"fill='#FFFFFF' fill-opacity='{0.85 if up else 0}' stroke='#FFFFFF' stroke-width='1.2'/>")
        vh = 12 + 70 * v / vmax
        parts.append(f"<rect x='{cx - bw / 2}' y='{H - 20 - vh:.1f}' width='{bw}' height='{vh:.1f}' rx='1.5' "
                     f"fill='#FFFFFF' fill-opacity='0.35'/>")
        window = [r[3] for r in ohlc[max(0, i - 9):i + 1]]
        ma.append(f"{cx},{y(sum(window) / len(window)):.1f}")
    ma_line = (f"<polyline points='{' '.join(ma)}' fill='none' stroke='#0A84FF' stroke-width='3' "
               f"stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' "
            f"preserveAspectRatio='none'>{''.join(parts)}{ma_line}</svg>")


def svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")


def hero_line_svg(title: str, n: int = 64,
                  series: tuple[float, ...] | None = None) -> tuple[str, float, float]:
    """The price line drawn behind each page title.

    With `series` (e.g. S&P 500 daily closes) the line is that real data; otherwise a
    procedural walk seeded by the title. Returns (svg, end_x_pct, end_y_pct); the end
    marker is positioned in HTML so it stays round while the SVG stretches."""
    if series and len(series) > 2:
        pts = list(series)
        n = len(pts) - 1
    else:
        rng = random.Random(zlib.crc32(title.encode("utf-8")))
        pts = _walk(rng, n, 1.0, closed=False)
        pts = [p + 0.32 * i for i, p in enumerate(pts)]    # clear uptrend
    lo, hi = min(pts), max(pts)
    W, H = 640, 220
    xy = [(i / n * W, 18 + (1 - (p - lo) / (hi - lo or 1)) * (H - 36)) for i, p in enumerate(pts)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{d} L{W},{H} L0,{H} Z"
    ex, ey = xy[-1]
    return (
        f"<svg class='fm-hero-line' viewBox='0 0 {W} {H}' preserveAspectRatio='none' aria-hidden='true'>"
        "<defs>"
        "<linearGradient id='fmHeroStroke' x1='0' x2='1' y1='0' y2='0'>"
        "<stop offset='0' stop-color='#0A84FF' stop-opacity='0'/>"
        "<stop offset='0.35' stop-color='#0A84FF'/><stop offset='1' stop-color='#BF5AF2'/></linearGradient>"
        "<linearGradient id='fmHeroFill' x1='0' x2='0' y1='0' y2='1'>"
        "<stop offset='0' stop-color='#0A84FF' stop-opacity='0.22'/>"
        "<stop offset='1' stop-color='#0A84FF' stop-opacity='0'/></linearGradient>"
        "</defs>"
        f"<path class='fm-hero-area' d='{area}' fill='url(#fmHeroFill)'/>"
        f"<path class='fm-hero-path' d='{d}' pathLength='1' fill='none' stroke='url(#fmHeroStroke)' "
        "stroke-width='2.2' stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>"
        "</svg>",
        ex / W * 100,
        ey / H * 100,
    )
