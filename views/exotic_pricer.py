"""views/exotic_pricer.py — 15 closed-form exotic options + vanilla benchmark across 3 models."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.black_scholes import (
    bachelier_call, bachelier_greeks, bachelier_put,
    black76_call, black76_greeks, black76_put,
    call_greeks, call_price, put_greeks, put_price,
)
from models.exotic_options import price_all_exotics
from ui.components import panel, Stat, callout, chart, page_header, require, section, stat_grid
from ui.formatting import num
from ui.theme import C, SEQUENTIAL, SERIES, rgba

_MODELS = {
    "BSM — Black-Scholes-Merton":
        "Standard log-normal model: the underlying follows geometric Brownian motion.",
    "Black-76 — Black's Model":
        "Log-normal model for forwards and futures, using F = S·e^((r−q)T) as the underlying.",
    "Bachelier — Normal Model":
        "Arithmetic Brownian motion; handles negative underlyings. The lognormal σ input is "
        "converted to a normal vol σₙ = σ·F.",
}

_FORMULAS = [
    ("European call", r"C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2)"),
    ("European put", r"P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)"),
    ("d₁, d₂", r"d_1 = \frac{\ln(S/K) + (r - q + \sigma^2/2)T}{\sigma\sqrt{T}},\quad d_2 = d_1 - \sigma\sqrt{T}"),
    ("Digital call / put", r"DC = Q e^{-rT} N(d_2),\quad DP = Q e^{-rT} N(-d_2)"),
    ("One-touch up", r"OT_\uparrow = e^{-rT}\left[N\!\left(\tfrac{\mu T - b}{\sigma\sqrt{T}}\right) + e^{2\mu b/\sigma^2} N\!\left(\tfrac{-\mu T - b}{\sigma\sqrt{T}}\right)\right]"),
    ("No-touch", r"NT = e^{-rT} - OT"),
    ("Asian (geometric, Kemna–Vorst)", r"\hat\sigma = \sigma/\sqrt{3},\quad \hat b = \tfrac12\left(r - q - \sigma^2/6\right)"),
    ("Chooser (Rubinstein)", r"C(S,K,T) + K e^{-rT} N(-d_2(t_c)) - S e^{-qT} N(-d_1(t_c))"),
    ("Gap call", r"GC = S e^{-qT} N(d_1(K_{gap})) - K e^{-rT} N(d_2(K_{gap}))"),
    ("Power", r"e^{-rT} S^n \exp\!\left[n(r-q)T + \tfrac{n(n-1)}{2}\sigma^2 T\right]"),
    ("Range accrual", r"e^{-rT}\,\mathbb{P}(L < S_T < H)"),
]


def _vanillas(model_choice, S, K, T, r, sigma, q):
    """Vanilla call/put prices and greeks under the selected model."""
    F = S * np.exp((r - q) * T)
    sigma_n = sigma * F
    if model_choice.startswith("Black-76"):
        return ("B76", F, sigma_n, black76_call(F, K, T, r, sigma), black76_put(F, K, T, r, sigma),
                black76_greeks(F, K, T, r, sigma, is_call=True),
                black76_greeks(F, K, T, r, sigma, is_call=False))
    if model_choice.startswith("Bachelier"):
        return ("Bachelier", F, sigma_n,
                bachelier_call(F, K, T, r, sigma_n), bachelier_put(F, K, T, r, sigma_n),
                bachelier_greeks(F, K, T, r, sigma_n, is_call=True),
                bachelier_greeks(F, K, T, r, sigma_n, is_call=False))
    return ("BSM", F, sigma_n, call_price(S, K, T, r, sigma, q), put_price(S, K, T, r, sigma, q),
            call_greeks(S, K, T, r, sigma, q), put_greeks(S, K, T, r, sigma, q))


def _greek_grid(greek_fn, key, spots, sigmas, K, T, r, q):
    Z = np.zeros((len(sigmas), len(spots)))
    for i, sv in enumerate(sigmas):
        for j, spot in enumerate(spots):
            try:
                Z[i, j] = greek_fn(spot, K, T, r, sv, q)[key]
            except Exception:
                Z[i, j] = 0
    return Z


def _f(x, d=4):
    return num(x, d) if x is not None else "—"


def render():
    page_header(
        "Exotic Pricer",
        "Closed-form prices and Greeks for 15 exotic payoffs, benchmarked against vanillas "
        "under Black-Scholes, Black-76 or Bachelier.",
        eyebrow="Options",
    )

    # ── Model + import ──
    shared_spot = st.session_state.get("shared_spot")
    has_sp = shared_spot is not None

    def _import_spot():
        if st.session_state.get("ex_copy") and has_sp:
            st.session_state["ex_S"] = float(shared_spot)

    top_l, top_r = st.columns([2.4, 1], vertical_alignment="center")
    model_choice = top_l.radio("Pricing model", list(_MODELS), horizontal=True, key="ex_model")
    top_r.toggle(
        "Import S₀ from Payoff Analyzer", value=False, key="ex_copy", disabled=not has_sp,
        on_change=_import_spot,
        help=(f"Payoff Analyzer spot available: S₀ = {shared_spot}" if has_sp
              else "Open the Payoff Analyzer first to make its spot available."),
    )
    callout(_MODELS[model_choice], tone="neutral")

    # ── Inputs ──
    col_mkt, col_exo = st.columns(2, gap="medium")
    with col_mkt, panel():
        st.markdown("**Market**")
        a, b, c = st.columns(3)
        S = a.number_input("Spot S₀", value=100.0, step=1.0, key="ex_S")
        K = b.number_input("Strike K", value=100.0, step=1.0, key="ex_K")
        T = c.number_input("Maturity T (y)", value=1.0, step=0.25, key="ex_T")
        a, b, c = st.columns(3)
        r = a.number_input("Rate r", value=0.05, step=0.005, format="%.3f", key="ex_r")
        sigma = b.number_input("Vol σ", value=0.20, step=0.01, format="%.2f", key="ex_sig")
        q = c.number_input("Div. yield q", value=0.02, step=0.005, format="%.3f", key="ex_q")
    with col_exo, panel():
        st.markdown("**Exotic parameters**")
        a, b, c = st.columns(3)
        H_up = a.number_input("Upper barrier H", value=120.0, step=5.0, key="ex_H")
        H_down = b.number_input("Lower barrier L", value=80.0, step=5.0, key="ex_L")
        Q_pay = c.number_input("Digital payout Q", value=1.0, step=0.1, key="ex_Q")
        a, b, c = st.columns(3)
        K_gap = a.number_input("Gap trigger", value=105.0, step=1.0, key="ex_Kgap")
        n_pow = b.number_input("Power n", value=2, step=1, key="ex_npow")
        t_c = c.number_input("Chooser t_c", value=0.5, step=0.1, format="%.2f", key="ex_tc")
        a, b, _ = st.columns(3)
        sig2 = a.number_input("2nd asset σ₂", value=0.25, step=0.01, format="%.2f", key="ex_sig2",
                              help="Reserved for two-asset exotics.")
        rho = b.number_input("Correlation ρ", value=0.50, step=0.1, format="%.2f", key="ex_rho",
                             help="Reserved for two-asset exotics.")

    require(S > 0, "Spot price S₀ must be positive.")
    require(K > 0, "Strike K must be positive.")
    require(T > 0, "Maturity T must be greater than 0.")
    require(sigma > 0, "Volatility σ must be positive.")
    require(H_up > H_down, f"Upper Barrier H ({H_up}) must be greater than Lower Barrier L ({H_down}).")
    require(t_c < T, f"Chooser time t_c ({t_c}) must be less than maturity T ({T}).")

    # ── Pricing ──
    results = price_all_exotics(S, K, T, r, sigma, q, H_up, H_down, Q_pay,
                                sig2, rho, 95, n_pow, t_c, K_gap)
    model_label, F, sigma_n, call_p, put_p, call_g, put_g = _vanillas(
        model_choice, S, K, T, r, sigma, q)
    by_name = {res["name"]: res for res in results}

    def price_of(name):
        res = by_name.get(name)
        return res["price"] if res else float("nan")

    pow_name = next((res["name"] for res in results if res["name"].startswith("Power")), "")
    asian, lookback = price_of("Asian Call (Geometric)"), price_of("Lookback Call (Floating)")

    tab_dash, tab_table, tab_greeks, tab_method = st.tabs(
        ["Overview", "Prices & Greeks", "Greeks explorer", "Methodology"])

    with tab_dash:
        caption = f"{model_label}"
        if not model_choice.startswith("BSM"):
            caption += f" · forward F = {F:.3f}"
        if model_choice.startswith("Bachelier"):
            caption += f" · σₙ = {sigma_n:.3f}"
        section("Vanilla benchmark", caption)
        stat_grid([
            Stat("Call price", _f(call_p)),
            Stat("Put price", _f(put_p)),
            Stat("Call Δ", _f(call_g.get("delta"))),
            Stat("Put Δ", _f(put_g.get("delta"))),
            Stat("Vega", _f(call_g.get("vega"))),
            Stat("|C − P|", _f(abs(call_p - put_p)), hint="put-call gap"),
        ], columns=6)

        section("Digitals", f"payout Q = {Q_pay:g}")
        stat_grid([
            Stat("Digital call", _f(price_of("Digital Call"))),
            Stat("Digital put", _f(price_of("Digital Put"))),
            Stat("Digital C + P", _f(price_of("Digital Call") + price_of("Digital Put")),
                 hint=f"≈ Q·e^(−rT) = {Q_pay * np.exp(-r * T):.4f}"),
        ], columns=3)

        section("Touch & barrier", f"L = {H_down:g} · H = {H_up:g}")
        stat_grid([
            Stat("One-touch ↑", _f(price_of("One-Touch (Up)"))),
            Stat("No-touch ↑", _f(price_of("No-Touch (Up)"))),
            Stat("One-touch ↓", _f(price_of("One-Touch (Down)"))),
            Stat("No-touch ↓", _f(price_of("No-Touch (Down)"))),
            Stat("Double no-touch", _f(price_of("Double No-Touch"))),
        ], columns=5)

        section("Path-dependent & other exotics", "always priced with BSM closed forms")
        stat_grid([
            Stat("Asian call (geom.)", _f(asian), delta=asian - call_p, delta_fmt="{:+.4f} vs call"),
            Stat("Lookback call", _f(lookback), delta=lookback - call_p, delta_fmt="{:+.4f} vs call"),
            Stat("Chooser", _f(price_of("Chooser Option")), hint=f"t_c = {t_c:g}y"),
            Stat("Gap call", _f(price_of("Gap Call")), hint=f"trigger {K_gap:g}"),
            Stat("Power option", _f(price_of(pow_name)) if pow_name else "—", hint=f"n = {n_pow}"),
            Stat("Range accrual", _f(price_of("Range Accrual"))),
        ], columns=6)

    with tab_table:
        callout("Exotic options always use BSM closed forms; Greeks are shown where an "
                "analytic expression is implemented.", tone="neutral")
        rows = []
        for i, res in enumerate(results):
            row = {"#": i + 1, "Option": res["name"], "Method": res["method"], "Price": res["price"]}
            for g in ["delta", "gamma", "vega", "theta", "rho"]:
                row[g.capitalize()] = res.get(g)
            rows.append(row)
        st.dataframe(
            pd.DataFrame(rows), width="stretch", hide_index=True, height=580,
            column_config={
                "Price": st.column_config.NumberColumn(format="%.4f"),
                **{g: st.column_config.NumberColumn(format="%.6f")
                   for g in ["Delta", "Gamma", "Vega", "Theta", "Rho"]},
            },
        )

    with tab_greeks:
        g1, g2, _ = st.columns([1, 1, 2])
        greek_choice = g1.selectbox("Greek", ["Delta", "Gamma", "Vega", "Theta"], key="ex_greek")
        opt_type = g2.radio("Option type", ["Call", "Put"], horizontal=True, key="ex_opttype")
        greek_key = greek_choice.lower()
        greek_fn = call_greeks if opt_type == "Call" else put_greeks
        S_range = np.linspace(max(S * 0.5, 1), S * 1.5, 80)
        sig_range = np.linspace(0.05, 0.60, 50)

        left, right = st.columns([1.3, 1], gap="medium")
        with left:
            Z = _greek_grid(greek_fn, greek_key, S_range, sig_range, K, T, r, q)
            fig = go.Figure(go.Surface(x=S_range, y=sig_range, z=Z, colorscale=SEQUENTIAL,
                                       opacity=0.95, showscale=False))
            fig.update_layout(
                title=f"{greek_choice} surface — {opt_type} (K = {K:g})",
                scene=dict(xaxis_title="Spot S", yaxis_title="Vol σ", zaxis_title=greek_choice),
                hovermode="closest", margin=dict(l=0, r=0, t=48, b=0),
            )
            chart(fig, height=480)
        with right:
            greek_2d = _greek_grid(greek_fn, greek_key, S_range, [sigma], K, T, r, q)[0]
            fig2d = go.Figure(go.Scatter(
                x=S_range, y=greek_2d, mode="lines", name=f"{greek_choice} ({opt_type})",
                line=dict(color=SERIES[0], width=2),
                fill="tozeroy", fillcolor=rgba(SERIES[0], 0.08),
                hovertemplate=f"S %{{x:.2f}}<br>{greek_choice} %{{y:.5f}}<extra></extra>",
            ))
            fig2d.add_vline(x=S, line_dash="dash", line_color=C.muted, line_width=1,
                            annotation_text=f"S₀ = {S:g}", annotation_font_color=C.muted)
            fig2d.add_vline(x=K, line_dash="dot", line_color=C.subtle, line_width=1,
                            annotation_text=f"K = {K:g}", annotation_font_color=C.subtle,
                            annotation_position="bottom right")
            fig2d.update_layout(
                title=f"{greek_choice} vs spot · σ = {sigma:.2f}, T = {T:.2f}y",
                xaxis_title="Spot S", yaxis_title=greek_choice, showlegend=False,
                hovermode="closest",
            )
            chart(fig2d, height=480)

    with tab_method:
        for name, latex in _FORMULAS:
            st.markdown(f"**{name}**")
            st.latex(latex)
        st.caption("Lookback: Goldman–Sosin–Gatto closed form with running minimum. "
                   "μ = r − q − σ²/2, b = ln(H/S).")
