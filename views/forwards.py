"""views/forwards.py — Equity, FX and commodity forward pricer."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from models.forwards import (
    annualised_forward_premium, commodity_forward, commodity_term_structure,
    equity_forward, equity_term_structure, forward_value, forward_vs_rate,
    forward_vs_spot, fx_forward, fx_term_structure, implied_cost_of_carry,
)
from ui.components import panel, Stat, callout, chart, hline_zero, page_header, require, section, stat_grid
from ui.theme import C, SERIES, rgba

_MODELS = {
    "Equity": "Cost of carry: F = S · e^((r − q)·T), where q is the continuous dividend yield.",
    "FX": "Covered interest parity: F = S · e^((r_d − r_f)·T), with S in domestic units per foreign unit.",
    "Commodity": "F = S · e^((r + u − c)·T), with storage cost u and convenience yield c (continuous, annual).",
}

LINE = SERIES[0]      # forward curve
MARK = SERIES[1]      # current maturity / spot markers
STRIKE = SERIES[7]    # delivery price K


def render():
    page_header(
        "Forward Contracts",
        "Cost-of-carry pricing for equity, FX and commodity forwards, with term structure and sensitivities.",
        eyebrow="Rates & Forwards",
    )

    model_choice = st.segmented_control("Forward type", list(_MODELS), default="Equity",
                                        key="fwd_model", label_visibility="collapsed")
    model_choice = model_choice or "Equity"
    fwd_type = model_choice.lower()  # "equity", "fx", "commodity"
    callout(_MODELS[model_choice], tone="neutral")

    col_in, col_res = st.columns([1, 2.4], gap="large")

    # ── Inputs ──
    with col_in:
        with panel():
            st.markdown("**Parameters**")
            S = st.number_input(
                "Spot price S" if fwd_type != "fx" else "Spot rate S (dom/for)",
                value=100.0, step=1.0, format="%.4f", key="fwd_S",
                help="Equity/commodity: price per unit. FX: domestic units per 1 foreign unit.",
            )
            r = st.number_input(
                "Risk-free rate r" if fwd_type != "fx" else "Domestic rate r_d",
                value=0.05, step=0.005, format="%.4f", key="fwd_r",
                help="Continuous risk-free rate (domestic rate for FX).",
            )
            q = r_f = u = c = 0.0
            if fwd_type == "equity":
                q = st.number_input("Dividend yield q", value=0.02, step=0.005, format="%.4f",
                                    key="fwd_q", help="Continuous dividend yield; b = r − q.")
            elif fwd_type == "fx":
                r_f = st.number_input("Foreign rate r_f", value=0.02, step=0.005, format="%.4f",
                                      key="fwd_rf", help="If r_d > r_f, F > S.")
            else:
                u = st.number_input("Storage cost u", value=0.03, step=0.005, format="%.4f",
                                    key="fwd_u", help="Continuous annual storage cost rate.")
                c = st.number_input("Convenience yield c", value=0.01, step=0.005, format="%.4f",
                                    key="fwd_c", help="Backwardation when c > r + u.")
            T = st.number_input("Maturity T (years)", value=1.0, step=0.25, format="%.2f", key="fwd_T")
            K = st.number_input(
                "Delivery price K (0 = new contract)", value=0.0, step=1.0, format="%.4f", key="fwd_K",
                help="Agreed price of an existing forward. Long value V = (F − K)·e^(−rT).",
            )

    require(S > 0, "Spot price S must be positive.")
    require(T > 0, "Maturity T must be greater than 0.")

    # ── Pricing ──
    if fwd_type == "equity":
        F = equity_forward(S, r, q, T)
    elif fwd_type == "fx":
        F = fx_forward(S, r, r_f, T)
    else:
        F = commodity_forward(S, r, u, c, T)

    basis = F - S
    carry_b = implied_cost_of_carry(S, F, T)
    ann_prem = annualised_forward_premium(S, F, T)
    fwd_val = forward_value(F, K, r, T) if K > 0 else 0.0

    with col_res:
        stats = [
            Stat("Forward price F", f"{F:,.4f}", hint=f"T = {T:.2f}y", tone="accent"),
            Stat("Basis F − S", f"{basis:+,.4f}", tone="pos" if basis >= 0 else "neg",
                 hint="contango" if basis >= 0 else "backwardation"),
            Stat("Cost of carry b", f"{carry_b:.4%}", hint="ln(F/S) / T"),
            Stat("Annualised premium", f"{ann_prem:+.3%}", hint="(F − S) / (S·T)"),
        ]
        if K > 0:
            stats += [
                Stat("Delivery price K", f"{K:,.4f}", hint="existing contract"),
                Stat("Forward value V", f"{fwd_val:+,.4f}", tone="pos" if fwd_val >= 0 else "neg",
                     hint="(F − K)·e^(−rT)"),
            ]
        stat_grid(stats, columns=2 if K == 0 else 3)
        if K == 0:
            st.caption("Set a delivery price K > 0 to value an existing forward position.")

    # ── Charts ──
    T_range = np.linspace(0, max(T * 3, 3.0), 200)
    if fwd_type == "equity":
        F_curve = equity_term_structure(S, r, q, T_range)
    elif fwd_type == "fx":
        F_curve = fx_term_structure(S, r, r_f, T_range)
    else:
        F_curve = commodity_term_structure(S, r, u, c, T_range)

    section("Analysis")
    tab_curve, tab_spot, tab_rate, tab_payoff = st.tabs(
        ["Term structure", "F vs spot", "F vs rate", "Payoff at maturity"])

    with tab_curve:
        fig = go.Figure()
        fig.add_hline(y=S, line_dash="dot", line_color=C.muted, line_width=1,
                      annotation_text=f"Spot {S:,.2f}", annotation_font_color=C.muted)
        fig.add_trace(go.Scatter(x=T_range, y=F_curve, mode="lines", name="Forward F(T)",
                                 line=dict(color=LINE),
                                 hovertemplate="T %{x:.2f}y · F %{y:.4f}<extra></extra>"))
        fig.add_vline(x=T, line_dash="dash", line_color=MARK, line_width=1)
        fig.add_trace(go.Scatter(x=[T], y=[F], mode="markers", name=f"F({T:.2f}y) = {F:.4f}",
                                 marker=dict(color=MARK, size=10, line=dict(color=C.bg, width=2))))
        if K > 0:
            fig.add_hline(y=K, line_dash="dash", line_color=STRIKE, line_width=1,
                          annotation_text=f"K {K:,.2f}", annotation_font_color=STRIKE)
        fig.update_layout(xaxis_title="Maturity T (years)", yaxis_title="Forward price",
                          hovermode="closest")
        chart(fig, height=380, title="Forward term structure")

        basis_curve = F_curve - S
        fig_b = go.Figure()
        fig_b.add_trace(go.Scatter(x=T_range, y=np.where(basis_curve >= 0, basis_curve, 0),
                                   fill="tozeroy", mode="lines", name="Contango (F > S)",
                                   line=dict(color=C.pos, width=1.5), fillcolor=rgba(C.pos, 0.15)))
        fig_b.add_trace(go.Scatter(x=T_range, y=np.where(basis_curve < 0, basis_curve, 0),
                                   fill="tozeroy", mode="lines", name="Backwardation (F < S)",
                                   line=dict(color=C.neg, width=1.5), fillcolor=rgba(C.neg, 0.15)))
        hline_zero(fig_b)
        fig_b.update_layout(xaxis_title="Maturity T (years)", yaxis_title="Basis")
        chart(fig_b, height=260, title="Forward basis F(T) − S")

    with tab_spot:
        S_lo, S_hi = max(S * 0.4, 1.0), S * 1.8
        S_rng = np.linspace(S_lo, S_hi, 300)
        F_vs_S = forward_vs_spot(S_rng, r, q, T, fwd_type=fwd_type, r_f=r_f, u=u, c=c)
        fig_s = go.Figure()
        fig_s.add_trace(go.Scatter(x=S_rng, y=F_vs_S, mode="lines", name="F(S)", line=dict(color=LINE),
                                   hovertemplate="S %{x:.2f} · F %{y:.4f}<extra></extra>"))
        fig_s.add_trace(go.Scatter(x=[S_lo, S_hi], y=[S_lo, S_hi], mode="lines", name="F = S (zero carry)",
                                   line=dict(color=C.muted, width=1, dash="dot")))
        fig_s.add_vline(x=S, line_dash="dash", line_color=MARK, line_width=1,
                        annotation_text=f"S₀ {S:,.2f}", annotation_font_color=MARK)
        if K > 0:
            fig_s.add_hline(y=K, line_dash="dash", line_color=STRIKE, line_width=1,
                            annotation_text=f"K {K:,.2f}", annotation_font_color=STRIKE)
        fig_s.update_layout(xaxis_title="Spot price S", yaxis_title="Forward price")
        chart(fig_s, height=400, title=f"Forward price vs spot (T = {T:.2f}y)")

    with tab_rate:
        r_rng = np.linspace(max(r - 0.05, -0.02), r + 0.08, 300)
        F_vs_r = forward_vs_rate(S, r_rng, q, T, fwd_type=fwd_type, r_f=r_f, u=u, c=c)
        r_label = "Domestic rate r_d (%)" if fwd_type == "fx" else "Risk-free rate r (%)"
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(x=r_rng * 100, y=F_vs_r, mode="lines", name="F(r)", line=dict(color=LINE),
                                   hovertemplate="r %{x:.2f}% · F %{y:.4f}<extra></extra>"))
        fig_r.add_vline(x=r * 100, line_dash="dash", line_color=MARK, line_width=1,
                        annotation_text=f"r {r * 100:.2f}%", annotation_font_color=MARK)
        if K > 0:
            fig_r.add_hline(y=K, line_dash="dash", line_color=STRIKE, line_width=1,
                            annotation_text=f"K {K:,.2f}", annotation_font_color=STRIKE)
        fig_r.update_layout(xaxis_title=r_label, yaxis_title="Forward price", showlegend=False)
        chart(fig_r, height=400, title=f"Forward price vs {r_label.split('(')[0].strip().lower()} (T = {T:.2f}y)")

    with tab_payoff:
        K_pay = K if K > 0 else F
        S_p = np.linspace(max(K_pay * 0.5, 1.0), K_pay * 1.6, 400)
        long_pnl = S_p - K_pay
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=S_p, y=np.where(long_pnl >= 0, long_pnl, 0), fill="tozeroy",
                                   mode="none", fillcolor=rgba(C.pos, 0.10), showlegend=False,
                                   hoverinfo="skip"))
        fig_p.add_trace(go.Scatter(x=S_p, y=np.where(long_pnl < 0, long_pnl, 0), fill="tozeroy",
                                   mode="none", fillcolor=rgba(C.neg, 0.10), showlegend=False,
                                   hoverinfo="skip"))
        fig_p.add_trace(go.Scatter(x=S_p, y=long_pnl, mode="lines", name=f"Long forward (K = {K_pay:,.2f})",
                                   line=dict(color=SERIES[0]),
                                   hovertemplate="S_T %{x:.2f} · P&L %{y:+.4f}<extra></extra>"))
        fig_p.add_trace(go.Scatter(x=S_p, y=-long_pnl, mode="lines", name=f"Short forward (K = {K_pay:,.2f})",
                                   line=dict(color=SERIES[1], dash="dash"),
                                   hovertemplate="S_T %{x:.2f} · P&L %{y:+.4f}<extra></extra>"))
        hline_zero(fig_p)
        fig_p.add_vline(x=K_pay, line_dash="dot", line_color=C.muted, line_width=1,
                        annotation_text=f"K {K_pay:,.2f}", annotation_font_color=C.muted)
        fig_p.add_vline(x=S, line_dash="dash", line_color=C.subtle, line_width=1,
                        annotation_text=f"S₀ {S:,.2f}", annotation_font_color=C.subtle,
                        annotation_position="bottom right")
        fig_p.update_layout(xaxis_title="Spot at maturity S_T", yaxis_title="P&L")
        chart(fig_p, height=420, title=f"Payoff at maturity (K = {K_pay:,.2f})")
        if K == 0:
            st.caption("K defaults to the current forward F when no existing position is set.")

    with st.expander("Methodology"):
        st.markdown("**Equity forward** — cost of carry b = r − q")
        st.latex(r"F = S\,e^{(r-q)T}")
        st.markdown("**FX forward** — covered interest rate parity")
        st.latex(r"F = S\,e^{(r_d-r_f)T}")
        st.markdown("**Commodity forward** — backwardation when c > r + u")
        st.latex(r"F = S\,e^{(r+u-c)T}")
        st.markdown("**Value of an existing long forward** entered at K with T years remaining")
        st.latex(r"V = (F-K)\,e^{-rT}")
        st.markdown("**Basis** F − S · **implied carry** ln(F/S)/T · **annualised premium** (F − S)/(S·T)")
