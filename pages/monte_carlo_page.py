"""
monte_carlo_page.py — Monte Carlo Simulation Engine.
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
from config import (PLOTLY_LAYOUT, ACCENT_GOLD, ACCENT_BLUE, ACCENT_GREEN,
                    ACCENT_RED, TEXT_GREY, ACCENT_CYAN)
from models.monte_carlo import (
    simulate_gbm, price_options_mc, terminal_distribution_stats,
    convergence_analysis, sample_paths, histogram_data,
)
from models.black_scholes import call_price


def render():
    st.markdown("## Monte Carlo Simulation Engine")
    st.caption("GBM Price Paths · European/Asian/Barrier/Lookback Pricing · "
               "Convergence Analysis · Terminal Distribution")

    # ── Parameters ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Simulation Parameters")
        S0 = st.number_input("Spot S₀", value=100.0, step=1.0, key="mc_S")
        K = st.number_input("Strike K", value=100.0, step=1.0, key="mc_K")
        T = st.number_input("Maturity T (yr)", value=1.0, step=0.25, key="mc_T")
        r = st.number_input("Risk-Free Rate r", value=0.05, step=0.005,
                            format="%.3f", key="mc_r")
        sigma = st.number_input("Volatility σ", value=0.20, step=0.01,
                                format="%.2f", key="mc_sig")
        q = st.number_input("Dividend Yield q", value=0.02, step=0.005,
                            format="%.3f", key="mc_q")

    with col2:
        st.markdown("#### Engine Settings")
        n_sims = st.select_slider("Nb Simulations",
                                  options=[1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000],
                                  value=50000, key="mc_nsims")
        n_steps = st.select_slider("Nb Time Steps",
                                   options=[52, 126, 252, 504],
                                   value=252, key="mc_nsteps")
        H_up = st.number_input("Upper Barrier H", value=120.0, step=5.0, key="mc_H")
        H_down = st.number_input("Lower Barrier L", value=80.0, step=5.0, key="mc_L")
        seed = st.number_input("Random Seed", value=42, step=1, key="mc_seed")

    st.markdown("---")

    # ── Run Simulation ──
    if st.button("Run Monte Carlo Simulation", type="primary", key="mc_run"):
        with st.spinner(f"Simulating {n_sims:,} paths × {n_steps} steps..."):
            S_paths = simulate_gbm(S0, r, q, sigma, T, n_sims, n_steps, seed)
            st.session_state.mc_paths = S_paths
            st.session_state.mc_params = dict(S0=S0, K=K, T=T, r=r, sigma=sigma,
                                               q=q, H_up=H_up, H_down=H_down)
        st.success(f"Simulation complete: {n_sims:,} paths generated.")

    if "mc_paths" not in st.session_state:
        st.info("Click **Run Monte Carlo Simulation** to generate paths.")
        return

    S_paths = st.session_state.mc_paths
    params = st.session_state.mc_params
    S_T = S_paths[:, -1]

    # ── MC Pricing Results ──
    st.markdown("#### MC Pricing Results")
    mc_results = price_options_mc(S_paths, params["K"], params["r"], params["T"],
                                  params["H_up"], params["H_down"])

    # Add BSM exact for Euro call/put
    bsm_c = call_price(params["S0"], params["K"], params["T"], params["r"],
                       params["sigma"], params["q"])
    from models.black_scholes import put_price as bsm_put
    bsm_p = bsm_put(params["S0"], params["K"], params["T"], params["r"],
                     params["sigma"], params["q"])
    mc_results[0]["exact"] = bsm_c
    mc_results[0]["error_pct"] = abs(mc_results[0]["price"] - bsm_c) / bsm_c * 100
    mc_results[1]["exact"] = bsm_p
    mc_results[1]["error_pct"] = abs(mc_results[1]["price"] - bsm_p) / bsm_p * 100

    rows = []
    for res in mc_results:
        row = {
            "Option": res["name"],
            "MC Price": f"{res['price']:.4f}",
            "Std Error": f"{res['se']:.6f}",
            "95% CI Low": f"{res['ci_low']:.4f}",
            "95% CI High": f"{res['ci_high']:.4f}",
            "BSM Exact": f"{res['exact']:.4f}" if res["exact"] else "N/A",
            "Error %": f"{res['error_pct']:.2f}%" if res["error_pct"] else "",
            "Status": ("OK" if res["error_pct"] and res["error_pct"] < 5
                       else (">" if res["error_pct"] else "")),
        }
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Sample Paths Chart ──
    st.markdown("#### Sample GBM Paths")
    n_show = st.slider("Paths to display", 10, 1000, 200, key="mc_nshow")
    sp = sample_paths(S_paths, n_sample=n_show)
    n_months = sp.shape[1]
    months = list(range(n_months))

    # Generate multicolor spectrum — vivid HSL wheel with saturation variance
    def mc_colors(n):
        colors = []
        sat_cycle = [92, 80, 88, 76, 95]   # vary saturation for vibrancy
        lit_cycle = [58, 65, 52, 70, 55]   # vary lightness for depth
        for i in range(n):
            hue = int(360 * i / max(n, 1))
            sat = sat_cycle[i % len(sat_cycle)]
            lit = lit_cycle[i % len(lit_cycle)]
            colors.append(f"hsl({hue},{sat}%,{lit}%)")
        return colors

    path_colors = mc_colors(sp.shape[0])
    path_opacity = 0.80 if n_show <= 50 else max(0.08, 0.55 - n_show * 0.0004)
    path_width = 1.1 if n_show <= 150 else 0.7

    fig_paths = go.Figure()
    for i in range(sp.shape[0]):
        fig_paths.add_trace(go.Scatter(
            x=months, y=sp[i],
            mode="lines",
            name=f"Path {i+1}" if n_show <= 20 else None,
            line=dict(color=path_colors[i], width=path_width),
            opacity=path_opacity,
            showlegend=(n_show <= 20),
        ))

    fig_paths.add_hline(y=params["S0"], line_dash="dash", line_color=TEXT_GREY)
    if params["H_up"] > params["S0"]:
        fig_paths.add_hline(y=params["H_up"], line_dash="dot",
                            line_color=ACCENT_RED, annotation_text="H_up")
    if params["H_down"] < params["S0"]:
        fig_paths.add_hline(y=params["H_down"], line_dash="dot",
                            line_color=ACCENT_RED, annotation_text="H_down")

    fig_paths.update_layout(
        **PLOTLY_LAYOUT,
        title="Sample GBM Paths (monthly sampling)",
        xaxis_title="Month", yaxis_title="Price",
        height=400, showlegend=False,
    )
    st.plotly_chart(fig_paths, use_container_width=True)

    # ── Terminal Distribution + Convergence ──
    col_dist, col_conv = st.columns(2)

    with col_dist:
        st.markdown("#### Terminal Distribution S_T")
        hist = histogram_data(S_T, n_bins=30)
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Bar(
            x=[(h["bin_low"] + h["bin_high"]) / 2 for h in hist],
            y=[h["freq"] for h in hist],
            width=[(h["bin_high"] - h["bin_low"]) * 0.9 for h in hist],
            marker_color=ACCENT_BLUE, opacity=0.8,
        ))
        fig_hist.add_vline(x=params["K"], line_dash="dash",
                           line_color=ACCENT_CYAN, annotation_text="K")
        fig_hist.update_layout(
            **PLOTLY_LAYOUT, title="S_T Distribution",
            xaxis_title="S_T", yaxis_title="Frequency %", height=350,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

        # Stats — glass cards
        stats = terminal_distribution_stats(S_T, params["K"])
        _color_map = {
            "Mean": "#00E5FF", "Median": "#38BDF8",
            "Std Dev": "#A78BFA", "Skewness": "#F0B429",
            "Kurtosis": "#FB923C", "Min": "#FF4D6D", "Max": "#10D48A",
        }
        _cards = []
        for k, v in stats.items():
            _fmt = f"{v:.4f}" if isinstance(v, float) else str(v)
            _col = _color_map.get(k, "#9BAEC8")
            _cards.append(
                f"<div style='background:rgba(8,18,32,0.72);backdrop-filter:blur(14px);"
                f"-webkit-backdrop-filter:blur(14px);border:1px solid rgba(0,229,255,0.13);"
                f"border-radius:8px;padding:9px 13px;margin:4px 0;"
                f"box-shadow:0 2px 14px rgba(0,0,0,0.35)'>"
                f"<div style='color:#5A6A82;font-size:0.62rem;text-transform:uppercase;"
                f"letter-spacing:0.07em;font-weight:600;margin-bottom:2px'>{k}</div>"
                f"<div style='color:{_col};font-size:1.05rem;font-weight:700;"
                f"font-variant-numeric:tabular-nums'>{_fmt}</div>"
                f"</div>"
            )
        st.markdown(
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:4px'>"
            + "".join(_cards)
            + "</div>",
            unsafe_allow_html=True,
        )

    with col_conv:
        st.markdown("#### Convergence (European Call)")
        conv = convergence_analysis(S_paths, params["K"], params["r"], params["T"])

        fig_conv = go.Figure()
        n_paths = [c["n_paths"] for c in conv]
        mc_prices = [c["mc_price"] for c in conv]
        se_vals = [c["std_error"] for c in conv]

        fig_conv.add_trace(go.Scatter(
            x=n_paths, y=mc_prices, name="MC Price",
            line=dict(color=ACCENT_GREEN, width=2),
            error_y=dict(type="data", array=[1.96 * s for s in se_vals],
                         visible=True, color=ACCENT_GREEN),
        ))
        fig_conv.add_hline(y=bsm_c, line_dash="dash", line_color=ACCENT_CYAN,
                           annotation_text=f"BSM = {bsm_c:.4f}")
        fig_conv.update_layout(
            **PLOTLY_LAYOUT, title="MC Price Convergence",
            xaxis_title="Number of Paths", yaxis_title="MC Price",
            xaxis_type="log", height=350,
        )
        st.plotly_chart(fig_conv, use_container_width=True)

        # Convergence summary glass cards
        last_mc = mc_prices[-1]
        last_se = se_vals[-1]
        abs_err = abs(last_mc - bsm_c)
        rel_err = abs_err / bsm_c * 100
        _conv_items = [
            ("BSM Exact", f"{bsm_c:.4f}", "#00E5FF"),
            ("MC Price", f"{last_mc:.4f}", "#38BDF8"),
            ("Std Error", f"{last_se:.5f}", "#A78BFA"),
            ("Abs Error", f"{abs_err:.5f}", "#F0B429"),
            ("Rel Error", f"{rel_err:.3f}%", "#FB923C"),
            ("N Paths", f"{n_paths[-1]:,}", "#10D48A"),
        ]
        _conv_cards = "".join(
            f"<div style='background:rgba(8,18,32,0.72);backdrop-filter:blur(14px);"
            f"-webkit-backdrop-filter:blur(14px);border:1px solid rgba(0,229,255,0.13);"
            f"border-radius:8px;padding:9px 13px;margin:4px 0;"
            f"box-shadow:0 2px 14px rgba(0,0,0,0.35)'>"
            f"<div style='color:#5A6A82;font-size:0.62rem;text-transform:uppercase;"
            f"letter-spacing:0.07em;font-weight:600;margin-bottom:2px'>{lbl}</div>"
            f"<div style='color:{col};font-size:1.05rem;font-weight:700;"
            f"font-variant-numeric:tabular-nums'>{val}</div></div>"
            for lbl, val, col in _conv_items
        )
        st.markdown(
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:4px'>"
            + _conv_cards + "</div>",
            unsafe_allow_html=True,
        )
