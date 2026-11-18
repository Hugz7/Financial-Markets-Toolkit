"""views/vol_smile.py — Implied volatility smile, term structure and surface from live chains."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.interpolate import griddata

from models.volatility import atm_iv, otm_composite, skew_metrics
from services.options import clear_cache, fetch_expiries, fetch_smile
from ui.components import (Stat, callout, chart, empty_state, page_header, require,
                           section, stat_grid)
from ui.formatting import num, pct
from ui.theme import C, SEQUENTIAL, SERIES

MAX_CURVES = len(SERIES)  # one categorical colour per expiry, never cycled


def _x(df: pd.DataFrame, use_moneyness: bool) -> pd.Series:
    return df["moneyness"] if use_moneyness else df["strike"]


def _iv_axis(fig: go.Figure, x_title: str) -> None:
    fig.update_xaxes(title_text=x_title, showgrid=False)
    fig.update_yaxes(title_text="Implied volatility", ticksuffix="%")


def _controls() -> tuple[str, float, float, bool]:
    with st.container(border=True):
        c_t, c_r, c_q, c_b = st.columns([2, 1, 1, 1], vertical_alignment="bottom")
        ticker = c_t.text_input("Ticker", value="SPY", key="vs_ticker").strip().upper()
        r = c_r.number_input("Risk-free rate r", value=0.045, step=0.005, format="%.3f", key="vs_r")
        q = c_q.number_input("Dividend yield q", value=0.015, step=0.005, format="%.3f", key="vs_q")
        load = c_b.button("Load options", type="primary", key="vs_load",
                          icon=":material/download:", width="stretch")
    return ticker, r, q, load


def render():
    page_header(
        "Volatility Smile",
        "Black-Scholes implied volatility backed out of live option-chain mid prices — "
        "single-expiry smile, term structure and the full surface.",
        eyebrow="Options",
    )
    ticker, r, q, load = _controls()

    # ── Load expiries ──
    if load:
        require(bool(ticker), "Enter a ticker symbol.")
        clear_cache()
        try:
            with st.spinner(f"Fetching listed expiries for {ticker}…"):
                spot, expiries = fetch_expiries(ticker)
        except Exception as exc:
            st.error(f"Could not load options for **{ticker}**. Yahoo Finance returned no data — "
                     "check the symbol and your network connection, then try again.",
                     icon=":material/cloud_off:")
            st.caption(f"Details: {type(exc).__name__}: {exc}")
            return
        st.session_state["vs_spot"] = spot
        st.session_state["vs_expiries"] = expiries
        st.session_state["vs_ticker_loaded"] = ticker

    if "vs_spot" not in st.session_state:
        empty_state("No option chain loaded",
                    "Enter a ticker with listed options (e.g. SPY, QQQ, AAPL) and press Load options.")
        return

    S = st.session_state["vs_spot"]
    expiries = st.session_state["vs_expiries"]
    sym = st.session_state["vs_ticker_loaded"]

    # ── Expiry & axis selection ──
    c_sel, c_x = st.columns([2, 1], vertical_alignment="bottom")
    exp_single = c_sel.selectbox("Expiry", expiries, key="vs_exp_single")
    x_axis = c_x.segmented_control("X-axis", ["Strike K", "Moneyness K/S"],
                                   default="Strike K", key="vs_xaxis")
    use_moneyness = x_axis == "Moneyness K/S"
    x_label = "Moneyness K / S" if use_moneyness else "Strike K"
    x_atm = 1.0 if use_moneyness else S

    try:
        with st.spinner(f"Loading {sym} chain for {exp_single}…"):
            T_sel, calls, puts = fetch_smile(sym, exp_single, S, r, q)
    except Exception as exc:
        st.error(f"Failed to load the {exp_single} chain — {exc}", icon=":material/cloud_off:")
        return

    atm = atm_iv(calls, puts, S)
    stat_grid([
        Stat(sym, num(S), hint="Spot"),
        Stat("ATM implied vol", pct(atm, 1)),
        Stat("Time to expiry", f"{T_sel:.3f} y", hint=exp_single),
        Stat("Strikes loaded", f"{len(calls)} C / {len(puts)} P", hint=f"{len(expiries)} expiries listed"),
    ])

    tab_smile, tab_multi, tab_surface = st.tabs(["Smile", "Term structure", "Surface"])

    # ── Smile ──
    with tab_smile:
        if calls.empty and puts.empty:
            empty_state("No liquid strikes", "This expiry has no strikes passing the liquidity and IV filters.")
        else:
            fig = go.Figure()
            for df, name, color in ((calls, "Calls", SERIES[0]), (puts, "Puts", SERIES[1])):
                if len(df):
                    fig.add_trace(go.Scatter(
                        x=_x(df, use_moneyness), y=df["iv_bsm"] * 100, mode="lines+markers",
                        name=name, line=dict(color=color), marker=dict(color=color, size=6),
                        hovertemplate=f"{name}: %{{y:.2f}}%<extra></extra>",
                    ))
            if np.isfinite(atm):
                fig.add_vline(x=x_atm, line_dash="dot", line_color=C.muted, line_width=1,
                              annotation_text="ATM", annotation_font_color=C.muted)
                fig.add_hline(y=atm * 100, line_dash="dot", line_color=C.subtle, line_width=1,
                              annotation_text=f"ATM IV {atm * 100:.1f}%",
                              annotation_font_color=C.muted)
            _iv_axis(fig, x_label)
            chart(fig, height=440, title=f"{sym} smile · {exp_single} (T = {T_sel:.3f}y)")

            sk = skew_metrics(calls, puts, S)
            stat_grid([
                Stat("ATM IV", pct(sk["atm"])),
                Stat("90% put IV", pct(sk["put90"])),
                Stat("110% call IV", pct(sk["call110"])),
                Stat("Skew (90P − 110C)", pct(sk["skew"], signed=True)),
                Stat("Curvature (wings − ATM)", pct(sk["curvature"], signed=True)),
            ], columns=5)

            with st.expander("Raw chain data"):
                cols = ["strike", "moneyness", "bid", "ask", "mid", "iv_bsm", "volume", "openInterest"]
                tbl = pd.concat([
                    calls[[c for c in cols if c in calls]].assign(type="call"),
                    puts[[c for c in cols if c in puts]].assign(type="put"),
                ]).sort_values("strike")
                tbl["iv_bsm"] = tbl["iv_bsm"] * 100
                st.dataframe(
                    tbl[["type"] + [c for c in cols if c in tbl]], width="stretch", hide_index=True,
                    column_config={
                        "iv_bsm": st.column_config.NumberColumn("IV (%)", format="%.2f"),
                        "moneyness": st.column_config.NumberColumn("K/S", format="%.4f"),
                        "openInterest": st.column_config.NumberColumn("Open int."),
                    },
                )

    # ── Term structure ──
    with tab_multi:
        exp_multi = st.multiselect(
            f"Expiries (2–{MAX_CURVES})", options=expiries[:20],
            default=expiries[:min(4, len(expiries))], max_selections=MAX_CURVES,
            key="vs_exp_multi",
        )
        if len(exp_multi) < 2:
            empty_state("Pick at least two expiries", "Each expiry is drawn as an OTM composite smile.")
        else:
            fig_multi, atm_term, failed = go.Figure(), [], []
            with st.spinner("Loading chains…"):
                for color, expiry in zip(SERIES, exp_multi):
                    try:
                        T_i, c_i, p_i = fetch_smile(sym, expiry, S, r, q)
                    except Exception:
                        failed.append(expiry)
                        continue
                    comp = otm_composite(c_i, p_i)
                    if comp.empty:
                        continue
                    fig_multi.add_trace(go.Scatter(
                        x=_x(comp, use_moneyness), y=comp["iv_bsm"] * 100, mode="lines+markers",
                        name=f"{expiry} ({T_i:.2f}y)", line=dict(color=color),
                        marker=dict(color=color, size=5),
                        hovertemplate=f"{expiry}: %{{y:.2f}}%<extra></extra>",
                    ))
                    iv_atm = atm_iv(c_i, p_i, S)
                    if np.isfinite(iv_atm):
                        atm_term.append((T_i, iv_atm * 100, expiry))
            if failed:
                callout(f"Could not load: {', '.join(failed)}.", tone="warn")

            fig_multi.add_vline(x=x_atm, line_dash="dot", line_color=C.muted, line_width=1,
                                annotation_text="ATM", annotation_font_color=C.muted)
            _iv_axis(fig_multi, x_label)
            chart(fig_multi, height=460, title=f"{sym} smile by expiry · OTM composite")

            if len(atm_term) >= 2:
                atm_term.sort()
                fig_ts = go.Figure(go.Scatter(
                    x=[t for t, _, _ in atm_term], y=[v for _, v, _ in atm_term],
                    text=[e for _, _, e in atm_term], mode="lines+markers", name="ATM IV",
                    line=dict(color=SERIES[0]),
                    marker=dict(color=SERIES[0], size=9, line=dict(color=C.bg, width=2)),
                    hovertemplate="%{text} · T %{x:.3f}y<br>ATM IV %{y:.2f}%<extra></extra>",
                ))
                fig_ts.update_xaxes(title_text="Maturity T (years)", showgrid=False)
                fig_ts.update_yaxes(title_text="ATM implied vol", ticksuffix="%")
                fig_ts.update_layout(hovermode="closest", showlegend=False)
                chart(fig_ts, height=300, title=f"{sym} ATM volatility term structure")

    # ── Surface ──
    with tab_surface:
        exp_surf = st.multiselect(
            "Expiries for the surface (≥ 3)", options=expiries[:20],
            default=expiries[:min(6, len(expiries))], key="vs_exp_surf",
        )
        if len(exp_surf) < 3:
            empty_state("Pick at least three expiries", "The surface is interpolated across maturities.")
            return

        pts = []
        with st.spinner("Building surface…"):
            for expiry in exp_surf:
                try:
                    T_i, c_i, p_i = fetch_smile(sym, expiry, S, r, q)
                except Exception:
                    continue
                comp = otm_composite(c_i, p_i)
                pts.extend((T_i, m, iv * 100) for m, iv in zip(comp["moneyness"], comp["iv_bsm"]))

        if len(pts) < 10:
            empty_state("Not enough data for a surface",
                        "Fewer than 10 liquid strikes across the chosen expiries. Add expiries or try a more liquid ticker.")
            return

        pts_arr = np.array(pts)
        T_pts, M_pts, IV_pts = pts_arr[:, 0], pts_arr[:, 1], pts_arr[:, 2]
        T_grid = np.linspace(T_pts.min(), T_pts.max(), 30)
        M_grid = np.linspace(M_pts.min(), M_pts.max(), 50)
        TT, MM = np.meshgrid(T_grid, M_grid)
        IV_grid = griddata((T_pts, M_pts), IV_pts, (TT, MM), method="linear")

        # ATM ridge: nearest-to-ATM point within ±0.05y of each grid maturity
        atm_ridge = []
        for T_i in T_grid:
            nearby = pts_arr[np.abs(pts_arr[:, 0] - T_i) < 0.05]
            atm_ridge.append(nearby[np.argmin(np.abs(nearby[:, 1] - 1.0)), 2] if len(nearby) else np.nan)

        fig_surf = go.Figure(go.Surface(
            x=T_grid, y=M_grid, z=IV_grid, colorscale=SEQUENTIAL, opacity=0.92,
            colorbar=dict(title=dict(text="IV %", font=dict(color=C.muted, size=11)),
                          tickfont=dict(color=C.muted, size=10), thickness=12, len=0.7),
            hovertemplate="T %{x:.3f}y<br>K/S %{y:.3f}<br>IV %{z:.1f}%<extra></extra>",
        ))
        fig_surf.add_trace(go.Scatter3d(
            x=T_grid, y=np.ones(len(T_grid)), z=np.array(atm_ridge), mode="lines",
            line=dict(color=SERIES[1], width=5), name="ATM ridge",
            hovertemplate="ATM · T %{x:.3f}y<br>IV %{z:.1f}%<extra></extra>",
        ))
        fig_surf.update_layout(
            scene=dict(xaxis_title="Maturity (y)", yaxis_title="Moneyness K/S",
                       zaxis=dict(title="IV (%)", ticksuffix="%"),
                       camera=dict(eye=dict(x=1.8, y=-1.8, z=1.2))),
            margin=dict(l=0, r=0, t=40, b=0), hovermode="closest",
        )
        chart(fig_surf, height=580, title=f"{sym} implied volatility surface")
        st.caption("Linear interpolation of OTM mid-price IVs · orange line = ATM ridge · "
                   "illiquid strikes leave gaps.")
