"""services/suggestions.py — Persistence for the roadmap (suggestions.json at repo root)."""

from __future__ import annotations

import json
from pathlib import Path

SUGGESTIONS_FILE = Path(__file__).resolve().parent.parent / "suggestions.json"

PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Planned", "In Progress", "Done", "Rejected"]

DEFAULT_SUGGESTIONS = [
    {"title": "Volatility Smile / Skew", "description": "SABR, SVI, or spline interpolation", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Yield Curve Bootstrapping", "description": "Zero-coupon from swaps/bonds", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Variance Reduction MC", "description": "Antithetic variates, control variates, importance sampling — 50-70% error reduction", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "VaR / CVaR", "description": "Parametric + historical 99%/95% + Expected Shortfall", "priority": "High", "author": "System", "status": "Planned"},
    {"title": "Multi-Asset Correlation", "description": "Cholesky decomposition for worst-of, best-of, rainbow options", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Heston Stochastic Vol", "description": "FFT Carr-Madan calibration", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Swaption Pricer", "description": "Black76, Bachelier, vol cube", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Binomial/Trinomial Trees", "description": "CRR for American options, early exercise boundary", "priority": "Medium", "author": "System", "status": "Planned"},
    {"title": "Jump-Diffusion (Merton)", "description": "Poisson jumps + lognormal for fat tails", "priority": "Low", "author": "System", "status": "Planned"},
    {"title": "PDF Report Generator", "description": "Automated export with charts and commentary", "priority": "Low", "author": "System", "status": "Planned"},
]


def load_suggestions() -> list[dict]:
    if SUGGESTIONS_FILE.exists():
        with SUGGESTIONS_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    return [dict(s) for s in DEFAULT_SUGGESTIONS]


def save_suggestions(suggestions: list[dict]) -> None:
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2)
