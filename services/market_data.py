"""services/market_data.py — Live quotes via yfinance (cached)."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st
import yfinance as yf


@dataclass(frozen=True)
class Ticker:
    label: str
    symbol: str
    group: str


WATCHLIST: tuple[Ticker, ...] = (
    Ticker("S&P 500", "^GSPC", "Equities"),
    Ticker("Nasdaq", "^IXIC", "Equities"),
    Ticker("Dow Jones", "^DJI", "Equities"),
    Ticker("VIX", "^VIX", "Volatility"),
    Ticker("US 10Y", "^TNX", "Rates"),
    Ticker("EUR/USD", "EURUSD=X", "FX"),
    Ticker("Gold", "GC=F", "Commodities"),
    Ticker("WTI Crude", "CL=F", "Commodities"),
    Ticker("Bitcoin", "BTC-USD", "Crypto"),
)


def format_price(price: float, symbol: str) -> str:
    if price != price:  # NaN
        return "—"
    if symbol in ("^TNX", "EURUSD=X"):
        return f"{price:.4f}"
    if symbol == "BTC-USD":
        return f"${price:,.0f}"
    return f"{price:,.2f}"


@st.cache_data(ttl=120, show_spinner=False)
def fetch_quotes(symbols: tuple[str, ...]) -> dict[str, dict]:
    """Last close and day-over-day % change per symbol. Missing data → NaN."""
    out = {s: {"price": float("nan"), "pct": float("nan")} for s in symbols}
    try:
        data = yf.download(list(symbols), period="5d", interval="1d",
                           progress=False, auto_adjust=True)["Close"]
    except Exception:
        return out
    for s in symbols:
        try:
            series = data[s].dropna()
            price, prev = float(series.iloc[-1]), float(series.iloc[-2])
            out[s] = {"price": price, "pct": (price - prev) / prev * 100}
        except Exception:
            pass
    return out
