"""
vol_smile_page.py — Implied Volatility Smile & Surface.
Fetches live option chains via yfinance and computes BSM IV from mid-prices.
"""

import datetime
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from scipy.interpolate import griddata

from config import (
    PLOTLY_LAYOUT, ACCENT_CYAN, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_RED, ACCENT_GOLD, TEXT_GREY,
)
from models.black_scholes import implied_vol, call_price, put_price


# ── IV helper ─────────────────────────────────────────────────────────────────

def _safe_iv(price: float, S: float, K: float, T: float,
             r: float, q: float, is_call: bool) -> float:
    """Newton-Raphson BSM IV with convergence validation. Returns NaN on failure."""
    if price <= 0 or T <= 0 or K <= 0 or S <= 0:
        return np.nan
    try:
        iv = implied_vol(price, S, K, T, r, q, is_call=is_call)
        check_fn = call_price if is_call else put_price
        computed = check_fn(S, K, T, r, iv, q)
        if abs(computed - price) / max(price, 1e-6) > 0.08:
            return np.nan
        return iv if 0.005 < iv < 5.0 else np.nan
    except Exception:
        return np.nan


# ── Cached fetchers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _fetch_expiries(sym: str):
    t = yf.Ticker(sym)
    S = float(t.fast_info.last_price)
    return S, list(t.options)


@st.cache_data(ttl=300)
def _fetch_smile(sym: str, expiry: str, S: float, r: float, q: float):
    """Fetch chain, compute BSM IV from mid-prices, return enriched DataFrames."""
    today = datetime.date.today()
    exp_date = datetime.date.fromisoformat(expiry)
    T = max((exp_date - today).days / 365.0, 1 / 365.0)

    chain = yf.Ticker(sym).option_chain(expiry)

    def _enrich(df: pd.DataFrame, is_call: bool) -> pd.DataFrame:
        df = df.copy()
        df["mid"] = np.where(
            (df["bid"] > 0) & (df["ask"] > 0),
            (df["bid"] + df["ask"]) / 2.0,
            df["lastPrice"],
        )
        df["iv_bsm"] = [
            _safe_iv(row["mid"], S, row["strike"], T, r, q, is_call)
            for _, row in df.iterrows()
        ]
        df["moneyness"]     = df["strike"] / S
        df["log_moneyness"] = np.log(df["strike"] / S)
        df["T"]             = T
        return df

    calls = _enrich(chain.calls, is_call=True)
    puts  = _enrich(chain.puts,  is_call=False)

    # Liquidity filter: at least some open interest or volume
    def _clean(df):
        df = df[(df["moneyness"] >= 0.55) & (df["moneyness"] <= 1.60)]
        df = df[df["iv_bsm"].notna()]
        df = df[df["iv_bsm"] < 3.0]
        has_oi  = df["openInterest"].fillna(0) > 0
        has_vol = df["volume"].fillna(0) > 0
        return df[has_oi | has_vol].sort_values("strike")

    return T, _clean(calls), _clean(puts)


# ── Colour ramp for multi-expiry curves ───────────────────────────────────────

def _expiry_colors(n: int) -> list[str]:
    """Cyan → blue → purple ramp."""
    palette = [
        "#00E5FF", "#38BDF8", "#818CF8", "#A78BFA",
        "#F472B6", "#F0B429", "#10D48A",
    ]
    return [palette[i % len(palette)] for i in range(n)]


# ── ATM IV helper ──────────────────────────────────────────────────────────────

def _atm_iv(calls: pd.DataFrame, puts: pd.DataFrame, S: float) -> float:
    """Return the average IV of the two strikes nearest to spot."""
    combined = pd.concat([calls, puts])
    combined["dist"] = (combined["strike"] - S).abs()
    near = combined.nsmallest(4, "dist")
    valid = near["iv_bsm"].dropna()
    return float(valid.mean()) if len(valid) else np.nan


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    st.markdown("## Volatility Smile & Surface")
    st.caption(
        "Live market implied volatility from real option chains · "
        "BSM IV computed from bid/ask midpoint"
    )

    # ── Inputs ─────────────────────────────────────────────────────────────────
    col_t, col_r, col_q, col_btn = st.columns([2, 1, 1, 1])
    with col_t:
        ticker = st.text_input("Ticker", value="SPY", key="vs_ticker",
                               label_visibility="visible").strip().upper()
    with col_r:
        r = st.number_input("Risk-Free r", value=0.045, step=0.005,
                            format="%.3f", key="vs_r")
    with col_q:
        q = st.number_input("Div. Yield q", value=0.015, step=0.005,
                            format="%.3f", key="vs_q")
    with col_btn:
        st.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
        load = st.button("Load Options", type="primary", key="vs_load",
                         use_container_width=True)

    # ── Fetch expiries ──────────────────────────────────────────────────────────
    if load or "vs_spot" in st.session_state:
        if load:
            st.cache_data.clear()  # force refresh on explicit load
        try:
            S, expiries = _fetch_expiries(ticker)
            st.session_state["vs_spot"]     = S
            st.session_state["vs_expiries"] = expiries
            st.session_state["vs_ticker_loaded"] = ticker
        except Exception as e:
            st.error(f"Could not fetch data for **{ticker}**: {e}")
            return

    if "vs_spot" not in st.session_state:
        st.info("Enter a ticker and click **Load Options** to fetch live market data.")
        return

    S        = st.session_state["vs_spot"]
    expiries = st.session_state["vs_expiries"]
    sym      = st.session_state["vs_ticker_loaded"]

    # ── Spot price banner ───────────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:rgba(8,18,32,0.65);border:1px solid rgba(0,229,255,0.15);"
        f"border-radius:8px;padding:8px 16px;display:inline-block;margin:4px 0 12px 0;"
        f"color:#9BAEC8;font-size:0.84rem'>"
        f"<b style='color:{ACCENT_CYAN}'>{sym}</b>  ·  "
        f"Spot: <b style='color:{ACCENT_CYAN}'>{S:,.2f}</b>  ·  "
        f"{len(expiries)} expiries available</div>",
        unsafe_allow_html=True,
    )

    # ── Expiry selector ─────────────────────────────────────────────────────────
    col_sel, col_x = st.columns([2, 1])
    with col_sel:
        # Single expiry for smile tab, multi for surface
        exp_single = st.selectbox("Expiry (Smile)", expiries, key="vs_exp_single")
    with col_x:
        x_axis = st.radio("X-axis", ["Strike K", "Moneyness K/S"],
                          horizontal=True, key="vs_xaxis")
    use_moneyness = x_axis == "Moneyness K/S"

    # ── Load selected expiry ────────────────────────────────────────────────────
    try:
        with st.spinner(f"Loading option chain for {exp_single}…"):
            T_sel, calls, puts = _fetch_smile(sym, exp_single, S, r, q)
    except Exception as e:
        st.error(f"Failed to load chain: {e}")
        return

    atm_iv = _atm_iv(calls, puts, S)

    # ── Metric cards ────────────────────────────────────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Spot S", f"{S:,.2f}")
    mc2.metric("ATM IV", f"{atm_iv*100:.1f}%" if np.isfinite(atm_iv) else "—")
    mc3.metric("T (years)", f"{T_sel:.3f}")
    mc4.metric("Strikes loaded",
               f"{len(calls)} C / {len(puts)} P")

    st.markdown("---")

    # ── Tabs ────────────────────────────────────────────────────────────────────
    tab_smile, tab_multi, tab_surface = st.tabs([
        "Smile", "Multi-Expiry", "Vol Surface",
    ])

    # ── Tab 1: Smile ────────────────────────────────────────────────────────────
    with tab_smile:
        x_calls = calls["moneyness"]  if use_moneyness else calls["strike"]
        x_puts  = puts["moneyness"]   if use_moneyness else puts["strike"]
        x_label = "Moneyness  K / S" if use_moneyness else "Strike K"
        x_atm   = 1.0 if use_moneyness else S

        fig = go.Figure()

        if len(calls):
            fig.add_trace(go.Scatter(
                x=x_calls, y=calls["iv_bsm"] * 100,
                mode="lines+markers",
                name="Calls IV",
                line=dict(color=ACCENT_CYAN, width=2.2),
                marker=dict(color=ACCENT_CYAN, size=5),
                hovertemplate=(
                    f"<b>Call</b><br>"
                    f"{'M' if use_moneyness else 'K'}: %{{x:.4f}}<br>"
                    f"IV: %{{y:.2f}}%<extra></extra>"
                ),
            ))

        if len(puts):
            fig.add_trace(go.Scatter(
                x=x_puts, y=puts["iv_bsm"] * 100,
                mode="lines+markers",
                name="Puts IV",
                line=dict(color=ACCENT_RED, width=2.2, dash="dash"),
                marker=dict(color=ACCENT_RED, size=5),
                hovertemplate=(
                    f"<b>Put</b><br>"
                    f"{'M' if use_moneyness else 'K'}: %{{x:.4f}}<br>"
                    f"IV: %{{y:.2f}}%<extra></extra>"
                ),
            ))

        # ATM marker
        if np.isfinite(atm_iv):
            fig.add_vline(
                x=x_atm, line_dash="dot", line_color=ACCENT_GOLD, line_width=1.2,
                annotation_text="ATM",
                annotation_font_color=ACCENT_GOLD, annotation_font_size=10,
            )
            fig.add_hline(
                y=atm_iv * 100, line_dash="dot", line_color=TEXT_GREY, line_width=1,
                annotation_text=f"ATM IV = {atm_iv*100:.1f}%",
                annotation_font_color=TEXT_GREY, annotation_font_size=10,
            )

        # Flat-vol BSM baseline (constant ATM IV for reference)
        if use_moneyness and np.isfinite(atm_iv):
            fig.add_trace(go.Scatter(
                x=[0.60, 1.60], y=[atm_iv * 100, atm_iv * 100],
                mode="lines",
                name="BSM flat (ATM IV)",
                line=dict(color=TEXT_GREY, width=1, dash="dot"),
                showlegend=True,
            ))

        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(
                text=f"{sym} · Vol Smile  — {exp_single}  (T = {T_sel:.3f}y)",
                font=dict(size=13, color="#9BAEC8"),
            ),
            xaxis_title=x_label,
            yaxis_title="Implied Volatility (%)",
            height=460,
        )
        fig.update_layout(legend=dict(x=0.01, y=0.99))
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#1A2E45",
                         zeroline=False, ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

        # ── Skew metrics ───────────────────────────────────────────────────────
        skew_vals = _skew_metrics(calls, puts, S, T_sel)
        if skew_vals:
            skew_cards = "".join(
                f"<div style='background:rgba(8,18,32,0.72);backdrop-filter:blur(14px);"
                f"-webkit-backdrop-filter:blur(14px);border:1px solid rgba(0,229,255,0.13);"
                f"border-radius:8px;padding:9px 13px;'>"
                f"<div style='color:#5A6A82;font-size:0.62rem;text-transform:uppercase;"
                f"letter-spacing:0.07em;font-weight:600;margin-bottom:2px'>{k}</div>"
                f"<div style='color:{c};font-size:1.05rem;font-weight:700;"
                f"font-variant-numeric:tabular-nums'>{v}</div></div>"
                for k, v, c in skew_vals
            )
            st.markdown(
                f"<div style='display:grid;grid-template-columns:repeat({len(skew_vals)},1fr);"
                f"gap:8px;margin-top:8px'>" + skew_cards + "</div>",
                unsafe_allow_html=True,
            )

        # ── Raw data table ─────────────────────────────────────────────────────
        with st.expander("Raw data table"):
            disp_cols = ["strike", "moneyness", "bid", "ask", "mid",
                         "iv_bsm", "volume", "openInterest"]
            c_disp = calls[[c for c in disp_cols if c in calls.columns]].copy()
            p_disp = puts[[c  for c in disp_cols if c in puts.columns]].copy()
            c_disp.insert(0, "type", "call")
            p_disp.insert(0, "type", "put")
            all_disp = pd.concat([c_disp, p_disp]).sort_values("strike")
            all_disp["iv_bsm"]    = (all_disp["iv_bsm"] * 100).round(2)
            all_disp["moneyness"] = all_disp["moneyness"].round(4)
            all_disp = all_disp.rename(columns={"iv_bsm": "IV BSM (%)",
                                                  "moneyness": "K/S"})
            st.dataframe(all_disp, use_container_width=True, hide_index=True)

    # ── Tab 2: Multi-Expiry ────────────────────────────────────────────────────
    with tab_multi:
        exp_multi = st.multiselect(
            "Select expiries (2–7)",
            options=expiries[:20],  # limit to nearest 20 to avoid overload
            default=expiries[:min(4, len(expiries))],
            key="vs_exp_multi",
        )
        if len(exp_multi) < 2:
            st.info("Select at least 2 expiries.")
        else:
            colors = _expiry_colors(len(exp_multi))
            fig_multi = go.Figure()

            for color, expiry in zip(colors, exp_multi):
                try:
                    with st.spinner(f"Loading {expiry}…"):
                        T_i, c_i, p_i = _fetch_smile(sym, expiry, S, r, q)
                except Exception:
                    continue

                # Use calls for OTM call side, puts for OTM put side
                otm_calls = c_i[c_i["moneyness"] >= 1.0]
                otm_puts  = p_i[p_i["moneyness"] <= 1.0]
                combined = pd.concat([otm_puts, otm_calls]).sort_values("moneyness")

                if combined.empty:
                    continue

                x = combined["moneyness"] if use_moneyness else combined["strike"]
                fig_multi.add_trace(go.Scatter(
                    x=x, y=combined["iv_bsm"] * 100,
                    mode="lines+markers",
                    name=f"{expiry}  (T={T_i:.2f}y)",
                    line=dict(color=color, width=2),
                    marker=dict(color=color, size=4),
                    hovertemplate=(
                        f"<b>{expiry}</b><br>"
                        f"{'M' if use_moneyness else 'K'}: %{{x:.4f}}<br>"
                        f"IV: %{{y:.2f}}%<extra></extra>"
                    ),
                ))

            fig_multi.add_vline(
                x=1.0 if use_moneyness else S,
                line_dash="dot", line_color=ACCENT_GOLD, line_width=1,
                annotation_text="ATM", annotation_font_color=ACCENT_GOLD,
                annotation_font_size=10,
            )
            fig_multi.update_layout(
                **PLOTLY_LAYOUT,
                title=dict(
                    text=f"{sym} · Vol Smile by Expiry  (OTM composite)",
                    font=dict(size=13, color="#9BAEC8"),
                ),
                xaxis_title="Moneyness  K / S" if use_moneyness else "Strike K",
                yaxis_title="Implied Volatility (%)",
                height=480,
            )
            fig_multi.update_layout(legend=dict(x=1.01, y=1.0, xanchor="left"))
            fig_multi.update_xaxes(showgrid=False)
            fig_multi.update_yaxes(showgrid=True, gridcolor="#1A2E45",
                                   zeroline=False, ticksuffix="%")
            st.plotly_chart(fig_multi, use_container_width=True)

            # ATM term-structure chart
            atm_term = []
            for expiry in exp_multi:
                try:
                    T_i, c_i, p_i = _fetch_smile(sym, expiry, S, r, q)
                    iv_atm = _atm_iv(c_i, p_i, S)
                    if np.isfinite(iv_atm):
                        atm_term.append((T_i, iv_atm * 100, expiry))
                except Exception:
                    pass

            if len(atm_term) >= 2:
                atm_term.sort()
                fig_ts = go.Figure()
                fig_ts.add_trace(go.Scatter(
                    x=[t for t, _, _ in atm_term],
                    y=[v for _, v, _ in atm_term],
                    mode="lines+markers",
                    line=dict(color=ACCENT_CYAN, width=2.5),
                    marker=dict(color=ACCENT_CYAN, size=8,
                                line=dict(color="#080C14", width=2)),
                    text=[e for _, _, e in atm_term],
                    hovertemplate=(
                        "<b>Expiry</b>: %{text}<br>"
                        "T: %{x:.3f}y<br>ATM IV: %{y:.2f}%<extra></extra>"
                    ),
                    name="ATM IV",
                ))
                fig_ts.update_layout(
                    **PLOTLY_LAYOUT,
                    title=dict(text=f"{sym} · ATM Vol Term Structure",
                               font=dict(size=13, color="#9BAEC8")),
                    xaxis_title="Maturity T (years)",
                    yaxis_title="ATM Implied Vol (%)",
                    height=300,
                )
                fig_ts.update_xaxes(showgrid=False)
                fig_ts.update_yaxes(showgrid=True, gridcolor="#1A2E45",
                                    zeroline=False, ticksuffix="%")
                st.plotly_chart(fig_ts, use_container_width=True)

    # ── Tab 3: Vol Surface ─────────────────────────────────────────────────────
    with tab_surface:
        exp_surf = st.multiselect(
            "Select expiries for surface (3–8)",
            options=expiries[:20],
            default=expiries[:min(6, len(expiries))],
            key="vs_exp_surf",
        )
        if len(exp_surf) < 3:
            st.info("Select at least 3 expiries.")
        else:
            # Gather scatter points (T, moneyness, IV)
            pts = []
            for expiry in exp_surf:
                try:
                    T_i, c_i, p_i = _fetch_smile(sym, expiry, S, r, q)
                    otm_calls = c_i[c_i["moneyness"] >= 1.0]
                    otm_puts  = p_i[p_i["moneyness"] <= 1.0]
                    comp = pd.concat([otm_puts, otm_calls])
                    for _, row in comp.iterrows():
                        pts.append((T_i, row["moneyness"], row["iv_bsm"] * 100))
                except Exception:
                    pass

            if len(pts) < 10:
                st.warning("Not enough data points for a surface.")
            else:
                pts_arr = np.array(pts)
                T_pts  = pts_arr[:, 0]
                M_pts  = pts_arr[:, 1]
                IV_pts = pts_arr[:, 2]

                # Create regular grid and interpolate
                T_grid  = np.linspace(T_pts.min(), T_pts.max(), 30)
                M_grid  = np.linspace(M_pts.min(), M_pts.max(), 50)
                TT, MM  = np.meshgrid(T_grid, M_grid)
                IV_grid = griddata(
                    (T_pts, M_pts), IV_pts,
                    (TT, MM), method="linear",
                )

                fig_surf = go.Figure(data=[go.Surface(
                    x=T_grid, y=M_grid, z=IV_grid,
                    colorscale=[
                        [0.0, "#FF4D6D"],
                        [0.3, "#F0B429"],
                        [0.6, "#00E5FF"],
                        [1.0, "#A78BFA"],
                    ],
                    opacity=0.88,
                    colorbar=dict(
                        title=dict(text="IV (%)", font=dict(color="#9BAEC8", size=11)),
                        tickfont=dict(color="#9BAEC8", size=10),
                        thickness=14, len=0.7,
                    ),
                    hovertemplate=(
                        "T: %{x:.3f}y<br>K/S: %{y:.3f}<br>IV: %{z:.1f}%<extra></extra>"
                    ),
                )])

                # Mark ATM ridge
                atm_ivs = []
                for T_i in T_grid:
                    # Interpolate IV at ATM (moneyness=1) for each T
                    nearby = pts_arr[np.abs(pts_arr[:, 0] - T_i) < 0.05]
                    if len(nearby):
                        nearest_idx = np.argmin(np.abs(nearby[:, 1] - 1.0))
                        atm_ivs.append(nearby[nearest_idx, 2])
                    else:
                        atm_ivs.append(np.nan)

                fig_surf.add_trace(go.Scatter3d(
                    x=T_grid,
                    y=np.ones(len(T_grid)),
                    z=np.array(atm_ivs),
                    mode="lines",
                    line=dict(color=ACCENT_GOLD, width=4),
                    name="ATM",
                    hovertemplate="ATM<br>T: %{x:.3f}y<br>IV: %{z:.1f}%<extra></extra>",
                ))

                fig_surf.update_layout(
                    scene=dict(
                        xaxis=dict(title="Maturity (years)",
                                   backgroundcolor="#080C14",
                                   gridcolor="#1A2E45",
                                   showbackground=True,
                                   tickfont=dict(color="#9BAEC8", size=10)),
                        yaxis=dict(title="Moneyness K/S",
                                   backgroundcolor="#080C14",
                                   gridcolor="#1A2E45",
                                   showbackground=True,
                                   tickfont=dict(color="#9BAEC8", size=10)),
                        zaxis=dict(title="IV (%)",
                                   backgroundcolor="#080C14",
                                   gridcolor="#1A2E45",
                                   showbackground=True,
                                   tickfont=dict(color="#9BAEC8", size=10),
                                   ticksuffix="%"),
                        bgcolor="#080C14",
                        camera=dict(eye=dict(x=1.8, y=-1.8, z=1.2)),
                    ),
                    paper_bgcolor="#080C14",
                    plot_bgcolor="#080C14",
                    font=dict(color="#9BAEC8", family="Inter, sans-serif"),
                    title=dict(
                        text=f"{sym} · Implied Volatility Surface",
                        font=dict(size=13, color="#9BAEC8"),
                    ),
                    height=580,
                    margin=dict(l=0, r=0, t=50, b=0),
                    legend=dict(font=dict(color="#9BAEC8")),
                )
                st.plotly_chart(fig_surf, use_container_width=True)
                st.caption(
                    "Surface interpolated from market mid-prices · "
                    "Gold line = ATM ridge · Data may have gaps in illiquid strikes"
                )


# ── Skew metrics helper ────────────────────────────────────────────────────────

def _skew_metrics(calls: pd.DataFrame, puts: pd.DataFrame,
                  S: float, T: float) -> list[tuple]:
    """Return (label, value_str, color) tuples for key skew metrics."""
    out = []

    # ATM IV
    atm_iv = _atm_iv(calls, puts, S)
    if np.isfinite(atm_iv):
        out.append(("ATM IV", f"{atm_iv*100:.2f}%", ACCENT_CYAN))

    # 90 / 110 moneyness IV (nearest strike)
    def _nearest_iv(df, target_m):
        if df.empty:
            return np.nan
        df = df.copy()
        df["_dist"] = (df["moneyness"] - target_m).abs()
        row = df.nsmallest(1, "_dist")
        return float(row["iv_bsm"].iloc[0]) if not row.empty else np.nan

    iv_90 = _nearest_iv(puts,  0.90)
    iv_110 = _nearest_iv(calls, 1.10)

    if np.isfinite(iv_90):
        out.append(("90% Put IV", f"{iv_90*100:.2f}%", ACCENT_RED))
    if np.isfinite(iv_110):
        out.append(("110% Call IV", f"{iv_110*100:.2f}%", ACCENT_GREEN))

    # Skew = IV(90%) − IV(110%)
    if np.isfinite(iv_90) and np.isfinite(iv_110):
        skew = (iv_90 - iv_110) * 100
        col = ACCENT_RED if skew > 0 else ACCENT_CYAN
        out.append(("Skew  90%P − 110%C", f"{skew:+.2f}%", col))

    # Smile curvature = (IV90 + IV110)/2 − ATM
    if np.isfinite(iv_90) and np.isfinite(iv_110) and np.isfinite(atm_iv):
        curv = ((iv_90 + iv_110) / 2 - atm_iv) * 100
        out.append(("Curvature  (wings − ATM)", f"{curv:+.2f}%",
                    ACCENT_GOLD if curv > 0 else TEXT_GREY))

    return out
