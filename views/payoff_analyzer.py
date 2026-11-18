"""views/payoff_analyzer.py — Multi-leg payoff analyzer (20 legs, 20 instruments, presets)."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.payoffs import (DIRECTIONS, INSTRUMENTS, NO_PRESET, STRATEGY_PRESETS,
                            compute_leg_payoff)
from ui.components import Stat, callout, chart, page_header, section, stat_grid
from ui.formatting import num
from ui.theme import C, SERIES, rgba

N_LEGS = 20
_EMPTY_LEG = dict(instrument="None", direction="Long", K=100.0, barrier=0.0,
                  T=1.0, premium=0.0, qty=0.0)
# Column widths for the leg editor: label, instrument, direction, K, barrier, premium, qty
_LEG_COLS = [0.7, 2.4, 1.2, 1.2, 1.2, 1.2, 1.0]


def _init_legs() -> None:
    """Create leg state once and pre-seed widget keys (avoids default-value conflicts)."""
    if "legs" not in st.session_state:
        st.session_state.legs = [
            dict(instrument="Call", direction="Long", K=100.0, barrier=0.0, T=1.0,
                 premium=2.0, qty=1.0)
        ] + [dict(_EMPTY_LEG) for _ in range(N_LEGS - 1)]
    else:
        for leg in st.session_state.legs:  # legacy int qty → float
            leg["qty"] = float(leg["qty"])
    st.session_state.setdefault("last_preset", NO_PRESET)

    for i, leg in enumerate(st.session_state.legs):
        st.session_state.setdefault(f"sp_inst_{i}", leg["instrument"])
        st.session_state.setdefault(f"sp_dir_{i}", leg["direction"])
        st.session_state.setdefault(f"sp_K_{i}", float(leg["K"]))
        st.session_state.setdefault(f"sp_barr_{i}", float(leg["barrier"]))
        st.session_state.setdefault(f"sp_prem_{i}", float(leg["premium"]))
        if not isinstance(st.session_state.setdefault(f"sp_qty_{i}", float(leg["qty"])), float):
            st.session_state[f"sp_qty_{i}"] = float(st.session_state[f"sp_qty_{i}"])


def _apply_preset(preset: str) -> None:
    """Load a preset into leg state and widget state (only when the preset changes)."""
    if preset == NO_PRESET or preset == st.session_state.last_preset:
        return
    st.session_state.last_preset = preset
    data = STRATEGY_PRESETS[preset]
    for i in range(N_LEGS):
        if i in data:
            inst, dirn, K, barr, T, prem, qty = data[i]
            leg = dict(instrument=inst, direction=dirn, K=float(K), barrier=float(barr),
                       T=float(T), premium=float(prem), qty=float(qty))
        else:
            leg = dict(_EMPTY_LEG)
        st.session_state.legs[i] = leg
        st.session_state[f"sp_inst_{i}"] = leg["instrument"]
        st.session_state[f"sp_dir_{i}"] = leg["direction"]
        st.session_state[f"sp_K_{i}"] = leg["K"]
        st.session_state[f"sp_barr_{i}"] = leg["barrier"]
        st.session_state[f"sp_prem_{i}"] = leg["premium"]
        st.session_state[f"sp_qty_{i}"] = float(leg["qty"])


def _leg_editor(legs: list[dict], n_visible: int) -> None:
    head = st.columns(_LEG_COLS)
    for col, label in zip(head, ["Leg", "Instrument", "Side", "Strike / Face",
                                 "Barrier / Pay", "Premium", "Qty"]):
        col.caption(label)
    for i in range(n_visible):
        leg = legs[i]
        cols = st.columns(_LEG_COLS, vertical_alignment="center")
        cols[0].markdown(f"**{i + 1}**")
        leg["instrument"] = cols[1].selectbox(f"inst_{i}", INSTRUMENTS, key=f"sp_inst_{i}",
                                              label_visibility="collapsed")
        leg["direction"] = cols[2].selectbox(f"dir_{i}", DIRECTIONS, key=f"sp_dir_{i}",
                                             label_visibility="collapsed")
        leg["K"] = cols[3].number_input(f"K_{i}", step=1.0, key=f"sp_K_{i}",
                                        label_visibility="collapsed")
        leg["barrier"] = cols[4].number_input(f"barr_{i}", step=1.0, key=f"sp_barr_{i}",
                                              label_visibility="collapsed")
        leg["premium"] = cols[5].number_input(f"prem_{i}", step=0.5, key=f"sp_prem_{i}",
                                              label_visibility="collapsed")
        leg["qty"] = cols[6].number_input(f"qty_{i}", step=0.5, min_value=0.0, format="%.2f",
                                          key=f"sp_qty_{i}", label_visibility="collapsed")


def render():
    page_header(
        "Payoff Analyzer",
        "Build multi-leg structures from 20 instruments — vanillas, barriers, digitals, "
        "bonds — and read the payoff and P&L at maturity.",
        eyebrow="Options",
    )

    # ── Setup ──
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
        preset = c1.selectbox("Strategy preset", list(STRATEGY_PRESETS), key="sp_preset",
                              help="Quick-load a classic strategy into the legs below.")
        S0 = c2.number_input("Spot S₀", value=100.0, step=1.0, key="sp_S0")
        # Widget keys are dropped when the user navigates away; this plain key persists
        # so other pages (Exotic Pricer) can import the spot.
        st.session_state["shared_spot"] = S0
        S_min = c3.number_input("Chart S min", value=50.0, step=5.0, key="sp_smin")
        S_max = c4.number_input("Chart S max", value=150.0, step=5.0, key="sp_smax")

        c5, c6, c7 = st.columns([2.2, 1, 2])
        n_points = c5.slider("Resolution (points)", 100, 500, 300, key="sp_npts")
        bond_rate = c6.number_input("Bond rate r_b", value=0.04, step=0.005, format="%.3f",
                                    key="sp_bond_rate",
                                    help="Used for the bond PV reference: PV(1y) = K·e^(−r_b).")
        n_visible = c7.slider("Visible legs", 2, N_LEGS, 6, key="sp_nlegs")
        st.caption(f"Bond PV (1y) = K × e^(−r_b) ≈ K × {np.exp(-bond_rate):.4f}")

    _init_legs()
    _apply_preset(preset)
    if preset != NO_PRESET:
        callout(f"{preset} loaded into the legs below — adjust strikes and premiums as needed.",
                tone="neutral")

    # ── Legs ──
    section("Legs", f"{n_visible} of {N_LEGS} shown · legs with zero quantity are ignored")
    legs = st.session_state.legs
    with st.container(border=True):
        _leg_editor(legs, n_visible)

    # ── Compute ──
    S_arr = np.linspace(max(S_min, 0.01), S_max, n_points)
    total_payoff = np.zeros_like(S_arr)
    total_premium = 0.0
    leg_payoffs = {}
    for i, leg in enumerate(legs):
        if leg["qty"] > 0 and leg["instrument"] != "None":
            lp = compute_leg_payoff(S_arr, leg["instrument"], leg["direction"],
                                    leg["K"], leg["barrier"], leg["qty"])
            leg_payoffs[f"Leg {i + 1}: {leg['instrument']}"] = lp
            total_payoff += lp
            total_premium += (-1 if leg["direction"] == "Long" else 1) * leg["premium"] * leg["qty"]
    net_pnl = total_payoff + total_premium

    be_idx = np.where(np.diff(np.sign(net_pnl)))[0]
    breakevens = S_arr[be_idx] if len(be_idx) else []
    max_profit, max_loss = float(np.max(net_pnl)), float(np.min(net_pnl))

    # ── Results ──
    section("Payoff at maturity")
    stat_grid([
        Stat("Max profit", num(max_profit), tone="pos" if max_profit > 0 else "default"),
        Stat("Max loss", num(max_loss), tone="neg" if max_loss < 0 else "default"),
        Stat("Net premium", num(total_premium, signed=True),
             hint="received" if total_premium > 0 else "paid" if total_premium < 0 else None),
        Stat("Breakeven(s)", ", ".join(f"{b:.1f}" for b in breakevens[:3]) or "—"),
    ])

    fig = go.Figure()
    for idx, (name, payoff) in enumerate(leg_payoffs.items()):
        fig.add_trace(go.Scatter(
            x=S_arr, y=payoff, name=name, opacity=0.7,
            line=dict(color=SERIES[idx] if idx < len(SERIES) else C.subtle, width=1, dash="dot"),
        ))
    fig.add_trace(go.Scatter(x=S_arr, y=np.maximum(net_pnl, 0), line=dict(width=0),
                             fill="tozeroy", fillcolor=rgba(C.pos, 0.12),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=S_arr, y=np.minimum(net_pnl, 0), line=dict(width=0),
                             fill="tozeroy", fillcolor=rgba(C.neg, 0.12),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=S_arr, y=total_payoff, name="Total payoff",
                             line=dict(color=C.accent, width=2.5)))
    fig.add_trace(go.Scatter(x=S_arr, y=net_pnl, name="Net P&L (after premium)",
                             line=dict(color=C.text, width=2)))
    fig.add_hline(y=0, line_color=C.axis, line_width=1)
    fig.add_vline(x=S0, line_dash="dash", line_color=C.muted, line_width=1,
                  annotation_text=f"S₀ = {S0:g}", annotation_font_color=C.muted)
    fig.update_layout(xaxis_title="Spot at maturity S_T", yaxis_title="Payoff / P&L")
    chart(fig, height=480)

    with st.expander("Strategy presets reference"):
        ref = []
        for name, preset_legs in STRATEGY_PRESETS.items():
            if name == NO_PRESET:
                continue
            desc = " + ".join(f"{v[1]} {v[0]} K={v[2]}" + (f" ×{v[6]}" if v[6] > 1 else "")
                              for v in preset_legs.values())
            ref.append(dict(Strategy=name, Legs=desc))
        st.dataframe(pd.DataFrame(ref), width="stretch", hide_index=True)
