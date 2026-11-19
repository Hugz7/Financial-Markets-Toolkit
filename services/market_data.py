"""
services/market_data.py — Live market data via yfinance (cached).

- Watchlist history → last price, 1D / 1W / 1M changes and sparklines.
- S&P 500 daily OHLC (5y) → dashboard chart and the site's design curve. The last
  successful download is also written to data/cache/sp500.csv, so the design keeps
  showing the real index offline; if neither is available, callers get None.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
SP500_CACHE = CACHE_DIR / "sp500.csv"
SP500 = "^GSPC"


@dataclass(frozen=True)
class Ticker:
    label: str
    symbol: str
    group: str


WATCHLIST: tuple[Ticker, ...] = (
    Ticker("S&P 500", "^GSPC", "Equities"),
    Ticker("Nasdaq", "^IXIC", "Equities"),
    Ticker("Dow Jones", "^DJI", "Equities"),
    Ticker("CAC 40", "^FCHI", "Equities"),
    Ticker("DAX", "^GDAXI", "Equities"),
    Ticker("Nikkei 225", "^N225", "Equities"),
    Ticker("VIX", "^VIX", "Volatility"),
    Ticker("US 10Y", "^TNX", "Rates"),
    Ticker("EUR/USD", "EURUSD=X", "FX"),
    Ticker("Gold", "GC=F", "Commodities"),
    Ticker("WTI Crude", "CL=F", "Commodities"),
    Ticker("Bitcoin", "BTC-USD", "Crypto"),
)

HORIZONS = {"1D": 1, "1W": 5, "1M": 21}   # trading-day lookbacks


def format_price(price: float, symbol: str) -> str:
    if price != price:  # NaN
        return "—"
    if symbol == "EURUSD=X":
        return f"{price:.4f}"
    if symbol == "^TNX":
        return f"{price:.3f}%"
    if symbol == "BTC-USD":
        return f"${price:,.0f}"
    return f"{price:,.2f}"


def changes(closes: pd.Series) -> dict[str, float]:
    """Percentage change over each horizon from a series of daily closes."""
    closes = closes.dropna()
    out = {}
    for name, lag in HORIZONS.items():
        out[name] = (float(closes.iloc[-1] / closes.iloc[-1 - lag] - 1) * 100
                     if len(closes) > lag else float("nan"))
    return out


@st.cache_data(ttl=120, show_spinner=False)
def fetch_watchlist(symbols: tuple[str, ...]) -> dict[str, pd.Series]:
    """~2 months of daily closes per symbol (empty Series when unavailable)."""
    try:
        data = yf.download(list(symbols), period="3mo", interval="1d",
                           progress=False, auto_adjust=True, threads=True)["Close"]
    except Exception:
        return {s: pd.Series(dtype=float) for s in symbols}
    out = {}
    for s in symbols:
        try:
            out[s] = data[s].dropna()
        except Exception:
            out[s] = pd.Series(dtype=float)
    return out


def _read_cache() -> pd.DataFrame | None:
    try:
        df = pd.read_csv(SP500_CACHE, index_col=0, parse_dates=True)
        return df if len(df) > 50 else None
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def sp500_history() -> tuple[pd.DataFrame | None, str]:
    """(OHLCV DataFrame, source) where source is 'live', 'cache' or 'none'."""
    try:
        df = yf.Ticker(SP500).history(period="5y", interval="1d", auto_adjust=True)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if len(df) > 50:
            df.index = df.index.tz_localize(None)
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                df.to_csv(SP500_CACHE)
            except OSError:
                pass
            return df, "live"
    except Exception:
        pass
    cached = _read_cache()
    return (cached, "cache") if cached is not None else (None, "none")


def weekly_ohlc(df: pd.DataFrame, weeks: int = 104) -> pd.DataFrame:
    """Resample daily OHLC to weekly candles (last `weeks`)."""
    w = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                  "Close": "last", "Volume": "sum"}).dropna()
    return w.tail(weeks)


def nyse_status(now: dt.datetime | None = None) -> tuple[bool, str]:
    """Approximate NYSE session (Mon–Fri 9:30–16:00 New York time; holidays ignored)."""
    from zoneinfo import ZoneInfo
    ny = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo("America/New_York"))
    open_ = ny.weekday() < 5 and dt.time(9, 30) <= ny.time() < dt.time(16, 0)
    return open_, ny.strftime("%H:%M ET")
