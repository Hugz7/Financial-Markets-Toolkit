"""Tests for exotic option pricing models."""

import numpy as np
import pytest
from models.exotic_options import (
    one_touch_up, no_touch_up,
    one_touch_down, no_touch_down,
    double_no_touch,
    asian_geometric_call,
    range_accrual,
    gap_call,
    chooser_option,
)
from models.black_scholes import call_price


S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
H_up, H_down = 120.0, 80.0


def test_touch_no_touch_sum_up():
    """OT_up + NT_up = e^(-rT) for any parameters."""
    erT = np.exp(-r * T)
    ot = one_touch_up(S, H_up, T, r, sigma)
    nt = no_touch_up(S, H_up, T, r, sigma)
    assert abs(ot + nt - erT) < 1e-12


def test_touch_no_touch_sum_down():
    """OT_down + NT_down = e^(-rT) for any parameters."""
    erT = np.exp(-r * T)
    ot = one_touch_down(S, H_down, T, r, sigma)
    nt = no_touch_down(S, H_down, T, r, sigma)
    assert abs(ot + nt - erT) < 1e-12


def test_touch_no_touch_sum_various_params():
    """Touch/no-touch identity holds across parameter ranges."""
    for h in [110.0, 130.0, 150.0]:
        erT = np.exp(-r * T)
        assert abs(one_touch_up(S, h, T, r, sigma) + no_touch_up(S, h, T, r, sigma) - erT) < 1e-12
    for l in [90.0, 70.0, 50.0]:
        erT = np.exp(-r * T)
        assert abs(one_touch_down(S, l, T, r, sigma) + no_touch_down(S, l, T, r, sigma) - erT) < 1e-12


def test_one_touch_up_already_touched():
    """If S >= H, OT_up = e^(-rT)."""
    erT = np.exp(-r * T)
    ot = one_touch_up(200.0, 100.0, T, r, sigma)
    assert abs(ot - erT) < 1e-12


def test_one_touch_down_already_touched():
    """If S <= L, OT_down = e^(-rT)."""
    erT = np.exp(-r * T)
    ot = one_touch_down(50.0, 100.0, T, r, sigma)
    assert abs(ot - erT) < 1e-12


def test_double_no_touch_bounded():
    """Double no-touch price is in [0, e^(-rT)]."""
    erT = np.exp(-r * T)
    dnt = double_no_touch(S, H_down, H_up, T, r, sigma)
    assert 0 <= dnt <= erT + 1e-12


def test_double_no_touch_decreases_with_wider_barriers():
    """Wider barriers → higher DNT probability (more room to stay inside)."""
    dnt_narrow = double_no_touch(S, 95.0, 105.0, T, r, sigma)
    dnt_wide = double_no_touch(S, 70.0, 130.0, T, r, sigma)
    assert dnt_narrow < dnt_wide


def test_range_accrual_bounded():
    """Range accrual probability is in [0, e^(-rT)]."""
    erT = np.exp(-r * T)
    ra = range_accrual(S, H_down, H_up, T, r, sigma)
    assert 0 <= ra <= erT + 1e-12


def test_range_accrual_at_expiry():
    """At T=0, range accrual = e^(-rT) if S in range, else 0."""
    # S=100 is in (80, 120)
    assert range_accrual(100.0, 80.0, 120.0, 0.0, r, sigma) == pytest.approx(1.0)
    # S=70 is outside (80, 120)
    assert range_accrual(70.0, 80.0, 120.0, 0.0, r, sigma) == pytest.approx(0.0)


def test_gap_call_equals_call_when_same_strike():
    """Gap call with K_gap == K equals a standard BSM call."""
    gc = gap_call(S, K, T, r, sigma, q=0.0, K_gap=K)
    c = call_price(S, K, T, r, sigma, q=0.0)
    assert abs(gc - c) < 1e-10


def test_asian_geometric_call_below_vanilla():
    """Asian geometric call <= vanilla call (averaging reduces volatility)."""
    agc_price = asian_geometric_call(S, K, T, r, sigma)
    vanilla = call_price(S, K, T, r, sigma)
    assert agc_price <= vanilla + 1e-10


def test_chooser_option_above_vanilla_call():
    """Chooser option price >= vanilla call (holder has more rights)."""
    chooser = chooser_option(S, K, T, r, sigma, q=0.0, t_c=0.5)
    vanilla = call_price(S, K, T, r, sigma, q=0.0)
    assert chooser >= vanilla - 1e-10
