"""
exotic_pricer.py — Exotic Options Pricer with 15 closed-form options + Greeks.
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
from config import (PLOTLY_LAYOUT, ACCENT_GOLD, ACCENT_BLUE, ACCENT_GREEN,
                    ACCENT_RED, TEXT_GREY, ACCENT_CYAN)
from models.exotic_options import price_all_exotics
from models.black_scholes import (
    call_price, put_price, call_greeks, put_greeks,
    black76_call, black76_put, black76_greeks,
    bachelier_call, bachelier_put, bachelier_greeks,
)


_MODEL_INFO = {
    "BSM — Black-Scholes-Merton": {
        "desc": "Standard log-normal model. Underlying follows geometric Brownian motion.",
        "color": "#38BDF8",
    },
    "Black-76 — Black's Model": {
        "desc": "Log-normal model for forwards/futures. Uses F = S·e^{(r−q)T} as underlying.",
        "color": "#F0B429",
    },
    "Bachelier — Normal Model": {
        "desc": "Arithmetic Brownian motion. Handles negative underlyings. Input σ is lognormal; "
                "converted to normal vol σ_n = σ·F.",
        "color": "#10D48A",
    },
}


def render():
    st.markdown("## Exotic Options Pricer — Multi-Model")
    st.caption("BSM · Black-76 · Bachelier · Digitals · Touch · Barriers · Asian · Lookback · "
               "Chooser · Gap · Power · Range Accrual")

    # ── Copy Zone ──
    _has_sp_data = "sp_S0" in st.session_state
    _import_label = (
        f"Payoff Analyzer data available — S₀ = <b>{st.session_state.get('sp_S0', '—')}</b>"
        if _has_sp_data
        else "No Payoff Analyzer data yet — go to <b>Payoff Analyzer</b> first to populate"
    )
    _banner_color = "rgba(16,212,138,0.08)" if _has_sp_data else "rgba(240,180,41,0.07)"
    _border_color = "#10D48A" if _has_sp_data else "#F0B429"
    st.markdown(
        f"<div style='background:{_banner_color};border:1px solid {_border_color}55;"
        f"border-left:3px solid {_border_color};border-radius:8px;padding:10px 16px;"
        f"margin-bottom:10px;display:flex;align-items:center;justify-content:space-between'>"
        f"<span style='color:#9BAEC8;font-size:0.84rem'>{_import_label}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    use_copy = st.toggle(
        "⇠ Import S₀ & σ from Payoff Analyzer",
        value=False,
        key="ex_copy",
        disabled=not _has_sp_data,
        help="Auto-fills Spot and Volatility from the Payoff Analyzer tab" if _has_sp_data
             else "Open the Payoff Analyzer tab first to make data available",
    )

    # ── Model Selector ──
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#1A2E45,transparent);"
        "margin:10px 0 12px 0'></div>",
        unsafe_allow_html=True,
    )
    model_choice = st.radio(
        "**Pricing Model**",
        list(_MODEL_INFO.keys()),
        horizontal=True,
        key="ex_model",
    )
    _minfo = _MODEL_INFO[model_choice]
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.65);backdrop-filter:blur(10px);"
        f"-webkit-backdrop-filter:blur(10px);border:1px solid {_minfo['color']}33;"
        f"border-left:3px solid {_minfo['color']};border-radius:8px;padding:8px 14px;"
        f"margin-bottom:12px'>"
        f"<span style='color:#7B8EA8;font-size:0.82rem'>{_minfo['desc']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,#1A2E45,transparent);"
        "margin:0 0 12px 0'></div>",
        unsafe_allow_html=True,
    )

    # ── Market Parameters ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Market Parameters")
        default_S = st.session_state.get("sp_S0", 100.0) if st.session_state.get("ex_copy") else 100.0
        S = st.number_input("Spot Price S₀", value=default_S, step=1.0, key="ex_S")
        K = st.number_input("Strike K", value=100.0, step=1.0, key="ex_K")
        T = st.number_input("Maturity T (yr)", value=1.0, step=0.25, key="ex_T")
        r = st.number_input("Risk-Free Rate r", value=0.05, step=0.005, format="%.3f", key="ex_r")
        sigma = st.number_input("Volatility σ", value=0.20, step=0.01, format="%.2f", key="ex_sig")
        q = st.number_input("Dividend Yield q", value=0.02, step=0.005, format="%.3f", key="ex_q")

    with col2:
        st.markdown("#### Exotic Parameters")
        H_up = st.number_input("Upper Barrier H", value=120.0, step=5.0, key="ex_H")
        H_down = st.number_input("Lower Barrier L", value=80.0, step=5.0, key="ex_L")
        Q_pay = st.number_input("Digital Payout Q", value=1.0, step=0.1, key="ex_Q")
        sig2 = st.number_input("2nd Asset Vol σ₂", value=0.25, step=0.01, format="%.2f", key="ex_sig2")
        rho = st.number_input("Correlation ρ", value=0.50, step=0.1, format="%.2f", key="ex_rho")
        n_pow = st.number_input("Power n", value=2, step=1, key="ex_npow")
        t_c = st.number_input("Chooser Time t_c", value=0.5, step=0.1, format="%.2f", key="ex_tc")
        K_gap = st.number_input("Gap Strike K_gap", value=105.0, step=1.0, key="ex_Kgap")

    st.markdown("---")

    # ── Price All 15 Exotics ──
    results = price_all_exotics(
        S, K, T, r, sigma, q, H_up, H_down, Q_pay,
        sig2, rho, 95, n_pow, t_c, K_gap,
    )

    # ── Compute vanilla prices using the selected model ──
    F = S * np.exp((r - q) * T)  # forward price (shared by B76 and Bachelier)
    sigma_n = sigma * F           # normal vol for Bachelier (ATM approximation)

    if model_choice.startswith("Black-76"):
        call_p = black76_call(F, K, T, r, sigma)
        put_p  = black76_put(F, K, T, r, sigma)
        call_g = black76_greeks(F, K, T, r, sigma, is_call=True)
        put_g  = black76_greeks(F, K, T, r, sigma, is_call=False)
        model_label = "B76"
    elif model_choice.startswith("Bachelier"):
        call_p = bachelier_call(F, K, T, r, sigma_n)
        put_p  = bachelier_put(F, K, T, r, sigma_n)
        call_g = bachelier_greeks(F, K, T, r, sigma_n, is_call=True)
        put_g  = bachelier_greeks(F, K, T, r, sigma_n, is_call=False)
        model_label = "Bachelier"
    else:
        call_p = call_price(S, K, T, r, sigma, q)
        put_p  = put_price(S, K, T, r, sigma, q)
        call_g = call_greeks(S, K, T, r, sigma, q)
        put_g  = put_greeks(S, K, T, r, sigma, q)
        model_label = "BSM"

    call_d = call_g.get("delta")
    put_d  = put_g.get("delta")
    call_v = call_g.get("vega")
    call_t = call_g.get("theta")

    # ── Mini Dashboard ──
    by_name = {r["name"]: r for r in results}

    def price_of(name):
        r = by_name.get(name)
        return r["price"] if r else float("nan")

    def delta_of(name):
        r = by_name.get(name)
        return r.get("delta") if r else None

    # ── Vanilla row ──
    st.markdown(f"#### Vanilla Benchmark <span style='color:#5A6A82;font-size:0.75rem;font-weight:400'>— {model_label}</span>",
                unsafe_allow_html=True)
    _fwd_note = f"F = {F:.3f}" if not model_choice.startswith("BSM") else ""
    if _fwd_note:
        st.caption(f"Forward price: {_fwd_note}" + (f"  |  σ_n = {sigma_n:.3f}" if model_choice.startswith("Bachelier") else ""))
    vc1, vc2, vc3, vc4, vc5, vc6 = st.columns(6)
    vc1.metric("Call Price",   f"{call_p:.4f}")
    vc2.metric("Put Price",    f"{put_p:.4f}")
    vc3.metric("Call Δ",       f"{call_d:.4f}" if call_d is not None else "—")
    vc4.metric("Put Δ",        f"{put_d:.4f}"  if put_d  is not None else "—")
    vc5.metric("Vega",         f"{call_v:.4f}" if call_v is not None else "—")
    vc6.metric("Put-Call Par.", f"{abs(call_p - put_p):.4f}", help="|C − P|")

    # ── Digitals row ──
    st.markdown("#### Digitals")
    dc1, dc2, dc3, dc4 = st.columns(4)
    dc1.metric("Digital Call",  f"{price_of('Digital Call'):.4f}")
    dc2.metric("Digital Put",   f"{price_of('Digital Put'):.4f}")
    dc3.metric("Digital C+P",   f"{price_of('Digital Call') + price_of('Digital Put'):.4f}",
               help="Should ≈ Q·e⁻ʳᵀ")

    # ── Barriers / Touch row ──
    st.markdown("#### Touch / Barrier")
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("One-Touch ↑",   f"{price_of('One-Touch (Up)'):.4f}")
    bc2.metric("No-Touch ↑",    f"{price_of('No-Touch (Up)'):.4f}")
    bc3.metric("One-Touch ↓",   f"{price_of('One-Touch (Down)'):.4f}")
    bc4.metric("No-Touch ↓",    f"{price_of('No-Touch (Down)'):.4f}")
    bc5.metric("Dbl No-Touch",  f"{price_of('Double No-Touch'):.4f}")

    # ── Path-Dependent row ──
    st.markdown("#### Path-Dependent & Exotics")
    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("Asian Call (Geom.)", f"{price_of('Asian Call (Geometric)'):.4f}",
               delta=f"{price_of('Asian Call (Geometric)') - call_p:.4f} vs Call",
               delta_color="normal")
    ec2.metric("Lookback Call",      f"{price_of('Lookback Call (Floating)'):.4f}",
               delta=f"{price_of('Lookback Call (Floating)') - call_p:.4f} vs Call",
               delta_color="normal")
    ec3.metric("Chooser",            f"{price_of('Chooser Option'):.4f}")

    pow_name = next((r["name"] for r in results if r["name"].startswith("Power")), "")
    ec4, ec5, ec6 = st.columns(3)
    ec4.metric("Gap Call",           f"{price_of('Gap Call'):.4f}")
    ec5.metric("Power Option",       f"{price_of(pow_name):.4f}" if pow_name else "—")
    ec6.metric("Range Accrual",      f"{price_of('Range Accrual'):.4f}")

    st.markdown("---")
    st.markdown(
        "#### Full Table — Prices & Greeks "
        "<span style='color:#5A6A82;font-size:0.75rem;font-weight:400'>"
        "— Exotic options always use BSM closed-form</span>",
        unsafe_allow_html=True,
    )

    # Build display table
    rows = []
    for i, res in enumerate(results):
        row = {
            "#": i + 1,
            "Option": res["name"],
            "Method": res["method"],
            "Price": f"{res['price']:.4f}",
        }
        for g in ["delta", "gamma", "vega", "theta", "rho"]:
            val = res.get(g)
            row[g.capitalize()] = f"{val:.6f}" if val is not None else "—"
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=580)

    # ── Greeks Surface ──
    st.markdown("---")
    st.markdown("#### Greeks Visualization")

    greek_choice = st.selectbox("Select Greek to plot", ["Delta", "Gamma", "Vega", "Theta"],
                                key="ex_greek")
    opt_type = st.radio("Option type", ["Call", "Put"], horizontal=True, key="ex_opttype")

    S_range = np.linspace(max(S * 0.5, 1), S * 1.5, 80)
    sig_range = np.linspace(0.05, 0.60, 50)

    greek_key = greek_choice.lower()
    greek_fn = call_greeks if opt_type == "Call" else put_greeks

    Z = np.zeros((len(sig_range), len(S_range)))
    for i, sv in enumerate(sig_range):
        for j, spot in enumerate(S_range):
            try:
                g = greek_fn(spot, K, T, r, sv, q)
                Z[i, j] = g[greek_key]
            except Exception:
                Z[i, j] = 0

    fig = go.Figure(data=[go.Surface(
        x=S_range, y=sig_range, z=Z,
        colorscale="Blues", opacity=0.92,
        reversescale=True,
    )])
    fig.update_layout(
        title=f"{greek_choice} Surface — {opt_type} (K={K})",
        scene=dict(
            xaxis_title="Spot Price S",
            yaxis_title="Volatility σ",
            zaxis_title=greek_choice,
            bgcolor="rgba(14,17,23,0.8)",
        ),
        **{k: v for k, v in PLOTLY_LAYOUT.items() if k != "template"},
        template="plotly_dark",
        height=550,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 2D Greek vs Spot Price ──
    st.markdown(
        f"**{greek_choice} vs Spot Price** "
        f"<span style='color:#5A6A82;font-size:0.80rem'>"
        f"— σ = {sigma:.2f}, K = {K}, T = {T:.2f}y, r = {r:.3f}</span>",
        unsafe_allow_html=True,
    )
    greek_2d = np.zeros(len(S_range))
    for j, spot in enumerate(S_range):
        try:
            g = greek_fn(spot, K, T, r, sigma, q)
            greek_2d[j] = g[greek_key]
        except Exception:
            greek_2d[j] = 0

    _color_2d = _minfo["color"]
    fig2d = go.Figure()
    fig2d.add_trace(go.Scatter(
        x=S_range, y=greek_2d,
        mode="lines",
        line=dict(color=_color_2d, width=2.5),
        fill="tozeroy",
        fillcolor=f"rgba({int(_color_2d[1:3],16)},{int(_color_2d[3:5],16)},{int(_color_2d[5:7],16)},0.07)",
        name=f"{greek_choice} ({opt_type})",
        hovertemplate=f"<b>S</b>: %{{x:.2f}}<br><b>{greek_choice}</b>: %{{y:.5f}}<extra></extra>",
    ))
    fig2d.add_vline(x=S, line_dash="dash", line_color=ACCENT_GOLD, line_width=1.2,
                    annotation_text=f"S₀={S}", annotation_font_color=ACCENT_GOLD,
                    annotation_font_size=10)
    fig2d.add_vline(x=K, line_dash="dot", line_color=TEXT_GREY, line_width=1,
                    annotation_text=f"K={K}", annotation_font_color=TEXT_GREY,
                    annotation_font_size=10)
    fig2d.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text=f"{greek_choice} ({opt_type}) vs Spot Price",
                   font=dict(size=13, color="#9BAEC8")),
        xaxis_title="Spot Price S",
        yaxis_title=greek_choice,
        height=320,
        showlegend=False,
    )
    fig2d.update_xaxes(showgrid=False, tickfont=dict(size=10))
    fig2d.update_yaxes(showgrid=True, gridcolor="#1A2E45", zeroline=True,
                       zerolinecolor="#1A2E45", tickfont=dict(size=10))
    st.plotly_chart(fig2d, use_container_width=True)

    # ── Formulas Reference ──
    with st.expander("Formulas Reference"):
        formulas = [
            ("European Call", "C = S·e⁻qᵀ·N(d₁) − K·e⁻ʳᵀ·N(d₂)"),
            ("European Put", "P = K·e⁻ʳᵀ·N(−d₂) − S·e⁻qᵀ·N(−d₁)"),
            ("d₁, d₂", "d₁ = [ln(S/K) + (r−q+σ²/2)T] / (σ√T),  d₂ = d₁ − σ√T"),
            ("Digital Call", "DC = Q·e⁻ʳᵀ·N(d₂)"),
            ("Digital Put", "DP = Q·e⁻ʳᵀ·N(−d₂)"),
            ("One-Touch Up", "OT↑ = e⁻ʳᵀ·[N((μT−b)/(σ√T)) + e^(2μb/σ²)·N((−μT−b)/(σ√T))]"),
            ("No-Touch", "NT = e⁻ʳᵀ − OT"),
            ("Asian (Geom.)", "Kemna-Vorst: σ̂=σ/√3, b̂=½(r−q−σ²/6), then BSM(S,K,T,r,σ̂,b̂)"),
            ("Lookback", "Goldman-Sosin-Gatto closed-form with running min"),
            ("Chooser", "Rubinstein: C(S,K,T) + K·e⁻ʳᵀ·N(−d₂(tc)) − S·e⁻qᵀ·N(−d₁(tc))"),
            ("Gap Call", "GC = S·e⁻qᵀ·N(d₁(K_gap)) − K·e⁻ʳᵀ·N(d₂(K_gap))"),
            ("Power", "e⁻ʳᵀ · Sⁿ · exp[n(r−q)T + n(n−1)σ²T/2]"),
            ("Range Accrual", "P(L < S_T < H) · e⁻ʳᵀ via log-normal CDF"),
        ]
        for name, formula in formulas:
            st.markdown(f"**{name}**: `{formula}`")
