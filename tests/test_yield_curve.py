"""Tests for curve conversions in models/yield_curve.py."""

import numpy as np

from models.yield_curve import spot_to_par


Z, F = 0.04, 2
FLAT_PAR = F * ((1 + Z) ** (1 / F) - 1)


def test_par_on_flat_curve_whole_periods_is_exact():
    """Flat annually-compounded spot z → par = f·((1+z)^(1/f) − 1) on coupon dates."""
    t = np.array([0.5, 1.0, 2.0, 10.0, 30.0])
    par = spot_to_par(t, np.full_like(t, Z), freq=F)
    assert np.allclose(par, FLAT_PAR, atol=1e-12)


def test_par_on_flat_curve_with_stub_stays_close():
    """With a short first period (simple accrual) par stays within a few bp."""
    t = np.array([0.1, 0.3, 0.75, 1.3, 4.6])
    par = spot_to_par(t, np.full_like(t, Z), freq=F)
    assert np.allclose(par, FLAT_PAR, atol=5e-4)


def test_par_is_smooth_on_fine_grid():
    """No zigzag: on a smooth upward curve, par rates change gradually."""
    t = np.linspace(0.05, 5, 200)
    spot = 0.03 + 0.01 * (1 - np.exp(-t))
    par = spot_to_par(t, spot, freq=2)
    assert np.all(np.isfinite(par))
    assert np.max(np.abs(np.diff(par))) < 5e-4
