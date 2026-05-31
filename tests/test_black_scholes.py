"""Tests for the Black-Scholes pricing engine."""

import numpy as np
import pytest
from models.black_scholes import call_price, put_price, implied_vol


# Reference parameters used across tests
S, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.02


def test_put_call_parity():
    """C - P = S·e^(-qT) - K·e^(-rT)"""
    C = call_price(S, K, T, r, sigma, q)
    P = put_price(S, K, T, r, sigma, q)
    lhs = C - P
    rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
    assert abs(lhs - rhs) < 1e-10, f"Put-call parity violated: {lhs:.8f} != {rhs:.8f}"


def test_put_call_parity_itm_otm():
    """Put-call parity holds for ITM and OTM options."""
    for K_test in [80.0, 100.0, 120.0]:
        C = call_price(S, K_test, T, r, sigma, q)
        P = put_price(S, K_test, T, r, sigma, q)
        rhs = S * np.exp(-q * T) - K_test * np.exp(-r * T)
        assert abs(C - P - rhs) < 1e-10


def test_call_price_known_value():
    """ATM BSM call should be approximately 9.15 for standard parameters (no dividend)."""
    C = call_price(100.0, 100.0, 1.0, 0.05, 0.20, 0.0)
    assert abs(C - 10.4506) < 0.01, f"BSM call = {C:.4f}, expected ≈ 10.45"


def test_call_nonnegative():
    """Call price is always >= 0."""
    for K_test in [50.0, 100.0, 150.0]:
        assert call_price(S, K_test, T, r, sigma, q) >= 0


def test_put_nonnegative():
    """Put price is always >= 0."""
    for K_test in [50.0, 100.0, 150.0]:
        assert put_price(S, K_test, T, r, sigma, q) >= 0


def test_call_at_expiry():
    """At expiry (T=0), call = max(S-K, 0)."""
    assert call_price(110.0, 100.0, 0.0, r, sigma, q) == pytest.approx(10.0)
    assert call_price(90.0, 100.0, 0.0, r, sigma, q) == pytest.approx(0.0)


def test_put_at_expiry():
    """At expiry (T=0), put = max(K-S, 0)."""
    assert put_price(90.0, 100.0, 0.0, r, sigma, q) == pytest.approx(10.0)
    assert put_price(110.0, 100.0, 0.0, r, sigma, q) == pytest.approx(0.0)


def test_implied_vol_roundtrip():
    """implied_vol(call_price(sigma)) should recover sigma."""
    for sigma_test in [0.10, 0.20, 0.35, 0.50]:
        price = call_price(S, K, T, r, sigma_test, q)
        iv = implied_vol(price, S, K, T, r, q, is_call=True)
        assert abs(iv - sigma_test) < 1e-5, f"IV roundtrip failed: got {iv:.5f}, expected {sigma_test}"


def test_implied_vol_put_roundtrip():
    """implied_vol(put_price(sigma)) should recover sigma for puts."""
    for sigma_test in [0.15, 0.25, 0.40]:
        price = put_price(S, K, T, r, sigma_test, q)
        iv = implied_vol(price, S, K, T, r, q, is_call=False)
        assert abs(iv - sigma_test) < 1e-5, f"IV put roundtrip failed: got {iv:.5f}, expected {sigma_test}"


def test_call_increases_with_spot():
    """Higher spot → higher call price."""
    prices = [call_price(s, K, T, r, sigma, q) for s in [80, 100, 120]]
    assert prices[0] < prices[1] < prices[2]


def test_put_decreases_with_spot():
    """Higher spot → lower put price."""
    prices = [put_price(s, K, T, r, sigma, q) for s in [80, 100, 120]]
    assert prices[0] > prices[1] > prices[2]
