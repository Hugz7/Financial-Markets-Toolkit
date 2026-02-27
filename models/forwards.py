"""
models/forwards.py — Forward contract pricing models.

Covers equity, FX, and commodity forwards with full term-structure and
sensitivity utilities.
"""

import numpy as np


# ── Core pricing formulas ──────────────────────────────────────────────────────

def equity_forward(S: float, r: float, q: float, T: float) -> float:
    """
    Equity forward price with continuous dividend yield.
        F = S · e^((r − q) · T)
    """
    return S * np.exp((r - q) * T)


def fx_forward(S: float, r_d: float, r_f: float, T: float) -> float:
    """
    FX forward price — covered interest rate parity.
        F = S · e^((r_d − r_f) · T)
    S is quoted as domestic per 1 unit of foreign (e.g. USD/EUR).
    """
    return S * np.exp((r_d - r_f) * T)


def commodity_forward(S: float, r: float, u: float, c: float, T: float) -> float:
    """
    Commodity forward with continuous storage cost u and convenience yield c.
        F = S · e^((r + u − c) · T)
    All rates continuous and annualised.
    """
    return S * np.exp((r + u - c) * T)


# ── Forward value (mark-to-market) ────────────────────────────────────────────

def forward_value(F_now: float, K: float, r: float, T: float) -> float:
    """
    Present value of an existing *long* forward entered at delivery price K,
    with current forward price F_now and T years remaining.
        V = (F_now − K) · e^(−r · T)
    """
    return (F_now - K) * np.exp(-r * T)


# ── Term-structure helpers ─────────────────────────────────────────────────────

def equity_term_structure(S, r, q, T_range):
    """Forward prices for an array of maturities (equity)."""
    T = np.asarray(T_range, dtype=float)
    return np.where(T == 0, S, S * np.exp((r - q) * T))


def fx_term_structure(S, r_d, r_f, T_range):
    """Forward prices for an array of maturities (FX)."""
    T = np.asarray(T_range, dtype=float)
    return np.where(T == 0, S, S * np.exp((r_d - r_f) * T))


def commodity_term_structure(S, r, u, c, T_range):
    """Forward prices for an array of maturities (commodity)."""
    T = np.asarray(T_range, dtype=float)
    return np.where(T == 0, S, S * np.exp((r + u - c) * T))


# ── Sensitivity grids ──────────────────────────────────────────────────────────

def forward_vs_spot(S_range, r, q, T, fwd_type="equity", r_f=0.0, u=0.0, c=0.0):
    """
    Forward price across a range of spot prices, for a fixed maturity T.
    Returns an array of the same length as S_range.
    """
    S = np.asarray(S_range, dtype=float)
    if fwd_type == "equity":
        return S * np.exp((r - q) * T)
    elif fwd_type == "fx":
        return S * np.exp((r - r_f) * T)
    else:  # commodity
        return S * np.exp((r + u - c) * T)


def forward_vs_rate(S, r_range, q, T, fwd_type="equity", r_f=0.0, u=0.0, c=0.0):
    """
    Forward price across a range of domestic risk-free rates, fixed S and T.
    """
    r = np.asarray(r_range, dtype=float)
    if fwd_type == "equity":
        return S * np.exp((r - q) * T)
    elif fwd_type == "fx":
        return S * np.exp((r - r_f) * T)
    else:  # commodity
        return S * np.exp((r + u - c) * T)


# ── Implied metrics ────────────────────────────────────────────────────────────

def implied_cost_of_carry(S: float, F: float, T: float) -> float:
    """Implied cost of carry b = ln(F/S) / T."""
    if T <= 0 or S <= 0 or F <= 0:
        return 0.0
    return np.log(F / S) / T


def annualised_forward_premium(S: float, F: float, T: float) -> float:
    """Annualised premium/discount: (F − S) / (S · T)."""
    if T <= 0 or S <= 0:
        return 0.0
    return (F - S) / (S * T)
