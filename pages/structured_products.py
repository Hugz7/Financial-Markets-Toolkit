"""
structured_products.py — Payoff analyzer with 20 legs, 20 instruments, strategy presets.
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
from config import (INSTRUMENTS, DIRECTIONS, STRATEGY_PRESETS,
                    PLOTLY_LAYOUT, ACCENT_GOLD, ACCENT_BLUE, ACCENT_GREEN,
                    ACCENT_RED, TEXT_GREY, ACCENT_CYAN)


def compute_leg_payoff(S_arr, instrument, direction, K, barrier, qty):
    """Compute payoff array for a single leg across spot prices."""
    if qty == 0 or instrument == "None":
        return np.zeros_like(S_arr)

    sign = 1 if direction == "Long" else -1

    if instrument == "Call":
        payoff = np.maximum(S_arr - K, 0)
    elif instrument == "Put":
        payoff = np.maximum(K - S_arr, 0)
    elif instrument == "Forward":
        payoff = S_arr - K
    elif instrument == "Digital Call":
        payoff = np.where(S_arr > K, barrier, 0.0)
    elif instrument == "Digital Put":
        payoff = np.where(S_arr < K, barrier, 0.0)
    elif instrument == "Barrier KI Call":
        payoff = np.where(S_arr > barrier, np.maximum(S_arr - K, 0), 0.0)
    elif instrument == "Barrier KI Put":
        payoff = np.where(S_arr < barrier, np.maximum(K - S_arr, 0), 0.0)
    elif instrument == "Barrier KO Call":
        payoff = np.where(S_arr < barrier, np.maximum(S_arr - K, 0), 0.0)
    elif instrument == "Barrier KO Put":
        payoff = np.where(S_arr > barrier, np.maximum(K - S_arr, 0), 0.0)
    elif instrument == "One-Touch Up":
        payoff = np.where(S_arr > barrier, 1.0, 0.0)
    elif instrument == "No-Touch Up":
        payoff = np.where(S_arr < barrier, 1.0, 0.0)
    elif instrument == "One-Touch Down":
        payoff = np.where(S_arr < barrier, 1.0, 0.0)
    elif instrument == "No-Touch Down":
        payoff = np.where(S_arr > barrier, 1.0, 0.0)
    elif instrument == "Gap Call":
        payoff = np.where(S_arr > barrier, S_arr - K, 0.0)
    elif instrument == "Range Accrual":
        payoff = np.where((S_arr > K) & (S_arr < barrier), 1.0, 0.0)
    elif instrument == "Autocall Coupon":
        payoff = np.where(S_arr >= K, barrier / 100.0, 0.0)
    elif instrument == "Bond":
        # Zero-coupon bond: pays face value K at maturity, flat payoff
        payoff = K * np.ones_like(S_arr)
    elif instrument == "Reverse Convertible":
        payoff = np.where(S_arr >= K, barrier, np.minimum(S_arr, K))
    elif instrument == "Straddle":
        payoff = np.abs(S_arr - K)
    else:
        payoff = np.zeros_like(S_arr)

    return sign * qty * payoff


def render():
    st.markdown("## Payoff Analyzer")
    st.caption("20 Legs · 20 Instruments · Vanilla · Barriers · Digitals · Bond · Strategy Presets")

    # ── Market Parameters ──
    col_mkt, col_preset = st.columns([1, 2])
    with col_mkt:
        st.markdown("#### Market Parameters")
        S0 = st.number_input("Spot Price S₀", value=100.0, step=1.0, key="sp_S0")
        S_min = st.number_input("Chart S_min", value=50.0, step=5.0, key="sp_smin")
        S_max = st.number_input("Chart S_max", value=150.0, step=5.0, key="sp_smax")
        n_points = st.slider("Nb Points", 100, 500, 300, key="sp_npts")
        bond_rate = st.number_input("Bond Rate r_b", value=0.04, step=0.005,
                                    format="%.3f", key="sp_bond_rate")
        st.caption(f"Bond PV(1yr) = K × e^(−r_b) ≈ K × {np.exp(-bond_rate):.4f}")

    # ── Strategy Presets ──
    with col_preset:
        st.markdown("#### Strategy Presets")
        preset = st.selectbox("Quick-load a strategy", list(STRATEGY_PRESETS.keys()), key="sp_preset")
        if preset != "── Select a preset ──":
            st.info(f"**{preset}** loaded → legs configured below. Adjust strikes/premiums as needed.")

    # ── Initialize leg state ──
    if "legs" not in st.session_state:
        st.session_state.legs = [
            dict(instrument="Call", direction="Long", K=100.0, barrier=0.0, T=1.0, premium=2.0, qty=1)
        ] + [
            dict(instrument="None", direction="Long", K=100.0, barrier=0.0, T=1.0, premium=0.0, qty=0)
            for _ in range(19)
        ]
    if "last_preset" not in st.session_state:
        st.session_state.last_preset = "── Select a preset ──"

    # Pre-initialize widget session state keys (avoids default-value conflict)
    for i in range(20):
        leg_i = st.session_state.legs[i]
        if f"sp_inst_{i}" not in st.session_state:
            st.session_state[f"sp_inst_{i}"] = leg_i["instrument"]
        if f"sp_dir_{i}" not in st.session_state:
            st.session_state[f"sp_dir_{i}"] = leg_i["direction"]
        if f"sp_K_{i}" not in st.session_state:
            st.session_state[f"sp_K_{i}"] = float(leg_i["K"])
        if f"sp_barr_{i}" not in st.session_state:
            st.session_state[f"sp_barr_{i}"] = float(leg_i["barrier"])
        if f"sp_prem_{i}" not in st.session_state:
            st.session_state[f"sp_prem_{i}"] = float(leg_i["premium"])
        if f"sp_qty_{i}" not in st.session_state:
            st.session_state[f"sp_qty_{i}"] = int(leg_i["qty"])

    # Apply preset only when it changes
    if preset != "── Select a preset ──" and preset != st.session_state.last_preset:
        st.session_state.last_preset = preset
        preset_data = STRATEGY_PRESETS[preset]
        for i in range(20):
            if i in preset_data:
                inst, dirn, K, barr, T, prem, qty = preset_data[i]
                st.session_state.legs[i] = dict(
                    instrument=inst, direction=dirn, K=float(K), barrier=float(barr),
                    T=float(T), premium=float(prem), qty=int(qty))
            else:
                st.session_state.legs[i] = dict(
                    instrument="None", direction="Long", K=100.0, barrier=0.0,
                    T=1.0, premium=0.0, qty=0)
            # Force widget state to match so the inputs re-render with preset values
            st.session_state[f"sp_inst_{i}"] = st.session_state.legs[i]["instrument"]
            st.session_state[f"sp_dir_{i}"] = st.session_state.legs[i]["direction"]
            st.session_state[f"sp_K_{i}"] = st.session_state.legs[i]["K"]
            st.session_state[f"sp_barr_{i}"] = st.session_state.legs[i]["barrier"]
            st.session_state[f"sp_prem_{i}"] = st.session_state.legs[i]["premium"]
            st.session_state[f"sp_qty_{i}"] = st.session_state.legs[i]["qty"]

    # ── Leg Configuration Table ──
    st.markdown("#### Instrument Legs (20 legs)")
    legs = st.session_state.legs

    # Display as editable columns
    n_visible = st.slider("Show legs", 2, 20, 6, key="sp_nlegs")

    for i in range(n_visible):
        leg = legs[i]
        cols = st.columns([1.5, 2.5, 1.2, 1.2, 1.2, 1.2, 1.2, 0.8])
        with cols[0]:
            if i == 0:
                st.caption("Leg")
            st.markdown(f"**Leg {i+1}**")
        with cols[1]:
            if i == 0:
                st.caption("Instrument")
            leg["instrument"] = st.selectbox(
                f"inst_{i}", INSTRUMENTS,
                key=f"sp_inst_{i}", label_visibility="collapsed")
        with cols[2]:
            if i == 0:
                st.caption("Direction")
            leg["direction"] = st.selectbox(
                f"dir_{i}", DIRECTIONS,
                key=f"sp_dir_{i}", label_visibility="collapsed")
        with cols[3]:
            if i == 0:
                st.caption("Strike / Face Value")
            leg["K"] = st.number_input(
                f"K_{i}", step=1.0,
                key=f"sp_K_{i}", label_visibility="collapsed")
        with cols[4]:
            if i == 0:
                st.caption("Barrier/Pay")
            leg["barrier"] = st.number_input(
                f"barr_{i}", step=1.0,
                key=f"sp_barr_{i}", label_visibility="collapsed")
        with cols[5]:
            if i == 0:
                st.caption("Premium")
            leg["premium"] = st.number_input(
                f"prem_{i}", step=0.5,
                key=f"sp_prem_{i}", label_visibility="collapsed")
        with cols[6]:
            if i == 0:
                st.caption("Qty")
            leg["qty"] = st.number_input(
                f"qty_{i}", step=1, min_value=0,
                key=f"sp_qty_{i}", label_visibility="collapsed")

    # ── Compute Payoffs ──
    S_arr = np.linspace(max(S_min, 0.01), S_max, n_points)
    total_payoff = np.zeros_like(S_arr)
    total_premium = 0.0
    leg_payoffs = {}

    for i, leg in enumerate(legs):
        if leg["qty"] > 0 and leg["instrument"] != "None":
            lp = compute_leg_payoff(
                S_arr, leg["instrument"], leg["direction"],
                leg["K"], leg["barrier"], leg["qty"])
            leg_payoffs[f"Leg {i+1}: {leg['instrument']}"] = lp
            total_payoff += lp
            prem_sign = -1 if leg["direction"] == "Long" else 1
            total_premium += prem_sign * leg["premium"] * leg["qty"]

    net_pnl = total_payoff + total_premium

    # ── Chart ──
    st.markdown("---")
    st.markdown("#### Payoff Diagram")

    fig = go.Figure()

    # Individual legs (thin lines)
    colors = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED, "#9B59B6", "#F39C12",
              "#1ABC9C", "#E67E22", "#3498DB", "#E91E63", "#00BCD4"] * 2
    for idx, (name, payoff) in enumerate(leg_payoffs.items()):
        fig.add_trace(go.Scatter(
            x=S_arr, y=payoff, name=name,
            line=dict(color=colors[idx % len(colors)], width=1, dash="dot"),
            opacity=0.6,
        ))

    # Total payoff
    fig.add_trace(go.Scatter(
        x=S_arr, y=total_payoff, name="Total Payoff",
        line=dict(color=ACCENT_CYAN, width=3),
    ))

    # Net P&L — green fill above zero, red fill below zero
    fig.add_trace(go.Scatter(
        x=S_arr, y=np.maximum(net_pnl, 0), name="_pnl_pos",
        line=dict(width=0), fill="tozeroy",
        fillcolor="rgba(16,212,138,0.14)", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=S_arr, y=np.minimum(net_pnl, 0), name="_pnl_neg",
        line=dict(width=0), fill="tozeroy",
        fillcolor="rgba(255,77,109,0.14)", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=S_arr, y=net_pnl, name="Net P&L (after premium)",
        line=dict(color=ACCENT_GREEN, width=2.5),
    ))

    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color=TEXT_GREY, line_width=1)
    # Spot marker
    fig.add_vline(x=S0, line_dash="dash", line_color=ACCENT_BLUE, line_width=1,
                  annotation_text=f"S₀={S0}")

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Payoff at Maturity",
        xaxis_title="Spot Price at Maturity (S_T)",
        yaxis_title="Payoff / P&L",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Summary Metrics ──
    col1, col2, col3, col4 = st.columns(4)
    breakeven_idx = np.where(np.diff(np.sign(net_pnl)))[0]
    breakevens = S_arr[breakeven_idx] if len(breakeven_idx) > 0 else []

    max_profit = np.max(net_pnl)
    max_loss = np.min(net_pnl)
    col1.metric("Max Profit", f"{max_profit:,.2f}")
    col2.metric("Max Loss", f"{max_loss:,.2f}")
    col3.metric("Net Premium", f"{total_premium:,.2f}")
    col4.metric("Breakeven(s)", ", ".join(f"{b:.1f}" for b in breakevens[:3]) or "N/A")

    # ── Preset Reference Table ──
    with st.expander("Strategy Presets Reference"):
        ref_data = []
        for name, preset_legs in STRATEGY_PRESETS.items():
            if name.startswith("──"):
                continue
            leg_desc = " + ".join(
                f"{v[1]} {v[0]} K={v[2]}" + (f" ×{v[6]}" if v[6] > 1 else "")
                for v in preset_legs.values())
            ref_data.append(dict(Strategy=name, Legs=leg_desc))
        st.dataframe(pd.DataFrame(ref_data), use_container_width=True, hide_index=True)
