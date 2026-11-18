"""
navigation.py — The page registry: sections, titles, icons and URL slugs.

main.py calls build() on every run; views that link to other pages call
page(slug) at render time (never at import time, to avoid a circular import).
"""

from __future__ import annotations

import streamlit as st

from views import (
    exotic_pricer, forwards, interview_prep, market_monitor, monte_carlo,
    payoff_analyzer, roadmap, swaps, vol_smile, yield_curve,
)

# section → [(module, title, material icon, url slug)]
_SPEC = {
    "Markets": [(market_monitor, "Market Monitor", "monitoring", "markets")],
    "Options": [
        (payoff_analyzer, "Payoff Analyzer", "stacked_line_chart", "payoff"),
        (exotic_pricer, "Exotic Pricer", "function", "exotics"),
        (vol_smile, "Volatility Smile", "ssid_chart", "vol-smile"),
    ],
    "Rates & Forwards": [
        (yield_curve, "Yield Curve", "show_chart", "yield-curve"),
        (swaps, "Swaps", "swap_horiz", "swaps"),
        (forwards, "Forwards", "trending_up", "forwards"),
    ],
    "Simulation": [(monte_carlo, "Monte Carlo", "scatter_plot", "monte-carlo")],
    "Practice": [(interview_prep, "Interview Prep", "style", "interview")],
    "Project": [(roadmap, "Roadmap", "checklist", "roadmap")],
}
DEFAULT_SLUG = "markets"

_BY_SLUG: dict[str, st.Page] = {}


def build() -> dict[str, list[st.Page]]:
    """Create this run's st.Page objects, grouped by section."""
    _BY_SLUG.clear()
    sections: dict[str, list[st.Page]] = {}
    for section, items in _SPEC.items():
        pages = []
        for module, title, icon, slug in items:
            p = st.Page(module.render, title=title, icon=f":material/{icon}:",
                        url_path=slug, default=(slug == DEFAULT_SLUG))
            _BY_SLUG[slug] = p
            pages.append(p)
        sections[section] = pages
    return sections


def page(slug: str) -> st.Page | None:
    """The st.Page for a slug, for st.page_link / st.switch_page."""
    return _BY_SLUG.get(slug)


def title(slug: str) -> str:
    for items in _SPEC.values():
        for _, t, _, s in items:
            if s == slug:
                return t
    return slug
