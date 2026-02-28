"""
swaps_page.py — Interest Rate Swap Cashflow Analyzer.
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
from config import (SWAP_TYPES, DAY_COUNTS, PLOTLY_LAYOUT, GRID_STYLE,
                    ACCENT_GOLD, ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED, TEXT_GREY,
                    ACCENT_CYAN)
from models.swaps import generate_swap_schedule, swap_metrics


def render():
    st.markdown("## Interest Rate Swap — Cashflow Analyzer")
    st.caption("IRS Pay/Receive Fixed · Basis Swap · XCCY Swap | Full Schedule, NPV, DV01")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Swap Parameters")
        swap_type = st.selectbox("Swap Type", SWAP_TYPES, key="sw_type",
                                  help="IRS Pay Fixed: you pay fixed, receive float. "
                                       "Basis Swap: float-for-float (e.g. SOFR vs EURIBOR). "
                                       "XCCY: cross-currency notional exchange at start and end.")
        notional = st.number_input("Notional (N)", value=1_000_000, step=100_000,
                                   format="%d", key="sw_notional",
                                   help="Principal used to calculate cashflows. "
                                        "Fixed CF = N × r_fixed × Δt. "
                                        "Never exchanged in a vanilla IRS.")
        fixed_rate = st.number_input("Fixed Rate", value=0.030, step=0.001,
                                     format="%.3f", key="sw_fixed",
                                     help="Annual fixed coupon rate r_K. "
                                          "Fixed leg CF = N × r_K × α (α = year fraction). "
                                          "Break-even rate = PV(float) / (N × Σ df_i × α).")
        float_rate = st.number_input("Floating Rate (SOFR/LIBOR)", value=0.025,
                                     step=0.001, format="%.3f", key="sw_float",
                                     help="Current floating reference rate (SOFR, EURIBOR…). "
                                          "Float CF = N × (r_float + spread) × α. "
                                          "Resets each period to the prevailing market rate.")
        float_spread = st.number_input("Floating Spread", value=0.001,
                                       step=0.001, format="%.3f", key="sw_spread",
                                       help="Basis-point add-on to the floating rate. "
                                            "Compensates for credit or liquidity premium. "
                                            "Effective float rate = r_float + spread.")
        tenor = st.number_input("Tenor (years)", value=5, step=1, key="sw_tenor",
                                help="Total life of the swap in years. "
                                     "Number of periods = tenor × frequency.")
        freq = st.selectbox("Payment Frequency (/year)", [1, 2, 4, 12], index=1, key="sw_freq",
                            help="Coupon payments per year. "
                                 "Year fraction α = 1/freq. "
                                 "More frequent payments → higher annuity factor.")
        discount_rate = st.number_input("Discount Rate", value=0.028,
                                        step=0.001, format="%.3f", key="sw_disc",
                                        help="OIS / risk-free rate used for discounting. "
                                             "Discount factor: df(t) = (1 + r)^(−t). "
                                             "NPV (pay fixed) = PV(float leg) − PV(fixed leg). "
                                             "DV01 ≈ ΔNPV for +1 bp shift in float rate.")
        day_count = st.selectbox("Day Count", DAY_COUNTS, key="sw_dc",
                                 help="Convention for computing year fractions. "
                                      "30/360: each month = 30 days, year = 360. "
                                      "ACT/360: actual days / 360 (money market). "
                                      "ACT/365: actual days / 365 (sterling, AUD).")
        currency = st.text_input("Currency", "USD", key="sw_ccy")

    with col2:
        st.markdown("#### XCCY / Basis Add-ons")
        fx_spot = st.number_input("FX Spot Rate", value=1.08, step=0.01,
                                  format="%.4f", key="sw_fx",
                                  help="Spot FX rate (domestic per foreign). "
                                       "Used to convert notionals in XCCY swaps. "
                                       "XCCY: notionals exchanged at start (spot) and end.")
        foreign_notional = st.number_input("Foreign Notional", value=int(notional * fx_spot),
                                           step=100_000, format="%d", key="sw_fn",
                                           help="Notional in the foreign currency leg. "
                                                "Typically: foreign_notional = domestic_notional × FX_spot.")
        foreign_fixed = st.number_input("Foreign Fixed Rate", value=0.025,
                                        step=0.001, format="%.3f", key="sw_ffixed",
                                        help="Fixed rate on the foreign currency leg (XCCY swap).")
        foreign_float = st.number_input("Foreign Floating Rate", value=0.020,
                                        step=0.001, format="%.3f", key="sw_ffloat",
                                        help="Floating reference rate in the foreign currency "
                                             "(e.g. EURIBOR for EUR leg).")
        ccy_pair = st.text_input("Currency Pair", "USD/EUR", key="sw_ccypair")

    st.markdown("---")

    # ── Generate Schedule ──
    df = generate_swap_schedule(
        notional=notional, fixed_rate=fixed_rate, float_rate=float_rate,
        float_spread=float_spread, tenor=tenor, freq=freq,
        discount_rate=discount_rate, day_count=day_count, swap_type=swap_type,
        fx_spot=fx_spot, foreign_notional=foreign_notional,
        foreign_fixed=foreign_fixed, foreign_float=foreign_float,
    )

    metrics = swap_metrics(df, notional, fixed_rate, float_rate, float_spread,
                           discount_rate, freq)

    # ── Summary Metrics ──
    st.markdown("#### Swap Metrics")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("PV Fixed Leg", f"{metrics['pv_fixed']:,.0f}")
    c2.metric("PV Floating Leg", f"{metrics['pv_float']:,.0f}")
    c3.metric("NPV (Pay Fixed)", f"{metrics['npv_pay_fixed']:,.0f}")
    c4.metric("NPV (Rec Fixed)", f"{metrics['npv_rec_fixed']:,.0f}")
    c5.metric("DV01 (approx)", f"{metrics['dv01']:,.0f}")
    c6.metric("Break-Even Rate", f"{metrics['breakeven_rate']:.3%}")

    # ── Cashflow Chart ──
    st.markdown("#### Cashflow Schedule")

    net_cf_col = "net_pay_fixed" if "Pay" in swap_type else "net_rec_fixed"

    fig = go.Figure()

    # ── Net CF bars — positive (pay float) = emerald, negative = rose ──
    net = df[net_cf_col]
    fig.add_trace(go.Bar(
        x=df["date"], y=np.where(net >= 0, net, 0), name="Net CF (inflow)",
        marker=dict(color="rgba(16,212,138,0.55)", line=dict(width=0)),
        hovertemplate="<b>Net inflow</b><br>%{x}<br>%{y:+,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["date"], y=np.where(net < 0, net, 0), name="Net CF (outflow)",
        marker=dict(color="rgba(255,77,109,0.50)", line=dict(width=0)),
        hovertemplate="<b>Net outflow</b><br>%{x}<br>%{y:+,.0f}<extra></extra>",
    ))

    # ── Fixed leg — thin line with small markers ──
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["fixed_cf"], name="Fixed Leg",
        mode="lines+markers",
        line=dict(color="rgba(56,189,248,0.70)", width=1.5, dash="dot"),
        marker=dict(size=4, color="#38BDF8", line=dict(width=0)),
        hovertemplate="<b>Fixed</b><br>%{x}<br>%{y:,.0f}<extra></extra>",
    ))

    # ── Floating leg — thin line ──
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["float_cf"], name="Floating Leg",
        mode="lines+markers",
        line=dict(color="rgba(167,139,250,0.70)", width=1.5, dash="dot"),
        marker=dict(size=4, color="#A78BFA", line=dict(width=0)),
        hovertemplate="<b>Float</b><br>%{x}<br>%{y:,.0f}<extra></extra>",
    ))

    # ── Cumulative NPV — secondary axis ──
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumul_npv"], name="Cumul. NPV",
        mode="lines",
        line=dict(color=ACCENT_GOLD, width=2),
        fill="tozeroy", fillcolor="rgba(240,180,41,0.06)",
        yaxis="y2",
        hovertemplate="<b>Cumul NPV</b><br>%{x}<br>%{y:,.0f}<extra></extra>",
    ))

    fig.add_hline(y=0, line_color="rgba(90,106,130,0.25)", line_width=1)

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"Cashflow Schedule — {swap_type}",
                   font=dict(size=14, color="#9BAEC8")),
        yaxis2=dict(
            title=dict(text="Cumul. NPV", font=dict(color=ACCENT_GOLD, size=10)),
            overlaying="y", side="right",
            showgrid=False, tickfont=dict(color=ACCENT_GOLD, size=9), zeroline=False,
        ),
        barmode="overlay",
        bargap=0.35,
        height=460,
    )
    fig.update_xaxes(showgrid=False, tickangle=-30, tickfont=dict(size=10))
    fig.update_yaxes(title_text=f"Cashflow ({currency})", showgrid=True,
                     gridcolor="#1A2E45", zeroline=False, selector=dict(overlaying=None))
    fig.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=10),
    ))
    st.plotly_chart(fig, use_container_width=True)

    # ── Schedule Table ──
    with st.expander("Full Schedule", expanded=False):
        display_df = df.copy()
        display_df.columns = [
            "Period", "Date", "Year Frac", "Fixed CF", "Floating CF",
            "Net CF (Pay Fix)", "Net CF (Rec Fix)", "Disc Factor",
            "PV Fixed", "PV Float", "PV Net", "Cumul NPV"
        ]
        st.dataframe(
            display_df.style.format({
                "Fixed CF": "{:,.0f}", "Floating CF": "{:,.0f}",
                "Net CF (Pay Fix)": "{:,.0f}", "Net CF (Rec Fix)": "{:,.0f}",
                "Disc Factor": "{:.6f}",
                "PV Fixed": "{:,.0f}", "PV Float": "{:,.0f}",
                "PV Net": "{:,.0f}", "Cumul NPV": "{:,.0f}",
            }),
            use_container_width=True, hide_index=True,
        )
