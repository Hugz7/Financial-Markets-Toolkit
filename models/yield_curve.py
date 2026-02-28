"""
yield_curve.py — Yield Curve Bootstrapping & Spread Calculations.

Bootstraps zero/spot curve from T-Bills, T-Notes, T-Bonds.
Computes spot, forward, and par curves.
Z-spread and par-par ASW spread on fixed-rate bonds.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.interpolate import CubicSpline


# ── Bootstrapping ──────────────────────────────────────────────────────────────

def bootstrap_spot_rates(instruments: list) -> tuple:
    """
    Bootstrap zero/spot rates from a list of bond instruments sorted by maturity.

    Each instrument dict:
        type    : 'T-Bill' | 'T-Note' | 'T-Bond'
        maturity: float  — years to maturity
        rate    : float  — annual coupon rate (decimal) for notes/bonds;
                           annual yield (decimal) for T-Bills (simple spot)
        price   : float  — dirty price (default 100 = at par)
        freq    : int    — coupon payments per year (default 2)

    T-Bills are treated as zero-coupon:
        price = 100 / (1 + rate)^T   →   spot = (100/price)^(1/T) - 1

    T-Notes / T-Bonds: semi-annual coupon bootstrapping.
        P = Σ (C/freq × 100) × df(t_i)  +  100 × df(T)
        df(T) is solved for, using already-bootstrapped intermediate rates.

    Returns
    -------
    maturities : np.ndarray  (sorted ascending)
    spot_rates : np.ndarray  (continuously compounded equivalent, same index)
    """
    instruments = sorted(instruments, key=lambda x: x["maturity"])

    mats: list = []
    spots: list = []

    def _spot_at(t: float) -> float:
        """Linear interpolation of the current bootstrapped curve at time t."""
        if not mats:
            return 0.0
        return float(np.interp(t, mats, spots))

    def _df(t: float) -> float:
        """Discount factor using the bootstrapped spot curve."""
        z = _spot_at(t)
        return (1.0 + z) ** (-t)

    for inst in instruments:
        T      = float(inst["maturity"])
        itype  = inst.get("type", "T-Bond")
        price  = float(inst.get("price", 100.0))
        rate   = float(inst.get("rate", 0.05))
        freq   = int(inst.get("freq", 2))

        if itype == "T-Bill":
            # Zero-coupon: derive spot directly from price
            if price == 100.0:
                # Price implied from rate (BEY / simple yield)
                price = 100.0 / (1.0 + rate * T)
            z = (100.0 / price) ** (1.0 / T) - 1.0
            mats.append(T)
            spots.append(z)

        else:  # T-Note or T-Bond — coupon-bearing
            alpha     = 1.0 / freq          # year fraction per period
            n         = int(round(T * freq))
            cf_times  = np.array([i * alpha for i in range(1, n + 1)])
            cf_amounts = np.full(n, rate / freq * 100.0)
            cf_amounts[-1] += 100.0         # principal repayment at maturity

            # PV of all cashflows except the last, using bootstrapped rates
            pv_inter = sum(
                amt * _df(t)
                for amt, t in zip(cf_amounts[:-1], cf_times[:-1])
            )

            pv_last = price - pv_inter
            if pv_last <= 0:
                raise ValueError(
                    f"Bootstrapping failed at T={T}y: price={price:.4f} leaves "
                    f"non-positive PV for the final cashflow. "
                    f"Check instrument ordering and prices."
                )

            # (1 + z_T)^T = last_CF / pv_last
            z_T = (cf_amounts[-1] / pv_last) ** (1.0 / T) - 1.0
            mats.append(T)
            spots.append(z_T)

    return np.array(mats), np.array(spots)


# ── Curve Interpolation ────────────────────────────────────────────────────────

def interpolate_curve(
    maturities: np.ndarray,
    rates: np.ndarray,
    t_grid: np.ndarray,
    method: str = "cubic",
) -> np.ndarray:
    """
    Smooth the bootstrapped rates onto a fine grid.

    method: 'linear' | 'cubic'  (cubic spline, not-a-knot)
    Values outside the bootstrapped range are extrapolated flat.
    """
    if method == "cubic" and len(maturities) >= 4:
        cs = CubicSpline(maturities, rates, bc_type="not-a-knot", extrapolate=True)
        return cs(t_grid)
    return np.interp(t_grid, maturities, rates)


# ── Derived Curves ─────────────────────────────────────────────────────────────

def spot_to_forward(
    t_grid: np.ndarray,
    spot_grid: np.ndarray,
) -> np.ndarray:
    """
    Period-forward rates on a uniform grid:
        f(t_{i-1}, t_i) = [(1+z_i)^t_i / (1+z_{i-1})^t_{i-1}]^(1/dt) - 1

    Returns array same length as t_grid;  forward[0] = spot[0].
    """
    fwd = np.empty_like(spot_grid)
    fwd[0] = spot_grid[0]
    for i in range(1, len(t_grid)):
        dt  = t_grid[i] - t_grid[i - 1]
        df1 = (1.0 + spot_grid[i - 1]) ** t_grid[i - 1]
        df2 = (1.0 + spot_grid[i])     ** t_grid[i]
        fwd[i] = (df2 / df1) ** (1.0 / dt) - 1.0
    return fwd


def spot_to_par(
    t_grid: np.ndarray,
    spot_grid: np.ndarray,
    freq: int = 2,
) -> np.ndarray:
    """
    Par/coupon rates from the spot curve.
        par(T) = (1 − df(T)) / Σ df(t_i) × α

    where the sum runs over coupon dates at frequency `freq`.
    """
    alpha   = 1.0 / freq
    par     = np.zeros_like(t_grid)

    for j, T in enumerate(t_grid):
        n           = max(1, int(round(T * freq)))
        coup_times  = np.linspace(alpha, T, n)
        z_coup      = np.interp(coup_times, t_grid, spot_grid)
        dfs         = (1.0 + z_coup) ** (-coup_times)
        df_T        = (1.0 + spot_grid[j]) ** (-T)
        annuity     = dfs.sum() * alpha
        par[j]      = (1.0 - df_T) / annuity if annuity > 0 else np.nan

    return par


# ── Z-Spread ──────────────────────────────────────────────────────────────────

def z_spread(
    market_price: float,
    coupon: float,
    maturity: float,
    maturities: np.ndarray,
    spot_rates: np.ndarray,
    freq: int = 2,
) -> float:
    """
    Z-spread: constant spread zs added uniformly to every spot rate so that
    the discounted bond cashflows equal the market price.

        P = Σ CF_i / (1 + z_i + zs)^t_i

    Solved via Brent's method on [-5%, +50%].
    Returns decimal (e.g. 0.0050 = 50 bps).
    """
    alpha    = 1.0 / freq
    n        = int(round(maturity * freq))
    cf_times = np.array([i * alpha for i in range(1, n + 1)])
    coupons  = np.full(n, coupon / freq * 100.0)
    coupons[-1] += 100.0

    z_interp = np.interp(cf_times, maturities, spot_rates)

    def _pv(zs: float) -> float:
        return (coupons / (1.0 + z_interp + zs) ** cf_times).sum() - market_price

    try:
        return brentq(_pv, -0.05, 0.50, xtol=1e-9, maxiter=200)
    except ValueError:
        return np.nan


# ── ASW Spread (par-par) ───────────────────────────────────────────────────────

def asw_spread(
    market_price: float,
    coupon: float,
    maturity: float,
    maturities: np.ndarray,
    spot_rates: np.ndarray,
    freq: int = 2,
) -> float:
    """
    Par-par Asset Swap Spread.

    In a par-par ASW the bond's fixed cashflows are swapped to floating.
    The investor buys the bond at dirty price P and the swap notional is
    always 100 (par).  The spread s solves the breakeven:

        ASW = (coupon − par_swap_rate) + (100 − P) / (100 × annuity)

    where:
        par_swap_rate = (1 − df_T) / annuity    [fair IRS fixed rate]
        annuity       = Σ df(t_i) × α           [PV of unit annuity]

    Returns decimal (e.g. 0.0050 = 50 bps).
    """
    alpha    = 1.0 / freq
    n        = int(round(maturity * freq))
    cf_times = np.array([i * alpha for i in range(1, n + 1)])

    z_interp = np.interp(cf_times, maturities, spot_rates)
    dfs      = (1.0 + z_interp) ** (-cf_times)
    annuity  = (dfs * alpha).sum()

    df_T         = (1.0 + np.interp(maturity, maturities, spot_rates)) ** (-maturity)
    par_swap_rate = (1.0 - df_T) / annuity if annuity > 0 else np.nan

    return (coupon - par_swap_rate) + (100.0 - market_price) / (100.0 * annuity)


# ── Key Spread Metrics ─────────────────────────────────────────────────────────

def key_spreads(maturities: np.ndarray, spot_rates: np.ndarray) -> dict:
    """
    Compute standard slope/butterfly spreads from the bootstrapped curve.
    All values in basis points.
    """
    def _z(t: float) -> float:
        return float(np.interp(t, maturities, spot_rates))

    z3m  = _z(0.25)
    z2y  = _z(2.0)
    z5y  = _z(5.0)
    z10y = _z(10.0)
    z30y = _z(30.0)

    return {
        "3M":          z3m  * 100,
        "2Y":          z2y  * 100,
        "5Y":          z5y  * 100,
        "10Y":         z10y * 100,
        "30Y":         z30y * 100,
        "2s10s":       (z10y - z2y)  * 10_000,   # bps
        "3M10Y":       (z10y - z3m)  * 10_000,
        "10s30s":      (z30y - z10y) * 10_000,
        "5s30s":       (z30y - z5y)  * 10_000,
        "butterfly_2_5_10": (z2y + z10y - 2 * z5y) * 10_000,
    }
