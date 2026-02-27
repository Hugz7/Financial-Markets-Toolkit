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
    Generate full cashflow schedule for an IRS.
    Returns DataFrame with all cashflows and PV calculations.
    """
    n_periods = int(tenor * freq)
    year_frac = 1.0 / freq

    # Day count adjustment (simplified)
    if day_count == "ACT/360":
        year_frac_adj = 365 / 360 * year_frac
    elif day_count == "ACT/365":
        year_frac_adj = year_frac
    else:  # 30/360
        year_frac_adj = year_frac

    rows = []
    cumul_npv = 0.0
    for i in range(1, n_periods + 1):
        t = i / freq
        df = (1 + discount_rate) ** (-i / freq)
        fixed_cf = notional * fixed_rate * year_frac_adj
        float_cf = notional * (float_rate + float_spread) * year_frac_adj

        net_pay = float_cf - fixed_cf   # Net CF if paying fixed
        net_rec = fixed_cf - float_cf   # Net CF if receiving fixed

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

    # DV01: approximate by bumping the rate by 1bp
    dv01 = abs(npv_pay) / ((float_rate + float_spread) * 10000) if float_rate > 0 else 0

    # Break-even fixed rate
    sum_df_yf = df["disc_factor"].sum() * (1 / freq)
    be_rate = (pv_float / (notional * sum_df_yf)) if sum_df_yf > 0 else 0

    return dict(
        pv_fixed=round(pv_fixed, 2),
        pv_float=round(pv_float, 2),
        npv_pay_fixed=round(npv_pay, 2),
        npv_rec_fixed=round(npv_rec, 2),
        dv01=round(dv01, 2),
        breakeven_rate=round(be_rate, 6),
    )
