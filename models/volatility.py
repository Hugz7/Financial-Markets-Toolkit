"""
volatility.py — Implied-volatility analytics on option-chain DataFrames.

Pure functions (no I/O). DataFrames carry at least: strike, moneyness, iv_bsm.
"""

import numpy as np
import pandas as pd

from models.black_scholes import call_price, implied_vol, put_price


def safe_implied_vol(price: float, S: float, K: float, T: float,
                     r: float, q: float, is_call: bool) -> float:
    """Newton-Raphson BSM IV with convergence validation. Returns NaN on failure."""
    if price <= 0 or T <= 0 or K <= 0 or S <= 0:
        return np.nan
    try:
        iv = implied_vol(price, S, K, T, r, q, is_call=is_call)
        check_fn = call_price if is_call else put_price
        computed = check_fn(S, K, T, r, iv, q)
        if abs(computed - price) / max(price, 1e-6) > 0.08:
            return np.nan
        return iv if 0.005 < iv < 5.0 else np.nan
    except Exception:
        return np.nan


def atm_iv(calls: pd.DataFrame, puts: pd.DataFrame, S: float) -> float:
    """Average IV of the strikes nearest to spot (4 closest across calls & puts)."""
    combined = pd.concat([calls, puts])
    if combined.empty:
        return np.nan
    combined = combined.assign(dist=(combined["strike"] - S).abs())
    valid = combined.nsmallest(4, "dist")["iv_bsm"].dropna()
    return float(valid.mean()) if len(valid) else np.nan


def nearest_iv(df: pd.DataFrame, target_moneyness: float) -> float:
    """IV of the strike whose moneyness is closest to `target_moneyness`."""
    if df.empty:
        return np.nan
    idx = (df["moneyness"] - target_moneyness).abs().idxmin()
    return float(df.loc[idx, "iv_bsm"])


def otm_composite(calls: pd.DataFrame, puts: pd.DataFrame) -> pd.DataFrame:
    """OTM puts (K/S ≤ 1) + OTM calls (K/S ≥ 1), sorted by moneyness."""
    return pd.concat([puts[puts["moneyness"] <= 1.0],
                      calls[calls["moneyness"] >= 1.0]]).sort_values("moneyness")


def skew_metrics(calls: pd.DataFrame, puts: pd.DataFrame, S: float) -> dict:
    """ATM IV, 90% put IV, 110% call IV, skew and curvature (fractions; NaN when missing)."""
    atm = atm_iv(calls, puts, S)
    iv90 = nearest_iv(puts, 0.90)
    iv110 = nearest_iv(calls, 1.10)
    return {
        "atm": atm,
        "put90": iv90,
        "call110": iv110,
        "skew": iv90 - iv110,
        "curvature": (iv90 + iv110) / 2 - atm,
    }
