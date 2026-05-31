"""Tests for the interest rate swap pricing engine."""

import numpy as np
import pytest
from models.swaps import generate_swap_schedule, swap_metrics


def make_schedule(swap_type="IRS Pay Fixed", fixed_rate=0.03, float_rate=0.025,
                  float_spread=0.001, tenor=5, freq=2, discount_rate=0.028,
                  foreign_float=0.020, fx_spot=1.08, foreign_notional=None):
    return generate_swap_schedule(
        notional=1_000_000,
        fixed_rate=fixed_rate,
        float_rate=float_rate,
        float_spread=float_spread,
        tenor=tenor,
        freq=freq,
        discount_rate=discount_rate,
        day_count="30/360",
        swap_type=swap_type,
        fx_spot=fx_spot,
        foreign_notional=foreign_notional,
        foreign_float=foreign_float,
    )


def make_metrics(df, swap_type="IRS Pay Fixed", fixed_rate=0.03, float_rate=0.025,
                 float_spread=0.001, discount_rate=0.028, freq=2):
    return swap_metrics(df, 1_000_000, fixed_rate, float_rate, float_spread, discount_rate, freq)


# ── Schedule correctness ──────────────────────────────────────────────────────

def test_schedule_row_count():
    df = make_schedule(tenor=5, freq=2)
    assert len(df) == 10  # 5 years × 2 per year


def test_schedule_columns():
    df = make_schedule()
    expected = {"period", "date", "year_frac", "fixed_cf", "float_cf",
                "net_pay_fixed", "net_rec_fixed", "disc_factor", "pv_fixed",
                "pv_float", "pv_net", "cumul_npv"}
    assert expected.issubset(set(df.columns))


def test_net_cf_symmetry():
    """net_pay_fixed = -net_rec_fixed for all rows."""
    df = make_schedule()
    diff = (df["net_pay_fixed"] + df["net_rec_fixed"]).abs()
    assert diff.max() < 1e-6


def test_pv_net_equals_pv_float_minus_pv_fixed():
    """pv_net = pv_float - pv_fixed for each row (within rounding to 2 d.p.)."""
    df = make_schedule()
    residual = (df["pv_net"] - (df["pv_float"] - df["pv_fixed"])).abs()
    assert residual.max() < 0.02  # values stored rounded to 2 decimal places


# ── DV01 correctness ──────────────────────────────────────────────────────────

def test_dv01_positive():
    """DV01 must be positive (a 1bp rise always increases PV of float leg)."""
    df = make_schedule()
    m = make_metrics(df)
    assert m["dv01"] > 0


def test_dv01_matches_finite_difference():
    """DV01 should match a 1bp finite-difference bump of the float rate."""
    notional = 1_000_000
    float_rate = 0.025
    float_spread = 0.001
    fixed_rate = 0.03
    discount_rate = 0.028
    freq = 2
    tenor = 5

    df0 = make_schedule(float_rate=float_rate)
    df1 = make_schedule(float_rate=float_rate + 0.0001)  # +1bp

    m0 = make_metrics(df0)
    m1 = make_metrics(df1, float_rate=float_rate + 0.0001)

    npv_bump = m1["npv_pay_fixed"] - m0["npv_pay_fixed"]
    dv01_fd = abs(npv_bump)

    assert abs(m0["dv01"] - dv01_fd) / dv01_fd < 0.01, (
        f"DV01 mismatch: formula={m0['dv01']:.2f}, finite-diff={dv01_fd:.2f}"
    )


def test_dv01_scales_with_notional():
    """DV01 is proportional to notional."""
    df1 = generate_swap_schedule(1_000_000, 0.03, 0.025, 0.001, 5, 2, 0.028)
    df2 = generate_swap_schedule(2_000_000, 0.03, 0.025, 0.001, 5, 2, 0.028)
    m1 = swap_metrics(df1, 1_000_000, 0.03, 0.025, 0.001, 0.028, 2)
    m2 = swap_metrics(df2, 2_000_000, 0.03, 0.025, 0.001, 0.028, 2)
    assert abs(m2["dv01"] / m1["dv01"] - 2.0) < 0.01


# ── Break-even rate ───────────────────────────────────────────────────────────

def test_breakeven_rate_makes_npv_zero():
    """Setting fixed_rate = break-even rate should produce NPV ≈ 0."""
    df = make_schedule()
    m = make_metrics(df)
    be = m["breakeven_rate"]

    df_be = make_schedule(fixed_rate=be)
    m_be = make_metrics(df_be, fixed_rate=be)
    assert abs(m_be["npv_pay_fixed"]) < 1.0, (
        f"NPV at break-even = {m_be['npv_pay_fixed']:.2f}, expected ≈ 0"
    )


# ── Swap type differentiation ─────────────────────────────────────────────────

def test_basis_swap_differs_from_irs():
    """Basis Swap cashflows differ from IRS Pay Fixed cashflows."""
    df_irs = make_schedule(swap_type="IRS Pay Fixed")
    df_basis = make_schedule(swap_type="Basis Swap")
    # In IRS, fixed_cf = N * fixed_rate * yf; in Basis, fixed_cf = N * float_rate * yf
    # These are different when fixed_rate != float_rate
    assert not df_irs["fixed_cf"].equals(df_basis["fixed_cf"])


def test_xccy_swap_differs_from_irs():
    """XCCY Swap cashflows differ from IRS cashflows."""
    df_irs = make_schedule(swap_type="IRS Pay Fixed")
    df_xccy = make_schedule(swap_type="XCCY Swap", foreign_float=0.015)
    m_irs = make_metrics(df_irs)
    m_xccy = make_metrics(df_xccy)
    # NPVs should differ because the float leg is different
    assert abs(m_irs["npv_pay_fixed"] - m_xccy["npv_pay_fixed"]) > 1.0


def test_irs_pay_receive_are_symmetric():
    """For any IRS schedule, NPV(pay) + NPV(receive) = 0 (same cashflows, opposite perspectives)."""
    df = make_schedule(swap_type="IRS Pay Fixed")
    m = make_metrics(df)
    # npv_rec_fixed is defined as -(npv_pay_fixed); verify the implementation is consistent
    assert abs(m["npv_pay_fixed"] + m["npv_rec_fixed"]) < 1e-6


def test_xccy_final_period_includes_notional():
    """XCCY Swap last period cashflows include notional re-exchange."""
    notional = 1_000_000
    fx_spot = 1.08
    foreign_notional = int(notional * fx_spot)
    foreign_notional_dom = foreign_notional / fx_spot

    df = make_schedule(swap_type="XCCY Swap", tenor=3, freq=1,
                       fx_spot=fx_spot, foreign_notional=foreign_notional)

    last_row = df.iloc[-1]
    # fixed_cf in last period = coupon + foreign_notional_dom
    coupon_fixed = notional * 0.03 * (1.0 / 1)  # tenor=3, freq=1 → year_frac=1
    assert last_row["fixed_cf"] > coupon_fixed + 1, "Final period should include notional re-exchange"
