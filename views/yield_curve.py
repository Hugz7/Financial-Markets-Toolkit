"""
views/yield_curve.py — Yield Curve Builder.

Bootstrap the zero/spot curve from T-Bills, T-Notes, T-Bonds; display spot,
forward and par curves with key spreads; Z-spread and ASW for a single bond.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.yield_curve import (
    asw_spread as calc_asw_spread,
    bootstrap_spot_rates,
    interpolate_curve,
    key_spreads,
    spot_to_forward,
    spot_to_par,
    z_spread as calc_z_spread,
)
from ui.components import (Stat, badges, callout, chart, empty_state, page_header,
                           section, stat_grid)
from ui.theme import C, SERIES, rgba

_FREQ_LABEL = {1: "Annual", 2: "Semi-annual", 4: "Quarterly"}

_DEFAULT_INSTRUMENTS = pd.DataFrame([
    {"Type": "T-Bill", "Maturity (y)": 0.083, "Rate/Coupon (%)": 5.30, "Price": 100.0, "Include": True},
    {"Type": "T-Bill", "Maturity (y)": 0.25,  "Rate/Coupon (%)": 5.25, "Price": 100.0, "Include": True},
    {"Type": "T-Bill", "Maturity (y)": 0.50,  "Rate/Coupon (%)": 5.15, "Price": 100.0, "Include": True},
    {"Type": "T-Bill", "Maturity (y)": 1.00,  "Rate/Coupon (%)": 4.90, "Price": 100.0, "Include": True},
    {"Type": "T-Note", "Maturity (y)": 2.00,  "Rate/Coupon (%)": 4.50, "Price": 100.0, "Include": True},
    {"Type": "T-Note", "Maturity (y)": 3.00,  "Rate/Coupon (%)": 4.30, "Price": 100.0, "Include": True},
    {"Type": "T-Note", "Maturity (y)": 5.00,  "Rate/Coupon (%)": 4.20, "Price": 100.0, "Include": True},
    {"Type": "T-Note", "Maturity (y)": 7.00,  "Rate/Coupon (%)": 4.25, "Price": 100.0, "Include": True},
    {"Type": "T-Note", "Maturity (y)": 10.00, "Rate/Coupon (%)": 4.30, "Price": 100.0, "Include": True},
    {"Type": "T-Bond", "Maturity (y)": 20.00, "Rate/Coupon (%)": 4.55, "Price": 100.0, "Include": True},
    {"Type": "T-Bond", "Maturity (y)": 30.00, "Rate/Coupon (%)": 4.45, "Price": 100.0, "Include": True},
])


def _bps(x: float, signed: bool = True) -> str:
    return "—" if x != x else f"{x:{'+' if signed else ''}.1f} bps"


# ── Curve interpretation (plain-language reading of the spreads) ──────────────

def _interpret(spreads: dict) -> dict:
    """Return {'slope': (label, tone, text), 'signals': [(title, tone, text), ...], 'butterfly': text}."""
    s2s10, s3m10 = spreads["2s10s"], spreads["3M10Y"]
    s10s30, bfly = spreads["10s30s"], spreads["butterfly_2_5_10"]

    if s2s10 > 100:
        slope = ("Steep normal", "pos",
                 f"2s10s at {s2s10:+.1f} bps — the long end sits well above the short end. Markets "
                 "price sustained growth, higher future inflation or a rising term premium; typical of "
                 "early expansions and post-tightening recoveries.")
    elif s2s10 > 25:
        slope = ("Normal", "pos",
                 f"2s10s at {s2s10:+.1f} bps — a classic upward-sloping curve. Term premium is positive: "
                 "investors demand more for longer maturities, consistent with neutral-to-accommodative policy.")
    elif s2s10 > -25:
        slope = ("Flat", "warn",
                 f"2s10s at {s2s10:+.1f} bps — a near-zero slope signals uncertainty between growth "
                 "(steepening) and tightening (inversion). Flat curves often precede inflection points in the rate cycle.")
    elif s2s10 > -75:
        slope = ("Mildly inverted", "neg",
                 f"2s10s at {s2s10:+.1f} bps — short rates exceed 10Y rates, historically a sign of late-cycle "
                 "tightening or slowing growth. Has preceded 7 of the last 8 US recessions.")
    else:
        slope = ("Deeply inverted", "neg",
                 f"2s10s at {s2s10:+.1f} bps — a strong recessionary signal: policy keeps short rates high while "
                 "the long end prices future cuts. Long duration has historically outperformed in this regime.")

    if s3m10 < -50:
        recession = (f"3M10Y · recessionary", "neg",
                     f"{s3m10:+.1f} bps — deeply negative. The Fed's preferred recession predictor (Estrella & "
                     "Mishkin, 1996): sustained inversion has preceded every US recession since 1968, with a 12–18 month lead.")
    elif s3m10 < 0:
        recession = (f"3M10Y · mildly inverted", "warn",
                     f"{s3m10:+.1f} bps — negative but not extreme; a watch signal. Duration of the inversion "
                     "matters more than its depth.")
    else:
        recession = (f"3M10Y · positive", "pos",
                     f"{s3m10:+.1f} bps — no imminent recession signal; the curve pays a premium for longer maturities.")

    if s10s30 > 30:
        long_end = (f"{s10s30:+.1f} bps — steep long end. Elevated ultra-long term premium: fiscal concerns, "
                    "inflation risk, or weak demand from pensions and foreign buyers.")
    elif s10s30 > -10:
        long_end = (f"{s10s30:+.1f} bps — flat long end, typical of mature tightening cycles or strong demand "
                    "for long-duration assets (liability matching).")
    else:
        long_end = (f"{s10s30:+.1f} bps — inverted long end: structural demand for 30Y duration "
                    "(LDI, reserve managers) or pricing of long-run rate compression.")

    if s2s10 > 0:
        carry = ("Positive carry — owning duration earns carry, and a 10Y bond rolls down toward the steeper "
                 "short end, gaining if rates stay unchanged.")
    else:
        carry = ("Negative carry — long bonds need a rally to profit; short-end and floating-rate positions "
                 "are rewarded in this environment.")

    if bfly > 20:
        butterfly = (f"Butterfly (2-5-10) at {bfly:+.1f} bps — humped: the 5Y is cheap versus the wings, often "
                     "from 5Y supply pressure or flight-to-quality at 2Y/10Y.")
    elif bfly < -20:
        butterfly = (f"Butterfly (2-5-10) at {bfly:+.1f} bps — the 5Y is rich versus the wings, common in easing "
                     "cycles where the belly anchors rate-cut expectations.")
    else:
        butterfly = f"Butterfly (2-5-10) at {bfly:+.1f} bps — balanced curvature; the belly is close to linear."

    return {
        "slope": slope,
        "signals": [recession, ("Long end · 10s30s", "info", long_end), ("Carry & roll-down", "neutral", carry)],
        "butterfly": butterfly,
    }


def _render_interpretation(spreads: dict) -> None:
    reading = _interpret(spreads)
    label, tone, text = reading["slope"]
    section("Curve interpretation")
    badges([(f"Curve shape · {label}", tone)])
    callout(text, tone=tone)
    for col, (title, sig_tone, body) in zip(st.columns(3), reading["signals"]):
        with col:
            callout(body, title=title, tone=sig_tone)
    callout(reading["butterfly"], tone="neutral")


# ── Inputs ────────────────────────────────────────────────────────────────────

def _settings_panel():
    with st.container(border=True):
        section("Curve settings")
        c1, c2 = st.columns(2)
        interp = c1.selectbox("Interpolation", ["Cubic Spline", "Linear"], key="yc_interp",
                              help="Method used to smooth the bootstrapped rates onto the fine grid.")
        freq_par = c2.selectbox("Par frequency", [2, 1, 4], format_func=_FREQ_LABEL.get, key="yc_freq",
                                help="Coupon payments per year used in the par rate.")
        t1, t2 = st.columns(2)
        show_fwd = t1.toggle("Forward", value=True, key="yc_fwd")
        show_par = t2.toggle("Par", value=True, key="yc_par")

    with st.container(border=True):
        section("Instruments", "edit, add or exclude rows")
        st.caption("T-Bills: zero-coupon, rate = simple yield. T-Notes / T-Bonds: "
                   "semi-annual coupon, price = dirty price.")
        if "yc_instruments" not in st.session_state:
            st.session_state["yc_instruments"] = _DEFAULT_INSTRUMENTS.copy()
        edited = st.data_editor(
            st.session_state["yc_instruments"], num_rows="dynamic", width="stretch",
            key="yc_table", hide_index=True,
            column_config={
                "Type": st.column_config.SelectboxColumn("Type", options=["T-Bill", "T-Note", "T-Bond"],
                                                         required=True, width="small"),
                "Maturity (y)": st.column_config.NumberColumn("Mat (y)", min_value=0.01, max_value=50.0,
                                                              step=0.25, format="%.3f"),
                "Rate/Coupon (%)": st.column_config.NumberColumn("Rate %", min_value=-2.0, max_value=20.0,
                                                                 step=0.05, format="%.3f"),
                "Price": st.column_config.NumberColumn("Price", min_value=50.0, max_value=150.0,
                                                       step=0.01, format="%.2f"),
                "Include": st.column_config.CheckboxColumn("Use", width="small"),
            },
        )
        st.session_state["yc_instruments"] = edited
        if st.button("Reset defaults", key="yc_reset", icon=":material/restart_alt:", width="stretch"):
            st.session_state["yc_instruments"] = _DEFAULT_INSTRUMENTS.copy()
            st.rerun()
    return interp, freq_par, show_fwd, show_par, edited


# ── Page ──────────────────────────────────────────────────────────────────────

def render():
    page_header(
        "Yield Curve",
        "Bootstrap spot, forward and par curves from T-Bills, T-Notes and T-Bonds, read the shape, "
        "and price a bond's Z-spread and asset-swap spread off the curve.",
        eyebrow="Rates & Forwards",
    )

    col_cfg, col_main = st.columns([1.35, 2.4], gap="large")
    with col_cfg:
        interp, freq_par, show_fwd, show_par, edited = _settings_panel()

    with col_main:
        active = edited[edited["Include"] == True].sort_values("Maturity (y)")  # noqa: E712
        if len(active) < 2:
            empty_state("Not enough instruments", "Include at least two instruments to bootstrap the curve.")
            return

        instruments = [{
            "type": row["Type"], "maturity": float(row["Maturity (y)"]),
            "rate": float(row["Rate/Coupon (%)"]) / 100.0, "price": float(row["Price"]), "freq": 2,
        } for _, row in active.iterrows()]

        try:
            mats, spots = bootstrap_spot_rates(instruments)
        except Exception as exc:
            st.error(f"Bootstrapping failed — {exc}", icon=":material/error:")
            return

        T_max = mats.max()
        method = "cubic" if interp == "Cubic Spline" else "linear"
        t_fine = np.linspace(mats.min(), T_max, 500)
        spot_fine = interpolate_curve(mats, spots, t_fine, method=method)
        fwd_fine = spot_to_forward(t_fine, spot_fine)
        par_fine = spot_to_par(t_fine, spot_fine, freq=freq_par)
        spreads = key_spreads(mats, spots)

        # ── Key metrics ──
        stat_grid([Stat(f"{k} spot", f"{spreads[k]:.2f}%") for k in ("3M", "2Y", "5Y", "10Y", "30Y")],
                  columns=5)

        def _spread_stat(key, label, flag_inversion=False):
            v = spreads[key]
            tone = ("neg" if v < 0 else "pos") if flag_inversion else "default"
            hint = ("inverted" if v < 0 else "normal") if flag_inversion else None
            return Stat(label, _bps(v), hint=hint, tone=tone, small=True)

        stat_grid([
            _spread_stat("2s10s", "2s10s", flag_inversion=True),
            _spread_stat("3M10Y", "3M10Y", flag_inversion=True),
            _spread_stat("10s30s", "10s30s"),
            _spread_stat("5s30s", "5s30s"),
            Stat("Butterfly 2-5-10", _bps(spreads["butterfly_2_5_10"]), hint="2Y + 10Y − 2×5Y", small=True),
        ], columns=5)

        tab_curve, tab_reading, tab_data, tab_spread = st.tabs(
            ["Curves", "Interpretation", "Bootstrapped data", "Z-spread & ASW"])

        # ── Curves ──
        with tab_curve:
            fig = go.Figure()
            fig.add_trace(go.Scatter(   # carry region between spot and forward
                x=np.concatenate([t_fine, t_fine[::-1]]),
                y=np.concatenate([spot_fine, fwd_fine[::-1]]) * 100,
                fill="toself", fillcolor=rgba(SERIES[0], 0.06), line=dict(width=0),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=t_fine, y=spot_fine * 100, mode="lines", name="Spot (zero)",
                line=dict(color=SERIES[0], width=2.5),
                hovertemplate="Spot %{y:.3f}%<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=mats, y=spots * 100, mode="markers", name="Bootstrapped knots",
                marker=dict(color=SERIES[0], size=9, line=dict(color=C.bg, width=2)),
                customdata=active["Type"].values,
                hovertemplate="%{customdata} knot %{y:.4f}%<extra></extra>",
            ))
            if show_fwd:
                fig.add_trace(go.Scatter(
                    x=t_fine, y=fwd_fine * 100, mode="lines", name="Forward",
                    line=dict(color=SERIES[1], dash="dash"),
                    hovertemplate="Forward %{y:.3f}%<extra></extra>",
                ))
            if show_par:
                fig.add_trace(go.Scatter(
                    x=t_fine, y=par_fine * 100, mode="lines", name="Par",
                    line=dict(color=SERIES[2], dash="dot"),
                    hovertemplate="Par %{y:.3f}%<extra></extra>",
                ))
            fig.update_xaxes(title_text="Maturity (years)", ticksuffix="y", showgrid=False)
            fig.update_yaxes(title_text="Rate", ticksuffix="%")
            chart(fig, height=460, title="Spot · forward · par")

            with st.expander("Methodology — how each curve is built"):
                st.markdown("**Bootstrapping.** T-Bills are zero-coupon:")
                st.latex(r"z(T) = \left(\frac{100}{P}\right)^{1/T} - 1")
                st.markdown("T-Notes / T-Bonds are solved one maturity at a time — "
                            r"$z_{T_n}$ is the only unknown, earlier $z_i$ are already bootstrapped:")
                st.latex(r"P = \sum_{i=1}^{n-1} \frac{C/f \times 100}{(1+z_i)^{t_i}}"
                         r" + \frac{(C/f+1)\times 100}{(1+z_{T_n})^{T_n}}")
                st.markdown(r"**Forward rates** over $t_{i-1} \to t_i$ (forward above spot ⟹ upward-sloping curve):")
                st.latex(r"f(t_{i-1}, t_i) = \left[\frac{(1+z_i)^{t_i}}{(1+z_{i-1})^{t_{i-1}}}\right]"
                         r"^{1/(t_i - t_{i-1})} - 1")
                st.markdown(r"**Par rates** — the fair coupon for a bond priced at par, with "
                            r"$df(t) = (1+z(t))^{-t}$ and $\alpha = 1/f$:")
                st.latex(r"\text{par}(T) = \frac{1 - df(T)}{\sum_{i=1}^{n} df(t_i)\,\alpha}")

        # ── Interpretation ──
        with tab_reading:
            _render_interpretation(spreads)

        # ── Bootstrapped data ──
        with tab_data:
            t_table = np.arange(0.25, T_max + 0.01, 0.25)
            t_table = t_table[t_table <= T_max]
            z_tab = interpolate_curve(mats, spots, t_table, method=method)
            disc = (1.0 + z_tab) ** (-t_table)
            df_display = pd.DataFrame({
                "Maturity (y)": t_table,
                "Spot (%)": z_tab * 100,
                "Forward (%)": spot_to_forward(t_table, z_tab) * 100,
                "Par (%)": spot_to_par(t_table, z_tab, freq=freq_par) * 100,
                "Discount factor": disc,
            })
            st.dataframe(
                df_display, width="stretch", hide_index=True, height=380,
                column_config={
                    "Maturity (y)": st.column_config.NumberColumn(format="%.2f"),
                    "Spot (%)": st.column_config.NumberColumn(format="%.4f"),
                    "Forward (%)": st.column_config.NumberColumn(format="%.4f"),
                    "Par (%)": st.column_config.NumberColumn(format="%.4f"),
                    "Discount factor": st.column_config.NumberColumn(format="%.6f"),
                },
            )
            fig_df = go.Figure(go.Scatter(
                x=t_table, y=disc, mode="lines", name="df(T)",
                line=dict(color=SERIES[0]), fill="tozeroy", fillcolor=rgba(SERIES[0], 0.08),
                hovertemplate="df %{y:.6f}<extra></extra>",
            ))
            fig_df.update_xaxes(title_text="Maturity (years)", showgrid=False)
            fig_df.update_yaxes(title_text="Discount factor")
            fig_df.update_layout(showlegend=False)
            chart(fig_df, height=280, title="Discount factors  df(T) = (1 + z(T))^−T")

        # ── Z-spread & ASW ──
        with tab_spread:
            _bond_spreads(mats, spots, T_max, method)


def _bond_spreads(mats: np.ndarray, spots: np.ndarray, T_max: float, method: str) -> None:
    section("Bond spread analysis", "relative to the bootstrapped curve")
    with st.container(border=True):
        b1, b2, b3, b4 = st.columns(4)
        bond_coupon = b1.number_input(
            "Annual coupon", value=0.0450, step=0.0025, format="%.4f", key="yc_cpn",
            help="Annual coupon rate (decimal). CF = coupon / freq × 100 per period.")
        bond_mat = b2.number_input(
            "Maturity (years)", value=10.0, step=0.5, format="%.2f", key="yc_bmat",
            help="Years to maturity. Should be ≤ the longest bootstrapped maturity.")
        bond_freq = b3.selectbox("Coupon frequency", [2, 1, 4], format_func=_FREQ_LABEL.get,
                                 key="yc_bfreq", help="Coupon payments per year.")
        bond_price = b4.number_input(
            "Dirty price", value=98.50, step=0.25, format="%.4f", key="yc_bpx",
            help="Full price per 100 face. P < 100 → discount, P > 100 → premium.")
    if bond_mat > T_max:
        callout(f"Bond maturity ({bond_mat}y) exceeds the longest bootstrapped instrument "
                f"({T_max}y); rates are extrapolated flat.", tone="warn")

    try:
        zs = calc_z_spread(bond_price, bond_coupon, bond_mat, mats, spots, freq=bond_freq)
        asw = calc_asw_spread(bond_price, bond_coupon, bond_mat, mats, spots, freq=bond_freq)
    except Exception as exc:
        st.error(f"Spread calculation failed — {exc}", icon=":material/error:")
        return

    zs_bps = zs * 10_000 if not np.isnan(zs) else np.nan
    asw_bps = asw * 10_000 if not np.isnan(asw) else np.nan
    z_at_mat = float(interpolate_curve(mats, spots, np.array([bond_mat]), method=method)[0])
    par_rates_bond = spot_to_par(np.array([bond_mat]), np.array([z_at_mat]), freq=bond_freq)
    par_at_mat = float(par_rates_bond[0]) if len(par_rates_bond) else 0.0

    stat_grid([
        Stat("Z-spread", _bps(zs_bps, signed=False), hint="parallel shift so PV = price"),
        Stat("ASW spread", _bps(asw_bps, signed=False), hint="par-par asset swap"),
        Stat("Par rate at maturity", f"{par_at_mat * 100:.3f}%", hint="fair coupon at par"),
        Stat("Z-spread − ASW", _bps(zs_bps - asw_bps), hint="convexity / curve shape"),
    ])

    # PV vs Z-spread sensitivity
    zs_range = np.linspace(-0.01, 0.05, 300)  # −100 to +500 bps
    alpha_b = 1.0 / bond_freq
    n_b = int(round(bond_mat * bond_freq))
    cf_times_b = np.array([i * alpha_b for i in range(1, n_b + 1)])
    coupons_b = np.full(n_b, bond_coupon / bond_freq * 100.0)
    if n_b:
        coupons_b[-1] += 100.0
    z_interp_b = np.interp(cf_times_b, mats, spots)
    pv_curve = np.array([(coupons_b / (1.0 + z_interp_b + s) ** cf_times_b).sum() for s in zs_range])

    fig_zs = go.Figure(go.Scatter(
        x=zs_range * 10_000, y=pv_curve, mode="lines", name="PV(zs)",
        line=dict(color=SERIES[0]), fill="tozeroy", fillcolor=rgba(SERIES[0], 0.06),
        hovertemplate="PV %{y:.4f}<extra></extra>",
    ))
    fig_zs.add_hline(y=bond_price, line_dash="dash", line_color=C.muted, line_width=1,
                     annotation_text=f"Market price {bond_price:.2f}", annotation_font_color=C.muted)
    if not np.isnan(zs_bps):
        fig_zs.add_vline(x=zs_bps, line_dash="dot", line_color=SERIES[1], line_width=1.5,
                         annotation_text=f"Z-spread {zs_bps:.1f} bps", annotation_font_color=C.text_2)
    fig_zs.update_xaxes(title_text="Z-spread (bps)", showgrid=False)
    fig_zs.update_yaxes(title_text="Present value", rangemode="tozero")
    fig_zs.update_layout(showlegend=False)
    chart(fig_zs, height=340, title="Bond PV as a function of the Z-spread")

    with st.expander("Methodology — Z-spread & ASW"):
        st.markdown(r"**Z-spread** — the constant $zs$ added to every spot rate so discounted "
                    "cashflows equal the market price (credit + liquidity premium over the curve):")
        st.latex(r"P = \sum_{i=1}^{n} \frac{CF_i}{\bigl(1 + z(t_i) + zs\bigr)^{t_i}}")
        st.markdown(r"**Par-par asset swap spread** — buy the bond at $P$ and swap the fixed coupon $C$ "
                    "for SOFR + s. The breakeven spread:")
        st.latex(r"ASW = (C - r_{\text{par}}) + \frac{100 - P}{100 \times \text{annuity}},\qquad "
                 r"r_{\text{par}} = \frac{1 - df(T)}{\text{annuity}},\quad "
                 r"\text{annuity} = \sum_{i} df(t_i)\,\alpha")
        st.markdown("If P = 100 and C = r_par, ASW = 0. ASW > 0 signals a credit / liquidity premium; "
                    "Z-spread ≈ ASW for near-par bonds and they diverge for distressed ones.")
