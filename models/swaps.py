"""
swaps.py — Interest Rate Swap cashflow analyzer.
Supports IRS Pay/Receive Fixed, Basis Swap, XCCY Swap.
"""

import numpy as np
import pandas as pd


def generate_swap_schedule(notional, fixed_rate, float_rate, float_spread,
                           tenor, freq, discount_rate, day_count="30/360",
                           swap_type="IRS Pay Fixed",
                           fx_spot=1.0, foreign_notional=None,
                           foreign_fixed=0.025, foreign_float=0.02):
    """
    Generate full cashflow schedule for a swap.

    Swap types
    ----------
    IRS Pay/Receive Fixed : fixed leg vs (float_rate + float_spread) leg.
    Basis Swap            : float_rate leg (Leg A) vs (float_rate + float_spread) leg (Leg B).
    XCCY Swap             : domestic fixed coupon vs foreign floating coupon (in domestic CCY).
                            Final period includes notional re-exchange.
    """
    n_periods = int(tenor * freq)
    year_frac = 1.0 / freq

    if day_count == "ACT/360":
        year_frac_adj = 365 / 360 * year_frac
    elif day_count == "ACT/365":
        year_frac_adj = year_frac
    else:  # 30/360
        year_frac_adj = year_frac

    if foreign_notional is None:
        foreign_notional = notional * fx_spot
    foreign_notional_dom = foreign_notional / fx_spot  # in domestic CCY

    rows = []
    cumul_npv = 0.0
    for i in range(1, n_periods + 1):
        t = i / freq
        df = (1 + discount_rate) ** (-t)

        if swap_type == "Basis Swap":
            # Float-for-float: Leg A (e.g. SOFR = float_rate flat),
            #                  Leg B (e.g. EURIBOR + basis = float_rate + float_spread).
            # fixed_rate input is not used — both legs are floating.
            fixed_cf = notional * float_rate * year_frac_adj
            float_cf = notional * (float_rate + float_spread) * year_frac_adj

        elif swap_type == "XCCY Swap":
            # Domestic fixed coupon vs foreign floating coupon (converted at fx_spot).
            # At final period, add notional re-exchange:
            #   pay back foreign notional (increases fixed_cf), receive domestic notional (increases float_cf).
            fixed_cf = notional * fixed_rate * year_frac_adj
            float_cf = foreign_notional_dom * foreign_float * year_frac_adj
            if i == n_periods:
                fixed_cf += foreign_notional_dom
                float_cf += notional

        else:
            # IRS Pay Fixed or IRS Receive Fixed
            fixed_cf = notional * fixed_rate * year_frac_adj
            float_cf = notional * (float_rate + float_spread) * year_frac_adj

        net_pay = float_cf - fixed_cf
        net_rec = fixed_cf - float_cf

        pv_fixed = fixed_cf * df
        pv_float = float_cf * df
        pv_net = net_pay * df
        cumul_npv += pv_net

        rows.append(dict(
            period=i,
            date=f"Y {t:.2f}",
            year_frac=round(year_frac_adj, 4),
            fixed_cf=round(fixed_cf, 2),
            float_cf=round(float_cf, 2),
            net_pay_fixed=round(net_pay, 2),
            net_rec_fixed=round(net_rec, 2),
            disc_factor=round(df, 6),
            pv_fixed=round(pv_fixed, 2),
            pv_float=round(pv_float, 2),
            pv_net=round(pv_net, 2),
            cumul_npv=round(cumul_npv, 2),
        ))

    return pd.DataFrame(rows)


def swap_metrics(df, notional, fixed_rate, float_rate, float_spread, discount_rate, freq):
    """Compute summary swap metrics from the schedule."""
    pv_fixed = df["pv_fixed"].sum()
    pv_float = df["pv_float"].sum()
    npv_pay = pv_float - pv_fixed
    npv_rec = pv_fixed - pv_float

    # DV01: PV change of the fixed annuity for a 1bp parallel shift.
    # = notional × Σ(disc_factor_i × year_frac_i) × 0.0001
    # Excludes notional re-exchange rows (year_frac unchanged, so the sum is over coupon accrual only).
    dv01 = notional * (df["disc_factor"] * df["year_frac"]).sum() * 0.0001

    # Break-even fixed rate: the rate that makes NPV = 0.
    annuity = (df["disc_factor"] * df["year_frac"]).sum()
    be_rate = (pv_float / (notional * annuity)) if annuity > 0 else 0

    return dict(
        pv_fixed=round(pv_fixed, 2),
        pv_float=round(pv_float, 2),
        npv_pay_fixed=round(npv_pay, 2),
        npv_rec_fixed=round(npv_rec, 2),
        dv01=round(dv01, 2),
        breakeven_rate=round(be_rate, 6),
    )
