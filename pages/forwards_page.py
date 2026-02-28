"""
forwards_page.py — Forward Contracts Pricer.
Equity · FX · Commodity forwards with term-structure and sensitivity charts.
"""

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from config import (
    PLOTLY_LAYOUT, ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED,
    ACCENT_GOLD, TEXT_GREY,
)
from models.forwards import (
    equity_forward, fx_forward, commodity_forward,
    forward_value, implied_cost_of_carry, annualised_forward_premium,
    equity_term_structure, fx_term_structure, commodity_term_structure,
    forward_vs_spot, forward_vs_rate,
)

# ── Model catalogue ────────────────────────────────────────────────────────────

_MODELS = {
    "Equity": {
        "desc": "Equity forward priced by cost-of-carry: F = S · e^((r − q) · T). "
                "q is the continuous dividend yield. Includes sensitivity to spot and rate.",
        "color": ACCENT_CYAN,
    },
    "FX": {
        "desc": "FX forward via covered interest rate parity: F = S · e^((r_d − r_f) · T). "
                "S is the spot exchange rate (domestic per foreign unit).",
        "color": ACCENT_BLUE,
    },
    "Commodity": {
        "desc": "Commodity forward: F = S · e^((r + u − c) · T). "
                "u = storage cost rate, c = convenience yield (both continuous, annualised).",
        "color": ACCENT_GOLD,
    },
}


def _glass_card(label, value, color, sub=None):
    sub_html = (
        f"<div style='color:#5A6A82;font-size:0.68rem;margin-top:2px'>{sub}</div>"
        if sub else ""
    )
    return (
        f"<div style='background:rgba(8,18,32,0.72);backdrop-filter:blur(14px);"
        f"-webkit-backdrop-filter:blur(14px);border:1px solid rgba(0,229,255,0.13);"
        f"border-radius:8px;padding:11px 15px;box-shadow:0 2px 14px rgba(0,0,0,0.35)'>"
        f"<div style='color:#5A6A82;font-size:0.62rem;text-transform:uppercase;"
        f"letter-spacing:0.07em;font-weight:600;margin-bottom:3px'>{label}</div>"
        f"<div style='color:{color};font-size:1.12rem;font-weight:700;"
        f"font-variant-numeric:tabular-nums'>{value}</div>"
        f"{sub_html}</div>"
    )


def render():
    st.markdown("## Forward Contracts")
    st.caption("Equity · FX · Commodity — cost-of-carry pricing, term structure & sensitivities")

    # ── Model selector ──────────────────────────────────────────────────────────
    model_choice = st.radio(
        "Forward type", list(_MODELS.keys()), horizontal=True, key="fwd_model"
    )
    _minfo = _MODELS[model_choice]
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.65);border-left:3px solid {_minfo['color']};"
        f"border-radius:0 6px 6px 0;padding:8px 14px;margin:4px 0 14px 0;"
        f"color:#9BAEC8;font-size:0.82rem'>{_minfo['desc']}</div>",
        unsafe_allow_html=True,
    )
    fwd_type = model_choice.lower()  # "equity", "fx", "commodity"

    st.markdown("---")

    # ── Inputs ─────────────────────────────────────────────────────────────────
    col_in, col_res = st.columns([1, 1], gap="large")

    with col_in:
        st.markdown("#### Parameters")
        S = st.number_input(
            "Spot Price S" if fwd_type != "fx" else "Spot Rate S (dom/for)",
            value=100.0, step=1.0, format="%.4f", key="fwd_S",
            help=(
                "Current spot price of the underlying. "
                "Equity/Commodity: price per share or unit. "
                "FX: domestic units per 1 foreign unit (e.g. 1.08 USD/EUR)."
            ),
        )
        r = st.number_input(
            "Risk-Free Rate r" if fwd_type != "fx" else "Domestic Rate r_d",
            value=0.05, step=0.005, format="%.4f", key="fwd_r",
            help=(
                "Continuous risk-free rate (or domestic rate for FX). "
                "Equity: F = S·e^((r−q)·T). "
                "FX: F = S·e^((r_d−r_f)·T)  [covered interest parity]. "
                "Commodity: F = S·e^((r+u−c)·T)."
            ),
        )

        if fwd_type == "equity":
            q = st.number_input("Dividend Yield q", value=0.02,
                                step=0.005, format="%.4f", key="fwd_q",
                                help="Continuous dividend yield. "
                                     "Reduces the cost of carry: b = r − q. "
                                     "High q → F < S·e^(r·T) (forward at a discount).")
            r_f = 0.0; u = 0.0; c = 0.0
        elif fwd_type == "fx":
            r_f = st.number_input("Foreign Rate r_f", value=0.02,
                                  step=0.005, format="%.4f", key="fwd_rf",
                                  help="Foreign risk-free rate (continuous). "
                                       "Covered Interest Parity: F = S·e^((r_d−r_f)·T). "
                                       "If r_d > r_f → F > S (domestic currency at premium). "
                                       "Deviations create arbitrage via forward contracts.")
            q = 0.0; u = 0.0; c = 0.0
        else:  # commodity
            u = st.number_input("Storage Cost u (annual)", value=0.03,
                                step=0.005, format="%.4f", key="fwd_u",
                                help="Continuous annual storage cost rate. "
                                     "Increases the forward: you must be compensated for "
                                     "holding the physical commodity. b = r + u − c.")
            c = st.number_input("Convenience Yield c (annual)", value=0.01,
                                step=0.005, format="%.4f", key="fwd_c",
                                help="Convenience yield: benefit of holding physical inventory "
                                     "(e.g. avoiding production shutdown). "
                                     "Reduces the forward. Backwardation: c > r + u → F < S.")
            q = 0.0; r_f = 0.0

        T = st.number_input("Maturity T (years)", value=1.0,
                            step=0.25, format="%.2f", key="fwd_T",
                            help="Time to delivery / maturity in years. "
                                 "Forward price grows with T when the cost of carry is positive. "
                                 "Value of existing forward decays toward (F−K) as T→0.")

        K = st.number_input(
            "Delivery Price K (existing forward — 0 = new)",
            value=0.0, step=1.0, format="%.4f", key="fwd_K",
            help="Agreed delivery price at contract inception. "
                 "Value of long forward: V = (F − K)·e^(−r·T). "
                 "V > 0 if current F > K (you locked in a cheap buy). "
                 "Set to 0 for a new contract (V = 0 by definition at inception).",
        )

    # ── Forward price computation ──────────────────────────────────────────────
    if fwd_type == "equity":
        F = equity_forward(S, r, q, T)
    elif fwd_type == "fx":
        F = fx_forward(S, r, r_f, T)
    else:
        F = commodity_forward(S, r, u, c, T)

    basis     = F - S
    carry_b   = implied_cost_of_carry(S, F, T)
    ann_prem  = annualised_forward_premium(S, F, T) * 100
    K_eff     = K if K > 0 else F
    fwd_val   = forward_value(F, K_eff, r, T) if K > 0 else 0.0

    # ── Metrics panel ──────────────────────────────────────────────────────────
    with col_res:
        st.markdown("#### Results")
        st.markdown(
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px'>"
            + _glass_card("Forward Price F", f"{F:.4f}", _minfo["color"],
                          sub=f"T = {T:.2f}y")
            + _glass_card("Basis  F − S", f"{basis:+.4f}",
                          ACCENT_GREEN if basis >= 0 else ACCENT_RED,
                          sub="contango" if basis >= 0 else "backwardation")
            + _glass_card("Cost of Carry  b", f"{carry_b:.4f}",
                          ACCENT_BLUE,
                          sub="ln(F/S) / T")
            + _glass_card("Ann. Premium", f"{ann_prem:+.3f}%",
                          ACCENT_GOLD,
                          sub="(F − S) / (S · T)")
            + "</div>",
            unsafe_allow_html=True,
        )
        if K > 0:
            st.markdown(
                "<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;"
                "margin-top:8px'>"
                + _glass_card("Delivery K (entered)", f"{K:.4f}", TEXT_GREY)
                + _glass_card("Forward Value V", f"{fwd_val:+.4f}",
                              ACCENT_GREEN if fwd_val >= 0 else ACCENT_RED,
                              sub="(F − K) · e^(−rT)")
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='color:#3A4A5C;font-size:0.75rem;margin-top:8px;padding:6px 0'>",
                unsafe_allow_html=True,
            )
            st.caption("Set Delivery Price K > 0 to value an existing forward position.")

    st.markdown("---")

    # ── Charts ─────────────────────────────────────────────────────────────────
    T_max = max(T * 3, 3.0)
    T_range = np.linspace(0, T_max, 200)

    if fwd_type == "equity":
        F_curve = equity_term_structure(S, r, q, T_range)
    elif fwd_type == "fx":
        F_curve = fx_term_structure(S, r, r_f, T_range)
    else:
        F_curve = commodity_term_structure(S, r, u, c, T_range)

    tab_curve, tab_spot, tab_rate, tab_payoff = st.tabs([
        "Term Structure", "F vs Spot", "F vs Rate", "Payoff at Maturity",
    ])

    # ── Tab 1: Forward Curve ────────────────────────────────────────────────────
    with tab_curve:
        fig = go.Figure()

        # Fill contango / backwardation zone
        contango_mask = F_curve >= S
        backw_mask    = F_curve < S

        if contango_mask.any():
            fig.add_trace(go.Scatter(
                x=T_range[contango_mask], y=F_curve[contango_mask],
                fill="tonexty", mode="none",
                fillcolor="rgba(16,212,138,0.08)", showlegend=False,
            ))
        if backw_mask.any():
            fig.add_trace(go.Scatter(
                x=T_range[backw_mask], y=F_curve[backw_mask],
                fill="tonexty", mode="none",
                fillcolor="rgba(255,77,109,0.08)", showlegend=False,
            ))

        fig.add_hline(y=S, line_dash="dot", line_color=TEXT_GREY, line_width=1,
                      annotation_text=f"Spot S = {S:.2f}",
                      annotation_font_color=TEXT_GREY, annotation_font_size=10)

        fig.add_trace(go.Scatter(
            x=T_range, y=F_curve,
            mode="lines",
            line=dict(color=_minfo["color"], width=2.5),
            name="Forward Price F(T)",
            hovertemplate="<b>T</b>: %{x:.2f}y<br><b>F</b>: %{y:.4f}<extra></extra>",
        ))

        # Mark current T
        fig.add_vline(x=T, line_dash="dash", line_color=ACCENT_GOLD, line_width=1.2,
                      annotation_text=f"T = {T:.2f}y", annotation_font_color=ACCENT_GOLD,
                      annotation_font_size=10)
        fig.add_trace(go.Scatter(
            x=[T], y=[F],
            mode="markers",
            marker=dict(color=ACCENT_GOLD, size=9, symbol="circle",
                        line=dict(color="#080C14", width=2)),
            name=f"F({T:.2f}y) = {F:.4f}",
            showlegend=True,
        ))

        if K > 0:
            fig.add_hline(y=K, line_dash="dash", line_color=ACCENT_RED, line_width=1,
                          annotation_text=f"K = {K:.2f}", annotation_font_color=ACCENT_RED,
                          annotation_font_size=10)

        fig.update_layout(
            **PLOTLY_LAYOUT,
            title="Forward Price Term Structure",
            xaxis_title="Maturity T (years)",
            yaxis_title="Forward Price F",
            height=380,
        )
        fig.update_layout(legend=dict(x=0.01, y=0.99))
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#1A2E45")
        st.plotly_chart(fig, use_container_width=True)

        # Basis curve below
        fig_basis = go.Figure()
        basis_curve = F_curve - S
        pos = np.where(basis_curve >= 0, basis_curve, 0)
        neg = np.where(basis_curve < 0, basis_curve, 0)
        fig_basis.add_trace(go.Bar(
            x=T_range, y=pos, name="Contango (F > S)",
            marker_color="rgba(16,212,138,0.50)", marker_line_width=0,
        ))
        fig_basis.add_trace(go.Bar(
            x=T_range, y=neg, name="Backwardation (F < S)",
            marker_color="rgba(255,77,109,0.45)", marker_line_width=0,
        ))
        fig_basis.update_layout(
            **PLOTLY_LAYOUT,
            barmode="overlay", bargap=0,
            title="Forward Basis  F(T) − S",
            xaxis_title="Maturity T (years)",
            yaxis_title="Basis",
            height=260, showlegend=True,
        )
        fig_basis.update_layout(legend=dict(x=0.01, y=0.99))
        fig_basis.update_xaxes(showgrid=False)
        fig_basis.update_yaxes(showgrid=True, gridcolor="#1A2E45",
                               zerolinecolor="#1A2E45", zeroline=True)
        st.plotly_chart(fig_basis, use_container_width=True)

    # ── Tab 2: F vs Spot ───────────────────────────────────────────────────────
    with tab_spot:
        S_lo = max(S * 0.4, 1.0)
        S_hi = S * 1.8
        S_rng = np.linspace(S_lo, S_hi, 300)
        F_vs_S = forward_vs_spot(S_rng, r, q, T, fwd_type=fwd_type, r_f=r_f, u=u, c=c)

        fig_s = go.Figure()
        fig_s.add_trace(go.Scatter(
            x=S_rng, y=F_vs_S, mode="lines",
            line=dict(color=_minfo["color"], width=2.5),
            name="F(S)",
            hovertemplate="<b>S</b>: %{x:.2f}<br><b>F</b>: %{y:.4f}<extra></extra>",
        ))
        # 45° identity line (F = S)
        fig_s.add_trace(go.Scatter(
            x=[S_lo, S_hi], y=[S_lo, S_hi],
            mode="lines", line=dict(color=TEXT_GREY, width=1, dash="dot"),
            name="F = S (zero carry)", showlegend=True,
        ))
        fig_s.add_vline(x=S, line_dash="dash", line_color=ACCENT_GOLD, line_width=1.2,
                        annotation_text=f"S₀ = {S:.2f}", annotation_font_color=ACCENT_GOLD,
                        annotation_font_size=10)
        if K > 0:
            fig_s.add_hline(y=K, line_dash="dash", line_color=ACCENT_RED, line_width=1,
                            annotation_text=f"K = {K:.2f}", annotation_font_color=ACCENT_RED,
                            annotation_font_size=10)
        fig_s.update_layout(
            **PLOTLY_LAYOUT,
            title=f"Forward Price vs Spot  (T = {T:.2f}y)",
            xaxis_title="Spot Price S",
            yaxis_title="Forward Price F",
            height=400,
        )
        fig_s.update_layout(legend=dict(x=0.01, y=0.99))
        fig_s.update_xaxes(showgrid=False)
        fig_s.update_yaxes(showgrid=True, gridcolor="#1A2E45")
        st.plotly_chart(fig_s, use_container_width=True)

    # ── Tab 3: F vs Rate ───────────────────────────────────────────────────────
    with tab_rate:
        r_lo = max(r - 0.05, -0.02)
        r_hi = r + 0.08
        r_rng = np.linspace(r_lo, r_hi, 300)
        F_vs_r = forward_vs_rate(S, r_rng, q, T, fwd_type=fwd_type, r_f=r_f, u=u, c=c)

        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(
            x=r_rng * 100, y=F_vs_r, mode="lines",
            line=dict(color=_minfo["color"], width=2.5),
            name="F(r)",
            hovertemplate="<b>r</b>: %{x:.2f}%<br><b>F</b>: %{y:.4f}<extra></extra>",
        ))
        fig_r.add_vline(x=r * 100, line_dash="dash", line_color=ACCENT_GOLD, line_width=1.2,
                        annotation_text=f"r = {r*100:.2f}%", annotation_font_color=ACCENT_GOLD,
                        annotation_font_size=10)
        if K > 0:
            fig_r.add_hline(y=K, line_dash="dash", line_color=ACCENT_RED, line_width=1,
                            annotation_text=f"K = {K:.2f}", annotation_font_color=ACCENT_RED,
                            annotation_font_size=10)
        r_label = "Domestic Rate r_d (%)" if fwd_type == "fx" else "Risk-Free Rate r (%)"
        fig_r.update_layout(
            **PLOTLY_LAYOUT,
            title=f"Forward Price vs {r_label.split('(')[0].strip()}  (T = {T:.2f}y)",
            xaxis_title=r_label,
            yaxis_title="Forward Price F",
            height=400,
        )
        fig_r.update_xaxes(showgrid=False)
        fig_r.update_yaxes(showgrid=True, gridcolor="#1A2E45")
        st.plotly_chart(fig_r, use_container_width=True)

    # ── Tab 4: Payoff at Maturity ──────────────────────────────────────────────
    with tab_payoff:
        K_pay = K if K > 0 else F
        S_lo_p = max(K_pay * 0.50, 1.0)
        S_hi_p = K_pay * 1.60
        S_p    = np.linspace(S_lo_p, S_hi_p, 400)

        long_pnl  = S_p - K_pay
        short_pnl = K_pay - S_p

        fig_p = go.Figure()

        # Long forward
        fig_p.add_trace(go.Scatter(
            x=S_p, y=long_pnl, mode="lines",
            line=dict(color=ACCENT_CYAN, width=2.5),
            name=f"Long Forward  (K = {K_pay:.2f})",
            hovertemplate="<b>S_T</b>: %{x:.2f}<br><b>P&L</b>: %{y:+.4f}<extra></extra>",
        ))
        # Short forward (dashed)
        fig_p.add_trace(go.Scatter(
            x=S_p, y=short_pnl, mode="lines",
            line=dict(color=ACCENT_RED, width=1.8, dash="dash"),
            name=f"Short Forward  (K = {K_pay:.2f})",
            hovertemplate="<b>S_T</b>: %{x:.2f}<br><b>P&L</b>: %{y:+.4f}<extra></extra>",
        ))

        # Fill P&L zones
        fig_p.add_trace(go.Scatter(
            x=S_p, y=np.where(long_pnl >= 0, long_pnl, 0),
            fill="tozeroy", mode="none",
            fillcolor="rgba(16,212,138,0.10)", showlegend=False,
        ))
        fig_p.add_trace(go.Scatter(
            x=S_p, y=np.where(long_pnl < 0, long_pnl, 0),
            fill="tozeroy", mode="none",
            fillcolor="rgba(255,77,109,0.10)", showlegend=False,
        ))

        fig_p.add_vline(x=K_pay, line_dash="dot", line_color=TEXT_GREY, line_width=1,
                        annotation_text=f"K = {K_pay:.2f}",
                        annotation_font_color=TEXT_GREY, annotation_font_size=10)
        fig_p.add_hline(y=0, line_color="#1A2E45", line_width=1)
        fig_p.add_vline(x=S, line_dash="dash", line_color=ACCENT_GOLD, line_width=1,
                        annotation_text=f"S₀ = {S:.2f}", annotation_font_color=ACCENT_GOLD,
                        annotation_font_size=10, annotation_position="bottom right")

        fig_p.update_layout(
            **PLOTLY_LAYOUT,
            title=f"Forward Payoff at Maturity  (K = {K_pay:.2f})",
            xaxis_title="Spot at Maturity  S_T",
            yaxis_title="P&L",
            height=420,
        )
        fig_p.update_layout(legend=dict(x=0.01, y=0.99))
        fig_p.update_xaxes(showgrid=False)
        fig_p.update_yaxes(showgrid=True, gridcolor="#1A2E45",
                           zeroline=True, zerolinecolor="#1A2E45")
        st.plotly_chart(fig_p, use_container_width=True)

        if K == 0:
            st.caption(
                "Delivery price K defaults to the current forward F when no existing "
                "position is set. Enter a K > 0 above to price an existing position."
            )

    # ── Formulas reference ──────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("Formulas Reference"):
        st.markdown("""
**Equity Forward**
$$F = S \\cdot e^{(r - q) \\cdot T}$$
Where $q$ = continuous dividend yield.
Cost of carry $b = r - q$.

---
**FX Forward** — Covered Interest Rate Parity
$$F = S \\cdot e^{(r_d - r_f) \\cdot T}$$
$r_d$ = domestic rate, $r_f$ = foreign rate.
$F > S$ when $r_d > r_f$ (domestic currency at discount).

---
**Commodity Forward**
$$F = S \\cdot e^{(r + u - c) \\cdot T}$$
$u$ = storage cost rate, $c$ = convenience yield.
Backwardation occurs when $c > r + u$.

---
**Value of existing long forward** (entered at $K$, $T$ years remaining)
$$V = (F - K) \\cdot e^{-r \\cdot T}$$

---
**Forward Basis** = $F - S$ (contango if positive, backwardation if negative)
**Implied carry** $b = \\ln(F/S) / T$
**Ann. premium** = $(F - S) / (S \\cdot T)$
        """)
