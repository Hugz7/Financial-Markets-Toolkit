"""views/swaps.py — Interest rate swap cashflow analyzer (IRS, basis, XCCY)."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from models.swaps import DAY_COUNTS, SWAP_TYPES, generate_swap_schedule, swap_metrics
from ui.components import panel, Stat, callout, chart, hline_zero, page_header, require, section, stat_grid
from ui.formatting import money, pct
from ui.theme import C, SERIES, rgba

_TYPE_NOTES = {
    "IRS Pay Fixed": "You pay the fixed rate and receive floating (rate + spread).",
    "IRS Receive Fixed": "You receive the fixed rate and pay floating (rate + spread).",
    "Basis Swap": "Float-for-float: Leg A pays the floating index flat, Leg B pays the index plus the spread. "
                  "The fixed rate input is not used.",
    "XCCY Swap": "Domestic fixed coupons against foreign floating coupons converted at FX spot; "
                 "the final period includes the notional re-exchange.",
}


def render():
    page_header(
        "Interest Rate Swaps",
        "Cashflow schedule, NPV, DV01 and break-even rate for vanilla IRS, basis and cross-currency swaps.",
        eyebrow="Rates & Forwards",
    )

    # ── Inputs ──
    with panel():
        c1, c2, c3, c4 = st.columns(4)
        swap_type = c1.selectbox("Swap type", SWAP_TYPES, key="sw_type")
        notional = c2.number_input("Notional", value=1_000_000, step=100_000, format="%d", key="sw_notional",
                                   help="Principal used to compute cashflows; never exchanged in a vanilla IRS.")
        currency = c3.text_input("Currency", "USD", key="sw_ccy")
        day_count = c4.selectbox("Day count", DAY_COUNTS, key="sw_dc",
                                 help="30/360 · ACT/360 (money market) · ACT/365.")

        c1, c2, c3, c4 = st.columns(4)
        fixed_rate = c1.number_input("Fixed rate", value=0.030, step=0.001, format="%.3f", key="sw_fixed",
                                     help="Fixed leg CF = N × r_fixed × α.")
        float_rate = c2.number_input("Floating rate (SOFR)", value=0.025, step=0.001, format="%.3f",
                                     key="sw_float", help="Floating reference rate, reset each period.")
        float_spread = c3.number_input("Floating spread", value=0.001, step=0.001, format="%.3f",
                                       key="sw_spread", help="Add-on to the floating rate.")
        discount_rate = c4.number_input("Discount rate", value=0.028, step=0.001, format="%.3f",
                                        key="sw_disc", help="OIS rate; df(t) = (1 + r)^(−t).")

        c1, c2, _, _ = st.columns(4)
        tenor = c1.number_input("Tenor (years)", value=5, step=1, key="sw_tenor")
        freq = c2.selectbox("Payments per year", [1, 2, 4, 12], index=1, key="sw_freq",
                            help="Year fraction α = 1 / frequency.")

    # XCCY parameters only matter for XCCY swaps
    fx_spot, foreign_notional, foreign_fixed, foreign_float = 1.08, int(notional * 1.08), 0.025, 0.020
    if swap_type == "XCCY Swap":
        with panel():
            st.markdown("**Cross-currency leg**")
            c1, c2, c3, c4, c5 = st.columns(5)
            fx_spot = c1.number_input("FX spot (dom/for)", value=1.08, step=0.01, format="%.4f", key="sw_fx")
            foreign_notional = c2.number_input("Foreign notional", value=int(notional * fx_spot),
                                               step=100_000, format="%d", key="sw_fn")
            foreign_fixed = c3.number_input("Foreign fixed rate", value=0.025, step=0.001,
                                            format="%.3f", key="sw_ffixed")
            foreign_float = c4.number_input("Foreign floating rate", value=0.020, step=0.001,
                                            format="%.3f", key="sw_ffloat")
            c5.text_input("Currency pair", "USD/EUR", key="sw_ccypair")

    callout(_TYPE_NOTES[swap_type], title=swap_type, tone="neutral")

    require(tenor > 0, "Tenor must be greater than 0.")
    require(discount_rate >= 0, "Discount rate must be non-negative.")
    require(fx_spot > 0, "FX spot must be positive.")

    # ── Schedule & metrics ──
    df = generate_swap_schedule(
        notional=notional, fixed_rate=fixed_rate, float_rate=float_rate,
        float_spread=float_spread, tenor=tenor, freq=freq,
        discount_rate=discount_rate, day_count=day_count, swap_type=swap_type,
        fx_spot=fx_spot, foreign_notional=foreign_notional,
        foreign_fixed=foreign_fixed, foreign_float=foreign_float,
    )
    m = swap_metrics(df, notional, fixed_rate, float_rate, float_spread, discount_rate, freq)

    if swap_type == "Basis Swap":
        leg_a, leg_b = "Leg A (index flat)", "Leg B (index + spread)"
    elif swap_type == "XCCY Swap":
        leg_a, leg_b = "Domestic fixed leg", "Foreign floating leg"
    else:
        leg_a, leg_b = "Fixed leg", "Floating leg"

    receive_fixed = swap_type == "IRS Receive Fixed"
    npv = m["npv_rec_fixed"] if receive_fixed else m["npv_pay_fixed"]
    net_col = "net_rec_fixed" if receive_fixed else "net_pay_fixed"

    section("Valuation")
    stat_grid([
        Stat(f"PV {leg_a.lower()}", money(m["pv_fixed"], ccy=currency)),
        Stat(f"PV {leg_b.lower()}", money(m["pv_float"], ccy=currency)),
        Stat("NPV (your side)", money(npv, ccy=currency), tone="pos" if npv >= 0 else "neg",
             hint="receive fixed" if receive_fixed else "pay leg A, receive leg B"),
        Stat("DV01", money(m["dv01"], ccy=currency), hint="PV change per 1 bp"),
        Stat("Break-even rate", pct(m["breakeven_rate"], 3), hint="fixed rate with NPV = 0"),
        Stat("Periods", f"{len(df)}", hint=f"{tenor}y × {freq}/yr"),
    ], columns=6)

    # ── Charts ──
    tab_cf, tab_npv, tab_table = st.tabs(["Cashflows", "Cumulative NPV", "Schedule"])

    with tab_cf:
        net = df[net_col]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["date"], y=net, name="Net cashflow",
                             marker_color=[C.pos if v >= 0 else C.neg for v in net],
                             hovertemplate="%{x}<br>Net %{y:+,.0f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=df["date"], y=df["fixed_cf"], name=leg_a, mode="lines+markers",
                                 line=dict(color=SERIES[0]), marker=dict(size=6),
                                 hovertemplate="%{x}<br>" + leg_a + " %{y:,.0f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=df["date"], y=df["float_cf"], name=leg_b, mode="lines+markers",
                                 line=dict(color=SERIES[1]), marker=dict(size=6),
                                 hovertemplate="%{x}<br>" + leg_b + " %{y:,.0f}<extra></extra>"))
        hline_zero(fig)
        fig.update_layout(yaxis_title=f"Cashflow ({currency})", hovermode="closest")
        fig.update_xaxes(tickangle=-30)
        chart(fig, height=420, title="Cashflows per period")
        if swap_type == "XCCY Swap":
            st.caption("The final period includes the notional re-exchange; the inception exchange is not shown.")

    with tab_npv:
        fig_n = go.Figure()
        fig_n.add_trace(go.Scatter(x=df["date"], y=df["cumul_npv"], mode="lines+markers", name="Cumulative NPV",
                                   line=dict(color=SERIES[0]), fill="tozeroy",
                                   fillcolor=rgba(SERIES[0], 0.12),
                                   hovertemplate="%{x}<br>Cumulative NPV %{y:+,.0f}<extra></extra>"))
        hline_zero(fig_n)
        fig_n.update_layout(yaxis_title=f"PV ({currency})", showlegend=False)
        fig_n.update_xaxes(tickangle=-30)
        chart(fig_n, height=380, title="Cumulative discounted net cashflow (pay leg A)")

    with tab_table:
        table = df.drop(columns=["pv_fixed_notional"]).rename(columns={
            "period": "Period", "date": "Date", "year_frac": "Year frac",
            "fixed_cf": f"{leg_a} CF", "float_cf": f"{leg_b} CF",
            "net_pay_fixed": "Net (pay A)", "net_rec_fixed": "Net (receive A)",
            "disc_factor": "Discount factor", "pv_fixed": f"PV {leg_a}", "pv_float": f"PV {leg_b}",
            "pv_net": "PV net", "cumul_npv": "Cumulative NPV",
        })
        money_cols = [c for c in table.columns if c not in ("Period", "Date", "Year frac", "Discount factor")]
        st.dataframe(
            table.style.format({**{c: "{:,.0f}" for c in money_cols},
                                "Year frac": "{:.4f}", "Discount factor": "{:.6f}"}),
            width="stretch", hide_index=True,
        )
