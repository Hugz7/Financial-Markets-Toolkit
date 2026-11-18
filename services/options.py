"""services/options.py — Live option chains via yfinance, enriched with BSM implied vol."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from models.volatility import safe_implied_vol


@st.cache_data(ttl=300, show_spinner=False)
def fetch_expiries(symbol: str) -> tuple[float, list[str]]:
    """Spot price and the list of listed expiries (ISO dates)."""
    t = yf.Ticker(symbol)
    spot = float(t.fast_info.last_price)
    expiries = list(t.options)
    if not np.isfinite(spot) or not expiries:
        raise ValueError(f"no listed options found for {symbol}")
    return spot, expiries


def _enrich(df: pd.DataFrame, S: float, T: float, r: float, q: float,
            is_call: bool) -> pd.DataFrame:
    df = df.copy()
    df["mid"] = np.where((df["bid"] > 0) & (df["ask"] > 0),
                         (df["bid"] + df["ask"]) / 2.0, df["lastPrice"])
    df["iv_bsm"] = [safe_implied_vol(m, S, k, T, r, q, is_call)
                    for m, k in zip(df["mid"], df["strike"])]
    df["moneyness"] = df["strike"] / S
    df["log_moneyness"] = np.log(df["strike"] / S)
    df["T"] = T
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Keep 0.55 ≤ K/S ≤ 1.60, valid IV < 300%, and some open interest or volume."""
    df = df[(df["moneyness"] >= 0.55) & (df["moneyness"] <= 1.60)]
    df = df[df["iv_bsm"].notna() & (df["iv_bsm"] < 3.0)]
    liquid = (df["openInterest"].fillna(0) > 0) | (df["volume"].fillna(0) > 0)
    return df[liquid].sort_values("strike")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_smile(symbol: str, expiry: str, S: float, r: float, q: float
                ) -> tuple[float, pd.DataFrame, pd.DataFrame]:
    """(T in years, calls, puts) for one expiry, with mid prices and BSM IV."""
    exp_date = dt.date.fromisoformat(expiry)
    T = max((exp_date - dt.date.today()).days / 365.0, 1 / 365.0)
    chain = yf.Ticker(symbol).option_chain(expiry)
    calls = _clean(_enrich(chain.calls, S, T, r, q, is_call=True))
    puts = _clean(_enrich(chain.puts, S, T, r, q, is_call=False))
    return T, calls, puts


def clear_cache() -> None:
    """Force fresh chains on the next fetch (explicit user reload)."""
    fetch_expiries.clear()
    fetch_smile.clear()
