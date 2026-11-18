"""ui/formatting.py — Number formatting shared by all views."""

import math


def _bad(x) -> bool:
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def num(x, decimals: int = 2, signed: bool = False) -> str:
    if _bad(x):
        return "—"
    return f"{x:{'+' if signed else ''},.{decimals}f}"


def money(x, decimals: int = 0, ccy: str = "") -> str:
    if _bad(x):
        return "—"
    prefix = f"{ccy} " if ccy else ""
    return f"{prefix}{x:,.{decimals}f}"


def pct(x, decimals: int = 2, signed: bool = False) -> str:
    """x is a fraction (0.0325 → '3.25%')."""
    if _bad(x):
        return "—"
    return f"{x * 100:{'+' if signed else ''}.{decimals}f}%"


def bp(x, decimals: int = 1) -> str:
    """x is a fraction (0.0001 → '1.0 bp')."""
    if _bad(x):
        return "—"
    return f"{x * 1e4:,.{decimals}f} bp"
