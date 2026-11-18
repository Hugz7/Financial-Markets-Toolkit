"""views/monte_carlo.py — GBM Monte Carlo engine: pricing, paths, distribution, convergence."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.black_scholes import call_price, put_price
from models.monte_carlo import (
    convergence_analysis, histogram_data, price_options_mc, sample_paths,
    simulate_gbm, terminal_distribution_stats,
)
from ui.components import panel, Stat, chart, empty_state, page_header, require, section, stat_grid
from ui.formatting import num, pct
from ui.theme import C, SERIES, rgba

PATH = SERIES[0]
BAND = C.text      # neutral envelope over the blue paths
MEAN = SERIES[1]
REF = SERIES[2]


def render():
    page_header(
        "Monte Carlo Simulation",
        "Geometric Brownian motion paths priced across European, Asian, barrier and lookback payoffs, "
        "benchmarked against closed-form Black-Scholes.",
        eyebrow="Simulation",
    )

    # ── Inputs ──
    with panel():
        st.markdown("**Market**")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        S0 = c1.number_input("Spot S₀", value=100.0, step=1.0, key="mc_S")
        K = c2.number_input("Strike K", value=100.0, step=1.0, key="mc_K")
        T = c3.number_input("Maturity T (yr)", value=1.0, step=0.25, key="mc_T")
        r = c4.number_input("Risk-free r", value=0.05, step=0.005, format="%.3f", key="mc_r")
        sigma = c5.number_input("Volatility σ", value=0.20, step=0.01, format="%.2f", key="mc_sig")
        q = c6.number_input("Dividend yield q", value=0.02, step=0.005, format="%.3f", key="mc_q")

        st.markdown("**Engine**")
        c1, c2, c3, c4, c5 = st.columns([1.6, 1.3, 1, 1, 0.8])
        n_sims = c1.select_slider("Simulations",
                                  options=[1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000],
                                  value=50000, key="mc_nsims", format_func=lambda n: f"{n:,}")
        n_steps = c2.select_slider("Time steps", options=[52, 126, 252, 504], value=252, key="mc_nsteps")
        H_up = c3.number_input("Upper barrier H", value=120.0, step=5.0, key="mc_H")
        H_down = c4.number_input("Lower barrier L", value=80.0, step=5.0, key="mc_L")
        seed = c5.number_input("Seed", value=42, step=1, key="mc_seed")

    require(S0 > 0, "Spot S₀ must be positive.")
    require(K > 0, "Strike K must be positive.")
    require(T > 0, "Maturity T must be greater than 0.")
    require(sigma > 0, "Volatility σ must be positive.")
    require(H_up > H_down, f"Upper barrier H ({H_up}) must be greater than lower barrier L ({H_down}).")

    if st.button("Run simulation", type="primary", key="mc_run", icon=":material/play_arrow:"):
        with st.spinner(f"Simulating {n_sims:,} paths × {n_steps} steps…"):
            st.session_state.mc_paths = simulate_gbm(S0, r, q, sigma, T, n_sims, n_steps, seed)
            st.session_state.mc_params = dict(S0=S0, K=K, T=T, r=r, sigma=sigma,
                                              q=q, H_up=H_up, H_down=H_down)
        st.toast(f"Simulated {n_sims:,} paths", icon=":material/check_circle:")

    if "mc_paths" not in st.session_state:
        empty_state("No simulation yet", "Set the parameters above and press Run simulation.")
        return

    S_paths = st.session_state.mc_paths
    p = st.session_state.mc_params
    S_T = S_paths[:, -1]
    if any(p[k] != v for k, v in dict(S0=S0, K=K, T=T, r=r, sigma=sigma, q=q,
                                         H_up=H_up, H_down=H_down).items()):
        st.caption(":material/info: Showing the last run — parameters changed since; press Run simulation to update.")

    # ── Pricing ──
    mc = price_options_mc(S_paths, p["K"], p["r"], p["T"], p["H_up"], p["H_down"])
    bsm_c = call_price(p["S0"], p["K"], p["T"], p["r"], p["sigma"], p["q"])
    bsm_p = put_price(p["S0"], p["K"], p["T"], p["r"], p["sigma"], p["q"])
    for res, exact in ((mc[0], bsm_c), (mc[1], bsm_p)):
        res["exact"] = exact
        res["error_pct"] = abs(res["price"] - exact) / exact * 100

    section("Pricing", f"{len(S_T):,} paths · 95% confidence intervals")
    call_ok = mc[0]["ci_low"] <= bsm_c <= mc[0]["ci_high"]
    stat_grid([
        Stat("European call (MC)", num(mc[0]["price"], 4), hint=f"BSM {bsm_c:.4f}"),
        Stat("European put (MC)", num(mc[1]["price"], 4), hint=f"BSM {bsm_p:.4f}"),
        Stat("Call pricing error", f"{mc[0]['error_pct']:.2f}%", tone="pos" if call_ok else "warn",
             hint="BSM inside 95% CI" if call_ok else "BSM outside 95% CI"),
        Stat("Std error (call)", num(mc[0]["se"], 5), hint="σ(payoff)·e^(−rT)/√n"),
    ], columns=4)

    table = pd.DataFrame([{
        "Option": res["name"],
        "MC price": res["price"],
        "Std error": res["se"],
        "95% CI low": res["ci_low"],
        "95% CI high": res["ci_high"],
        "BSM exact": f"{res['exact']:.4f}" if res["exact"] is not None else "—",
        "Error %": f"{res['error_pct']:.2f}%" if res["error_pct"] is not None else "—",
        "Status": ("" if not res["exact"] else
                   "Within CI" if res["ci_low"] <= res["exact"] <= res["ci_high"] else "Outside CI"),
    } for res in mc])
    st.dataframe(
        table.style.format({"MC price": "{:.4f}", "Std error": "{:.6f}", "95% CI low": "{:.4f}",
                            "95% CI high": "{:.4f}"}),
        width="stretch", hide_index=True,
    )

    tab_paths, tab_dist, tab_conv = st.tabs(["Sample paths", "Terminal distribution", "Convergence"])

    # ── Paths: one hue at low opacity + mean and percentile bands ──
    with tab_paths:
        n_show = st.slider("Paths to display", 10, 1000, 200, key="mc_nshow")
        sp = sample_paths(S_paths, n_sample=n_show)
        allp = sample_paths(S_paths, n_sample=len(S_paths))
        months = np.arange(sp.shape[1])
        p5, p25, p50, p75, p95 = np.percentile(allp, [5, 25, 50, 75, 95], axis=0)
        mean = allp.mean(axis=0)

        fig = go.Figure()
        opacity = 0.3 if n_show <= 50 else max(0.05, 0.22 - n_show * 0.0002)
        for i in range(sp.shape[0]):
            fig.add_trace(go.Scatter(x=months, y=sp[i], mode="lines", showlegend=False,
                                     line=dict(color=PATH, width=1), opacity=opacity, hoverinfo="skip"))
        # Percentile envelope drawn on top of the paths so it stays legible
        fig.add_trace(go.Scatter(x=months, y=p75, mode="lines", line=dict(width=0), showlegend=False,
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=months, y=p25, mode="lines", line=dict(width=0), fill="tonexty",
                                 fillcolor=rgba(BAND, 0.18), name="25–75th percentile",
                                 hoverinfo="skip"))
        for y, name, show in ((p95, "5th / 95th percentile", True), (p5, "5th percentile", False)):
            fig.add_trace(go.Scatter(x=months, y=y, mode="lines", name=name, showlegend=show,
                                     line=dict(color=C.text_2, width=1.2, dash="dash"),
                                     hovertemplate=name.split(" /")[0] + " %{y:.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=months, y=mean, mode="lines", name="Mean",
                                 line=dict(color=MEAN, width=2.5),
                                 hovertemplate="Month %{x}<br>Mean %{y:.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=months, y=p50, mode="lines", name="Median",
                                 line=dict(color=C.text, width=1.5, dash="dot"),
                                 hovertemplate="Median %{y:.2f}<extra></extra>"))
        fig.add_hline(y=p["S0"], line_dash="dash", line_color=C.muted, line_width=1)
        if p["H_up"] > p["S0"]:
            fig.add_hline(y=p["H_up"], line_dash="dot", line_color=C.neg, line_width=1,
                          annotation_text="H", annotation_font_color=C.neg)
        if p["H_down"] < p["S0"]:
            fig.add_hline(y=p["H_down"], line_dash="dot", line_color=C.neg, line_width=1,
                          annotation_text="L", annotation_font_color=C.neg)
        fig.update_layout(xaxis_title="Month", yaxis_title="Price", hovermode="x unified")
        chart(fig, height=440, title="Simulated GBM paths (monthly sampling)")

    # ── Terminal distribution ──
    with tab_dist:
        col_h, col_s = st.columns([1.6, 1], gap="large")
        with col_h:
            hist = histogram_data(S_T, n_bins=30)
            fig_h = go.Figure(go.Bar(
                x=[(h["bin_low"] + h["bin_high"]) / 2 for h in hist],
                y=[h["freq"] for h in hist],
                width=[(h["bin_high"] - h["bin_low"]) * 0.92 for h in hist],
                marker_color=PATH, name="Frequency",
                hovertemplate="S_T ≈ %{x:.2f}<br>%{y:.2f}% of paths<extra></extra>",
            ))
            fig_h.add_vline(x=p["K"], line_dash="dash", line_color=MEAN,
                            annotation_text="K", annotation_font_color=MEAN)
            fig_h.update_layout(xaxis_title="S_T", yaxis_title="Frequency (%)", showlegend=False,
                                hovermode="closest")
            chart(fig_h, height=380, title="Distribution of S_T")
        with col_s:
            s = terminal_distribution_stats(S_T, p["K"])
            stat_grid([
                Stat("Mean", num(s["mean"]), small=True),
                Stat("Median", num(s["median"]), small=True),
                Stat("Std dev", num(s["std"]), small=True),
                Stat("Skewness", num(s["skewness"], 3), small=True),
                Stat("Kurtosis", num(s["kurtosis"], 3), small=True, hint="Pearson (normal = 3)"),
                Stat("5th / 95th pct", f"{s['p5']:.1f} / {s['p95']:.1f}", small=True),
                Stat("P(S_T > K)", pct(s["prob_above_K"], 1), small=True),
                Stat("Expected shortfall 5%", num(s["expected_shortfall_5"]), small=True,
                     hint="mean of worst 5% S_T"),
            ], columns=2)

    # ── Convergence ──
    with tab_conv:
        conv = convergence_analysis(S_paths, p["K"], p["r"], p["T"])
        n_paths = [c["n_paths"] for c in conv]
        prices = [c["mc_price"] for c in conv]
        ses = [c["std_error"] for c in conv]
        col_c, col_k = st.columns([1.6, 1], gap="large")
        with col_c:
            fig_c = go.Figure()
            fig_c.add_trace(go.Scatter(
                x=n_paths, y=prices, name="MC price (±1.96 SE)", mode="lines+markers",
                line=dict(color=PATH),
                error_y=dict(type="data", array=[1.96 * x for x in ses], visible=True,
                             color=rgba(PATH, 0.6), thickness=1.2),
                hovertemplate="%{x:,} paths<br>%{y:.4f}<extra></extra>",
            ))
            fig_c.add_hline(y=bsm_c, line_dash="dash", line_color=REF,
                            annotation_text=f"BSM {bsm_c:.4f}", annotation_font_color=REF)
            fig_c.update_layout(xaxis_title="Number of paths", yaxis_title="Call price",
                                xaxis_type="log", hovermode="closest")
            chart(fig_c, height=380, title="European call convergence")
        with col_k:
            abs_err = abs(prices[-1] - bsm_c)
            stat_grid([
                Stat("BSM exact", num(bsm_c, 4), small=True),
                Stat("MC price", num(prices[-1], 4), small=True),
                Stat("Std error", num(ses[-1], 5), small=True),
                Stat("Abs error", num(abs_err, 5), small=True),
                Stat("Rel error", f"{abs_err / bsm_c * 100:.3f}%", small=True),
                Stat("Paths used", f"{n_paths[-1]:,}", small=True),
            ], columns=2)
