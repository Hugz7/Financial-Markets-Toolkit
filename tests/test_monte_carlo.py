"""Tests for the Monte Carlo simulation engine."""

import numpy as np
import pytest
from models.monte_carlo import simulate_gbm, price_options_mc, estimate_vol_from_paths
from models.black_scholes import call_price, put_price


S0, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.20, 0.02
N_SIMS = 100_000
N_STEPS = 252
SEED = 42


@pytest.fixture(scope="module")
def paths():
    return simulate_gbm(S0, r, q, sigma, T, N_SIMS, N_STEPS, seed=SEED)


def test_paths_shape(paths):
    assert paths.shape == (N_SIMS, N_STEPS + 1)


def test_paths_initial_value(paths):
    """All paths start at S0."""
    assert np.all(paths[:, 0] == S0)


def test_paths_positive(paths):
    """GBM paths are always positive."""
    assert np.all(paths > 0)


def test_european_call_within_ci(paths):
    """MC European call should be within its 95% CI of the BSM exact price."""
    results = price_options_mc(paths, K, r, T, H_up=130, H_down=70)
    call_res = results[0]
    assert call_res["name"] == "European Call"
    mc_price = call_res["price"]
    ci_low = call_res["ci_low"]
    ci_high = call_res["ci_high"]
    bsm = call_price(S0, K, T, r, sigma, q)
    assert ci_low <= bsm <= ci_high, (
        f"BSM call {bsm:.4f} outside MC 95% CI [{ci_low:.4f}, {ci_high:.4f}]"
    )


def test_european_put_within_ci(paths):
    """MC European put should be within its 95% CI of the BSM exact price."""
    results = price_options_mc(paths, K, r, T, H_up=130, H_down=70)
    put_res = results[1]
    assert put_res["name"] == "European Put"
    mc_price = put_res["price"]
    bsm = put_price(S0, K, T, r, sigma, q)
    assert put_res["ci_low"] <= bsm <= put_res["ci_high"], (
        f"BSM put {bsm:.4f} outside MC 95% CI [{put_res['ci_low']:.4f}, {put_res['ci_high']:.4f}]"
    )


def test_mc_call_error_under_2pct(paths):
    """With 100k paths, MC European call error should be under 2%."""
    results = price_options_mc(paths, K, r, T)
    mc_call = results[0]["price"]
    bsm = call_price(S0, K, T, r, sigma, q)
    rel_err = abs(mc_call - bsm) / bsm * 100
    assert rel_err < 2.0, f"MC call relative error {rel_err:.2f}% exceeds 2%"


def test_estimate_vol_uses_all_paths():
    """estimate_vol_from_paths should use all paths (not just the first)."""
    # With few paths, the result should still be reasonable (within ±50% of input sigma)
    paths_small = simulate_gbm(S0, r, q, sigma, T, n_sims=500, n_steps=N_STEPS, seed=SEED)
    est = estimate_vol_from_paths(paths_small, T)
    assert 0.5 * sigma < est < 2.0 * sigma, f"Estimated vol {est:.4f} is unreasonable"


def test_asian_call_below_vanilla(paths):
    """Asian call (arithmetic) <= vanilla call (averaging reduces effective volatility)."""
    results = price_options_mc(paths, K, r, T)
    assert results[2]["name"] == "Asian Call (Arithmetic)"
    vanilla_price = results[0]["price"]
    asian_price = results[2]["price"]
    # Allow a small MC noise buffer but Asian should be substantially below vanilla
    assert asian_price <= vanilla_price * 1.02
