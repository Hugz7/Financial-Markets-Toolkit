"""
yield_curve_page.py — Yield Curve Builder.

Bootstrap the zero/spot curve from T-Bills, T-Notes, T-Bonds.
Display Spot · Forward · Par curves with key spread metrics.
Compute Z-spread and ASW spread for individual bonds.
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import (
    PLOTLY_LAYOUT, ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_RED, ACCENT_GOLD, TEXT_GREY,
)
from models.yield_curve import (
    bootstrap_spot_rates,
    interpolate_curve,
    spot_to_forward,
    spot_to_par,
    z_spread as calc_z_spread,
    asw_spread as calc_asw_spread,
    key_spreads,
)


# ── Default instrument table ───────────────────────────────────────────────────

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


# ── Formula tooltip helper ─────────────────────────────────────────────────────

def _info_box(formula: str, explanation: str, color: str = ACCENT_CYAN) -> None:
    """Render a compact formula callout box."""
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.65);border-left:3px solid {color};"
        f"border-radius:0 6px 6px 0;padding:7px 12px;margin:4px 0 10px 0;"
        f"color:#9BAEC8;font-size:0.80rem'>"
        f"<span style='color:{color};font-family:monospace;font-size:0.85rem'>"
        f"{formula}</span>"
        f"<br><span style='color:#6A7E99;font-size:0.76rem'>{explanation}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _glass_card(label: str, value: str, color: str, sub: str = "") -> str:
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
        f"<div style='color:{color};font-size:1.08rem;font-weight:700;"
        f"font-variant-numeric:tabular-nums'>{value}</div>"
        f"{sub_html}</div>"
    )


def _spread_badge(label: str, value_bps: float) -> str:
    color = ACCENT_GREEN if value_bps >= 0 else ACCENT_RED
    sign  = "+" if value_bps >= 0 else ""
    return _glass_card(label, f"{sign}{value_bps:.1f} bps", color)


# ── Curve Interpretation ──────────────────────────────────────────────────────

def _render_curve_interpretation(spreads: dict) -> None:
    """
    Automatic plain-language interpretation of the bootstrapped yield curve.
    Covers slope, inversion signals, butterfly shape, and carry regime.
    """
    s2s10  = spreads["2s10s"]
    s3m10  = spreads["3M10Y"]
    s10s30 = spreads["10s30s"]
    bfly   = spreads["butterfly_2_5_10"]
    z3m    = spreads["3M"]
    z10    = spreads["10Y"]
    z30    = spreads["30Y"]

    # ── Slope classification ─────────────────────────────────────────────────
    if s2s10 > 100:
        slope_label = "STEEP NORMAL"
        slope_color = ACCENT_GREEN
        slope_desc  = (
            f"2s10s spread of **{s2s10:+.1f} bps** — the long end is significantly above "
            "the short end. Markets are pricing in sustained growth, higher future inflation, "
            "or a rising term premium. Typical of early expansion phases or post-tightening recoveries."
        )
    elif s2s10 > 25:
        slope_label = "NORMAL"
        slope_color = ACCENT_GREEN
        slope_desc  = (
            f"2s10s spread of **{s2s10:+.1f} bps** — classic upward-sloping curve. "
            "Term premium is positive: investors demand more compensation for longer maturities. "
            "Consistent with a neutral-to-accommodative monetary policy backdrop."
        )
    elif s2s10 > -25:
        slope_label = "FLAT"
        slope_color = ACCENT_GOLD
        slope_desc  = (
            f"2s10s spread of **{s2s10:+.1f} bps** — near-zero slope signals uncertainty. "
            "The market is undecided between growth (steepening) and tightening (inversion). "
            "Flat curves often precede inflection points in the rate cycle."
        )
    elif s2s10 > -75:
        slope_label = "MILDLY INVERTED"
        slope_color = ACCENT_RED
        slope_desc  = (
            f"2s10s spread of **{s2s10:+.1f} bps** — mild inversion. "
            "Short rates exceed 10Y rates, historically signalling late-cycle Fed tightening "
            "or decelerating growth expectations. Has preceded 7 of the last 8 US recessions."
        )
    else:
        slope_label = "DEEPLY INVERTED"
        slope_color = ACCENT_RED
        slope_desc  = (
            f"2s10s spread of **{s2s10:+.1f} bps** — deep inversion. "
            "A strong recessionary signal: the Fed is keeping short rates elevated while "
            "long-end rates anticipate future cuts. Duration trades (long bonds) have "
            "historically outperformed in this regime."
        )

    # ── 3M10Y signal (Fed's preferred recession predictor) ───────────────────
    if s3m10 < -50:
        recession_label = "RECESSIONARY"
        recession_color = ACCENT_RED
        recession_desc  = (
            f"3M10Y = **{s3m10:+.1f} bps** — deeply negative. "
            "This is the Fed's preferred recession predictor (Estrella & Mishkin, 1996). "
            "A sustained inversion > 3 months preceded every US recession since 1968 "
            "with an average 12–18 month lead time."
        )
    elif s3m10 < 0:
        recession_label = "MILDLY INVERTED"
        recession_color = ACCENT_GOLD
        recession_desc  = (
            f"3M10Y = **{s3m10:+.1f} bps** — negative but not extreme. "
            "Short-end rates above long-end: a watch signal. Duration of inversion matters more "
            "than depth for recession probability."
        )
    else:
        recession_label = "POSITIVE"
        recession_color = ACCENT_GREEN
        recession_desc  = (
            f"3M10Y = **{s3m10:+.1f} bps** — positive. "
            "No imminent recession signal from this measure. "
            "The term structure is paying a premium for holding longer maturities."
        )

    # ── Long end (10s30s) ────────────────────────────────────────────────────
    if s10s30 > 30:
        long_end_desc = (
            f"10s30s = **{s10s30:+.1f} bps** — steep long end. "
            "Term premium at the ultra-long end is elevated: fiscal deficit concerns, "
            "inflation risk, or low demand from pension funds / foreign buyers."
        )
    elif s10s30 > -10:
        long_end_desc = (
            f"10s30s = **{s10s30:+.1f} bps** — flat long end. "
            "Typical of mature tightening cycles or strong demand for long-duration assets "
            "(insurance/pension liability matching)."
        )
    else:
        long_end_desc = (
            f"10s30s = **{s10s30:+.1f} bps** — inverted long end. "
            "Ultra-long rates below 10Y: strong structural demand for 30Y duration "
            "(LDI, foreign reserve managers), or pricing in long-run rate compression."
        )

    # ── Butterfly shape ───────────────────────────────────────────────────────
    if bfly > 20:
        bfly_desc = (
            f"Butterfly (2-5-10) = **{bfly:+.1f} bps** — positive (humped). "
            "The 5Y is cheap vs wings: the belly of the curve is concave. "
            "Often driven by supply pressure at 5Y or flight-to-quality at 2Y/10Y."
        )
    elif bfly < -20:
        bfly_desc = (
            f"Butterfly (2-5-10) = **{bfly:+.1f} bps** — negative (concave). "
            "The 5Y is rich vs wings: the belly outperforms. "
            "Common in easing cycles where the 5Y anchors rate-cut expectations."
        )
    else:
        bfly_desc = (
            f"Butterfly (2-5-10) = **{bfly:+.1f} bps** — near zero. "
            "Balanced curvature: the curve is relatively linear across the belly."
        )

    # ── Carry & roll-down comment ─────────────────────────────────────────────
    if s2s10 > 0:
        carry_desc = (
            "**Positive carry regime** — owning duration earns carry. "
            "A bond held at 10Y will roll down the curve toward the steeper short end, "
            "generating mark-to-market gains if rates stay unchanged (roll-down effect)."
        )
    else:
        carry_desc = (
            "**Negative carry regime** — owning duration costs carry. "
            "Investors in long bonds must rely on a rally (rate decline) to profit. "
            "Short-end positions or floating-rate instruments are rewarded in this environment."
        )

    # ── Render ────────────────────────────────────────────────────────────────
    st.markdown("#### Curve Interpretation")

    # Main slope badge + description
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.72);border:1px solid {slope_color}33;"
        f"border-left:4px solid {slope_color};border-radius:8px;"
        f"padding:12px 16px;margin-bottom:8px'>"
        f"<span style='color:{slope_color};font-size:0.72rem;font-weight:700;"
        f"letter-spacing:0.1em;text-transform:uppercase'>Curve Shape — {slope_label}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(slope_desc)

    # Three columns: recession signal | long end | carry
    ic1, ic2, ic3 = st.columns(3)

    with ic1:
        st.markdown(
            f"<div style='background:rgba(8,18,32,0.60);border-left:3px solid {recession_color};"
            f"border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:6px'>"
            f"<span style='color:{recession_color};font-size:0.68rem;font-weight:700;"
            f"letter-spacing:0.08em;text-transform:uppercase'>3M10Y — {recession_label}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<span style='font-size:0.82rem;color:#9BAEC8'>{recession_desc}</span>",
                    unsafe_allow_html=True)

    with ic2:
        st.markdown(
            f"<div style='background:rgba(8,18,32,0.60);border-left:3px solid {ACCENT_BLUE};"
            f"border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:6px'>"
            f"<span style='color:{ACCENT_BLUE};font-size:0.68rem;font-weight:700;"
            f"letter-spacing:0.08em;text-transform:uppercase'>Long End (10s30s)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<span style='font-size:0.82rem;color:#9BAEC8'>{long_end_desc}</span>",
                    unsafe_allow_html=True)

    with ic3:
        st.markdown(
            f"<div style='background:rgba(8,18,32,0.60);border-left:3px solid {ACCENT_GOLD};"
            f"border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:6px'>"
            f"<span style='color:{ACCENT_GOLD};font-size:0.68rem;font-weight:700;"
            f"letter-spacing:0.08em;text-transform:uppercase'>Carry & Roll-Down</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<span style='font-size:0.82rem;color:#9BAEC8'>{carry_desc}</span>",
                    unsafe_allow_html=True)

    # Butterfly in its own row, smaller
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.50);border:1px solid #1A2E45;"
        f"border-radius:6px;padding:8px 14px;margin-top:6px'>"
        f"<span style='color:#5A6A82;font-size:0.68rem;font-weight:700;"
        f"letter-spacing:0.08em;text-transform:uppercase'>Butterfly </span>"
        f"<span style='font-size:0.82rem;color:#9BAEC8'>{bfly_desc}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Main render ────────────────────────────────────────────────────────────────

def render():
    st.markdown("## Yield Curve Builder")
    st.caption(
        "Bootstrap Spot · Forward · Par curves from T-Bills, T-Notes, T-Bonds "
        "| Z-Spread · ASW Spread on fixed-rate bonds"
    )

    # ── Sidebar-style settings ─────────────────────────────────────────────────
    col_cfg, col_main = st.columns([1, 2.5], gap="large")

    with col_cfg:
        st.markdown("#### Settings")
        interp = st.selectbox(
            "Interpolation",
            ["Cubic Spline", "Linear"],
            key="yc_interp",
            help="Method used to smooth the bootstrapped rates onto the fine grid.",
        )
        freq_par = st.selectbox(
            "Par coupon frequency",
            [2, 1, 4],
            format_func=lambda x: {1: "Annual", 2: "Semi-annual", 4: "Quarterly"}[x],
            key="yc_freq",
            help="Number of coupon payments per year used in par rate computation.",
        )
        show_fwd = st.toggle("Show Forward curve", value=True, key="yc_fwd")
        show_par = st.toggle("Show Par curve",     value=True, key="yc_par")

        st.markdown("---")
        st.markdown("#### Instrument Table")
        st.caption(
            "T-Bills: zero-coupon (rate = simple yield). "
            "T-Notes / T-Bonds: semi-annual coupon, price = dirty price."
        )

        if "yc_instruments" not in st.session_state:
            st.session_state["yc_instruments"] = _DEFAULT_INSTRUMENTS.copy()

        edited = st.data_editor(
            st.session_state["yc_instruments"],
            num_rows="dynamic",
            use_container_width=True,
            key="yc_table",
            column_config={
                "Type": st.column_config.SelectboxColumn(
                    "Type",
                    options=["T-Bill", "T-Note", "T-Bond"],
                    required=True,
                    width="small",
                ),
                "Maturity (y)": st.column_config.NumberColumn(
                    "Mat (y)", min_value=0.01, max_value=50.0,
                    step=0.25, format="%.3f",
                ),
                "Rate/Coupon (%)": st.column_config.NumberColumn(
                    "Rate/Cpn %", min_value=-2.0, max_value=20.0,
                    step=0.05, format="%.3f",
                ),
                "Price": st.column_config.NumberColumn(
                    "Price", min_value=50.0, max_value=150.0,
                    step=0.01, format="%.4f",
                ),
                "Include": st.column_config.CheckboxColumn("✓", width="small"),
            },
            hide_index=True,
        )
        st.session_state["yc_instruments"] = edited

        if st.button("Reset defaults", key="yc_reset", use_container_width=True):
            st.session_state["yc_instruments"] = _DEFAULT_INSTRUMENTS.copy()
            st.rerun()

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    with col_main:
        active = edited[edited["Include"] == True].copy()  # noqa: E712

        if len(active) < 2:
            st.warning("Select at least 2 instruments to bootstrap the curve.")
            return

        instruments = []
        for _, row in active.iterrows():
            instruments.append({
                "type":     row["Type"],
                "maturity": float(row["Maturity (y)"]),
                "rate":     float(row["Rate/Coupon (%)"]) / 100.0,
                "price":    float(row["Price"]),
                "freq":     2,
            })

        try:
            mats, spots = bootstrap_spot_rates(instruments)
        except Exception as exc:
            st.error(f"Bootstrapping error: {exc}")
            return

        # Fine grid for smooth display
        T_max  = mats.max()
        t_fine = np.linspace(mats.min(), T_max, 500)
        method = "cubic" if interp == "Cubic Spline" else "linear"

        spot_fine = interpolate_curve(mats, spots, t_fine, method=method)
        fwd_fine  = spot_to_forward(t_fine, spot_fine)
        par_fine  = spot_to_par(t_fine, spot_fine, freq=freq_par)

        spreads = key_spreads(mats, spots)

        # ── Key spread metrics ─────────────────────────────────────────────
        st.markdown("#### Curve Metrics")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("3M Spot",  f"{spreads['3M']:.2f}%")
        mc2.metric("2Y Spot",  f"{spreads['2Y']:.2f}%")
        mc3.metric("5Y Spot",  f"{spreads['5Y']:.2f}%")
        mc4.metric("10Y Spot", f"{spreads['10Y']:.2f}%")
        mc5.metric("30Y Spot", f"{spreads['30Y']:.2f}%")

        st.markdown("---")

        ms1, ms2, ms3, ms4, ms5 = st.columns(5)
        def _delta_metric(col, label, val, inverted=False):
            color = "normal" if not inverted else "inverse"
            col.metric(label, f"{val:+.1f} bps",
                       delta=f"{'inverted' if val < 0 else 'normal'}",
                       delta_color=color)

        ms1.metric("2s10s",            f"{spreads['2s10s']:+.1f} bps",
                   delta="inverted" if spreads['2s10s'] < 0 else "normal",
                   delta_color="inverse" if spreads['2s10s'] < 0 else "normal")
        ms2.metric("3M10Y",            f"{spreads['3M10Y']:+.1f} bps",
                   delta="inverted" if spreads['3M10Y'] < 0 else "normal",
                   delta_color="inverse" if spreads['3M10Y'] < 0 else "normal")
        ms3.metric("10s30s",           f"{spreads['10s30s']:+.1f} bps")
        ms4.metric("5s30s",            f"{spreads['5s30s']:+.1f} bps")
        ms5.metric("Butterfly 2-5-10", f"{spreads['butterfly_2_5_10']:+.1f} bps",
                   help="2Y + 10Y - 2×5Y. Positive = humped curve.")

        # ── Curve Interpretation ───────────────────────────────────────────
        _render_curve_interpretation(spreads)

        st.markdown("---")

        # ── Tabs: Curve | Bootstrapped Data | Bond Spreads ─────────────────
        tab_curve, tab_data, tab_spread = st.tabs([
            "Spot / Forward / Par Curve",
            "Bootstrapped Data",
            "Z-Spread & ASW",
        ])

        # ── Tab 1: Curve ──────────────────────────────────────────────────
        with tab_curve:
            fig = go.Figure()

            # Shading between spot and forward (carry region)
            fig.add_trace(go.Scatter(
                x=np.concatenate([t_fine, t_fine[::-1]]),
                y=np.concatenate([spot_fine, fwd_fine[::-1]]),
                fill="toself",
                fillcolor="rgba(0,229,255,0.04)",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))

            # Spot curve
            fig.add_trace(go.Scatter(
                x=t_fine, y=spot_fine * 100,
                mode="lines",
                name="Spot (zero) curve",
                line=dict(color=ACCENT_CYAN, width=2.5),
                hovertemplate="<b>Spot</b>  T=%{x:.2f}y<br>z = %{y:.3f}%<extra></extra>",
            ))

            # Bootstrapped knot points
            fig.add_trace(go.Scatter(
                x=mats, y=spots * 100,
                mode="markers",
                name="Bootstrapped knots",
                marker=dict(
                    color=ACCENT_CYAN, size=8, symbol="circle",
                    line=dict(color="#080C14", width=2),
                ),
                hovertemplate="<b>%{customdata}</b><br>T=%{x:.3f}y  z=%{y:.4f}%<extra></extra>",
                customdata=active["Type"].values,
            ))

            if show_fwd:
                fig.add_trace(go.Scatter(
                    x=t_fine, y=fwd_fine * 100,
                    mode="lines",
                    name="Forward curve",
                    line=dict(color=ACCENT_GOLD, width=2, dash="dash"),
                    hovertemplate="<b>Forward</b>  T=%{x:.2f}y<br>f = %{y:.3f}%<extra></extra>",
                ))

            if show_par:
                fig.add_trace(go.Scatter(
                    x=t_fine, y=par_fine * 100,
                    mode="lines",
                    name="Par curve",
                    line=dict(color=ACCENT_BLUE, width=2, dash="dot"),
                    hovertemplate="<b>Par</b>  T=%{x:.2f}y<br>par = %{y:.3f}%<extra></extra>",
                ))

            fig.update_layout(
                **PLOTLY_LAYOUT,
                title=dict(
                    text="Yield Curve — Spot · Forward · Par",
                    font=dict(size=14, color="#9BAEC8"),
                ),
                xaxis_title="Maturity (years)",
                yaxis_title="Rate (%)",
                height=460,
            )
            fig.update_xaxes(showgrid=False, ticksuffix="y")
            fig.update_yaxes(showgrid=True, gridcolor="#1A2E45", ticksuffix="%")
            fig.update_layout(legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1, bgcolor="rgba(0,0,0,0)",
                borderwidth=0, font=dict(size=10),
            ))
            st.plotly_chart(fig, use_container_width=True)

            # Formula reference
            with st.expander("Formulas — how each curve is built"):
                st.markdown(r"""
**Bootstrapping (spot / zero curve)**

T-Bills (zero-coupon):
$$z(T) = \left(\frac{100}{P}\right)^{1/T} - 1$$

T-Notes / T-Bonds (coupon-bearing) — solved iteratively for each maturity $T_n$:
$$P = \sum_{i=1}^{n-1} \frac{C/f \times 100}{(1+z_i)^{t_i}} + \frac{(C/f+1)\times 100}{(1+z_{T_n})^{T_n}}$$
$z_{T_n}$ is the only unknown; all earlier $z_i$ have already been bootstrapped.

---
**Forward rates** (period $t_{i-1} \to t_i$):
$$f(t_{i-1}, t_i) = \left[\frac{(1+z_i)^{t_i}}{(1+z_{i-1})^{t_{i-1}}}\right]^{1/(t_i - t_{i-1})} - 1$$

Forward > Spot ⟹ curve is upward-sloping (normal). Forward < Spot ⟹ inverted.

---
**Par rates** (fair coupon for a bond priced at par):
$$\text{par}(T) = \frac{1 - df(T)}{\sum_{i=1}^{n} df(t_i) \cdot \alpha}$$
where $df(t) = (1+z(t))^{-t}$ and $\alpha = 1/f$ is the year fraction per coupon.
                """)

        # ── Tab 2: Bootstrapped data table ────────────────────────────────
        with tab_data:
            # Show both bootstrapped knots and fine grid (every 0.5y)
            t_table = np.arange(0.25, T_max + 0.01, 0.25)
            t_table = t_table[t_table <= T_max]

            z_tab   = interpolate_curve(mats, spots, t_table, method=method)
            fwd_tab = spot_to_forward(t_table, z_tab)
            par_tab = spot_to_par(t_table, z_tab, freq=freq_par)

            df_display = pd.DataFrame({
                "Maturity (y)":   t_table,
                "Spot rate (%)":  z_tab   * 100,
                "Forward rate (%)": fwd_tab * 100,
                "Par rate (%)":   par_tab * 100,
                "Discount factor": (1.0 + z_tab) ** (-t_table),
            })

            st.dataframe(
                df_display.style.format({
                    "Maturity (y)":     "{:.2f}",
                    "Spot rate (%)":    "{:.4f}",
                    "Forward rate (%)": "{:.4f}",
                    "Par rate (%)":     "{:.4f}",
                    "Discount factor":  "{:.6f}",
                }),
                use_container_width=True,
                hide_index=True,
                height=420,
            )

            # Discount factor chart
            fig_df = go.Figure()
            fig_df.add_trace(go.Scatter(
                x=t_table,
                y=(1.0 + z_tab) ** (-t_table),
                mode="lines",
                line=dict(color=ACCENT_CYAN, width=2),
                fill="tozeroy",
                fillcolor="rgba(0,229,255,0.06)",
                name="df(T)",
                hovertemplate="T=%{x:.2f}y<br>df=%{y:.6f}<extra></extra>",
            ))
            fig_df.update_layout(
                **PLOTLY_LAYOUT,
                title="Discount Factor Curve  df(T) = (1 + z(T))^−T",
                xaxis_title="Maturity (years)",
                yaxis_title="Discount Factor",
                height=280,
            )
            fig_df.update_xaxes(showgrid=False)
            fig_df.update_yaxes(showgrid=True, gridcolor="#1A2E45")
            st.plotly_chart(fig_df, use_container_width=True)

        # ── Tab 3: Z-Spread & ASW ─────────────────────────────────────────
        with tab_spread:
            st.markdown("#### Bond Spread Analysis")
            st.caption(
                "Enter a bond's characteristics to compute its Z-spread and "
                "Asset Swap Spread relative to the bootstrapped curve."
            )

            _info_box(
                "Z-spread:   P = Σ CF_i / (1 + z_i + zs)^t_i",
                "Constant spread added to each spot rate so discounted cashflows = market price. "
                "Measures credit + liquidity premium over the risk-free curve.",
                ACCENT_CYAN,
            )
            _info_box(
                "ASW = (coupon − par_swap_rate) + (100 − P) / (100 × annuity)",
                "Par-par asset swap spread. Swap the fixed coupon for SOFR+s. "
                "annuity = Σ df(t_i)×α. par_swap_rate = (1−df_T)/annuity.",
                ACCENT_GOLD,
            )

            b1, b2 = st.columns(2)
            with b1:
                bond_coupon = st.number_input(
                    "Bond annual coupon rate",
                    value=0.0450, step=0.0025, format="%.4f",
                    key="yc_cpn",
                    help=(
                        "Annual coupon rate (decimal). "
                        "Semi-annual payments assumed: CF = coupon/2 × 100 every 6 months."
                    ),
                )
                bond_mat = st.number_input(
                    "Bond maturity (years)",
                    value=10.0, step=0.5, format="%.2f",
                    key="yc_bmat",
                    help="Years to maturity. Must be ≤ longest bootstrapped maturity.",
                )
                bond_freq = st.selectbox(
                    "Coupon frequency",
                    [2, 1, 4],
                    format_func=lambda x: {1: "Annual", 2: "Semi-annual", 4: "Quarterly"}[x],
                    key="yc_bfreq",
                    help="Number of coupon payments per year.",
                )

            with b2:
                bond_price = st.number_input(
                    "Market dirty price",
                    value=98.50, step=0.25, format="%.4f",
                    key="yc_bpx",
                    help=(
                        "Dirty (full) price per 100 face. "
                        "P = 100 → at par, P < 100 → discount, P > 100 → premium. "
                        "Bonds trading above par typically have negative Z-spread vs "
                        "a risk-free curve (or positive if credit-risky)."
                    ),
                )

                # Validate bond maturity within curve range
                if bond_mat > T_max:
                    st.warning(
                        f"Bond maturity ({bond_mat}y) exceeds the longest bootstrapped "
                        f"instrument ({T_max}y). Rates will be extrapolated flat."
                    )

            # ── Compute spreads ────────────────────────────────────────────
            try:
                zs  = calc_z_spread(
                    bond_price, bond_coupon, bond_mat,
                    mats, spots, freq=bond_freq,
                )
                asw = calc_asw_spread(
                    bond_price, bond_coupon, bond_mat,
                    mats, spots, freq=bond_freq,
                )

                zs_bps  = zs  * 10_000 if not np.isnan(zs)  else np.nan
                asw_bps = asw * 10_000 if not np.isnan(asw) else np.nan

                st.markdown("---")
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric(
                    "Z-Spread",
                    f"{zs_bps:.1f} bps" if not np.isnan(zs_bps) else "N/A",
                    help="Parallel shift of spot curve so PV(bond CFs) = market price.",
                )
                rc2.metric(
                    "ASW Spread",
                    f"{asw_bps:.1f} bps" if not np.isnan(asw_bps) else "N/A",
                    help="Par-par asset swap spread: fixed coupon swapped for SOFR+s.",
                )

                # Theoretical par rate at bond maturity
                par_at_mat = float(
                    interpolate_curve(mats, spots,
                                      np.array([bond_mat]), method=method)
                ) if bond_mat <= T_max else float(spots[-1])
                # Recompute par rate properly
                par_rates_bond = spot_to_par(
                    np.array([bond_mat]),
                    np.array([float(interpolate_curve(mats, spots, np.array([bond_mat]), method=method))]),
                    freq=bond_freq,
                )
                par_at_mat = float(par_rates_bond[0]) if len(par_rates_bond) else 0.0

                rc3.metric(
                    "Par rate at maturity",
                    f"{par_at_mat * 100:.3f}%",
                    help="Fair fixed coupon for a par-priced bond of the same maturity.",
                )
                rc4.metric(
                    "Z-Spread − ASW",
                    f"{(zs_bps - asw_bps):+.1f} bps" if not (np.isnan(zs_bps) or np.isnan(asw_bps)) else "N/A",
                    help=(
                        "Difference due to convexity and non-parallel curve shifts. "
                        "Typically small for near-par bonds."
                    ),
                )

            except Exception as exc:
                st.error(f"Spread calculation error: {exc}")
                return

            # ── PV sensitivity to Z-spread ─────────────────────────────
            st.markdown("---")
            st.markdown("#### PV vs Z-Spread sensitivity")

            zs_range = np.linspace(-0.01, 0.05, 300)  # -100 to +500 bps
            alpha_b   = 1.0 / bond_freq
            n_b       = int(round(bond_mat * bond_freq))
            cf_times_b = np.array([i * alpha_b for i in range(1, n_b + 1)])
            coupons_b  = np.full(n_b, bond_coupon / bond_freq * 100.0)
            coupons_b[-1] += 100.0
            z_interp_b = np.interp(cf_times_b, mats, spots)

            pv_curve = np.array([
                (coupons_b / (1.0 + z_interp_b + zs) ** cf_times_b).sum()
                for zs in zs_range
            ])

            fig_zs = go.Figure()
            # Area above/below market price
            fig_zs.add_trace(go.Scatter(
                x=zs_range * 10_000, y=pv_curve,
                mode="lines",
                line=dict(color=ACCENT_CYAN, width=2.5),
                fill="tozeroy",
                fillcolor="rgba(0,229,255,0.06)",
                name="PV(zs)",
                hovertemplate="zs=%{x:.1f} bps<br>PV=%{y:.4f}<extra></extra>",
            ))
            fig_zs.add_hline(
                y=bond_price,
                line_dash="dash", line_color=ACCENT_GOLD, line_width=1.5,
                annotation_text=f"Market price = {bond_price:.2f}",
                annotation_font_color=ACCENT_GOLD, annotation_font_size=10,
            )
            if not np.isnan(zs_bps):
                fig_zs.add_vline(
                    x=zs_bps,
                    line_dash="dot", line_color=ACCENT_RED, line_width=1.5,
                    annotation_text=f"Z-spread = {zs_bps:.1f} bps",
                    annotation_font_color=ACCENT_RED, annotation_font_size=10,
                )
            fig_zs.update_layout(
                **PLOTLY_LAYOUT,
                title="Bond PV as a function of Z-Spread",
                xaxis_title="Z-Spread (bps)",
                yaxis_title="Present Value",
                height=340,
            )
            fig_zs.update_xaxes(showgrid=False)
            fig_zs.update_yaxes(showgrid=True, gridcolor="#1A2E45")
            st.plotly_chart(fig_zs, use_container_width=True)

            # ── Spread formulas reference ──────────────────────────────
            with st.expander("Formulas — Z-spread & ASW in detail"):
                st.markdown(r"""
**Z-Spread**

The Z-spread $zs$ solves:
$$P = \sum_{i=1}^{n} \frac{CF_i}{\bigl(1 + z(t_i) + zs\bigr)^{t_i}}$$

where $z(t_i)$ is the bootstrapped spot rate at each cashflow date.
Z-spread is wider than the OAS (option-adjusted spread) for callable bonds.

---
**Par-Par Asset Swap Spread (ASW)**

In a par-par ASW the investor buys the bond at dirty price $P$ and enters a
swap that exchanges the fixed coupon $C$ for SOFR $+ s$.  The breakeven spread:

$$ASW = \underbrace{(C - r_{\text{par}})}_{\text{coupon excess}} + \underbrace{\frac{100 - P}{100 \times \text{annuity}}}_{\text{price adjustment}}$$

$$r_{\text{par}} = \frac{1 - df(T)}{\text{annuity}}, \qquad
\text{annuity} = \sum_{i=1}^{n} df(t_i) \cdot \alpha$$

- If $P = 100$ and $C = r_{\text{par}}$ ⟹ ASW = 0 (risk-free par bond).
- ASW > 0 signals credit / liquidity premium vs the curve.
- Z-spread ≈ ASW for near-par bonds; they diverge for distressed bonds.
                """)
