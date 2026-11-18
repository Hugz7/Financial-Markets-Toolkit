"""Sanity tests for the multi-leg payoff engine."""

import numpy as np
import pytest

from models.payoffs import INSTRUMENTS, STRATEGY_PRESETS, compute_leg_payoff

S = np.linspace(50, 150, 101)


def test_long_call_payoff():
    p = compute_leg_payoff(S, "Call", "Long", 100, 0, 1)
    assert np.allclose(p, np.maximum(S - 100, 0))


def test_short_put_is_negated_long_put():
    long_p = compute_leg_payoff(S, "Put", "Long", 100, 0, 2)
    short_p = compute_leg_payoff(S, "Put", "Short", 100, 0, 2)
    assert np.allclose(long_p + short_p, 0)
    assert np.allclose(long_p, 2 * np.maximum(100 - S, 0))


def test_call_minus_put_equals_forward():
    """Put-call parity at maturity: C − P = S − K."""
    c = compute_leg_payoff(S, "Call", "Long", 100, 0, 1)
    p = compute_leg_payoff(S, "Put", "Short", 100, 0, 1)
    fwd = compute_leg_payoff(S, "Forward", "Long", 100, 0, 1)
    assert np.allclose(c + p, fwd)


@pytest.mark.parametrize("inst", INSTRUMENTS)
def test_zero_qty_or_none_is_flat_zero(inst):
    assert np.allclose(compute_leg_payoff(S, inst, "Long", 100, 110, 0), 0)
    assert np.allclose(compute_leg_payoff(S, "None", "Long", 100, 110, 1), 0)


def test_straddle_equals_call_plus_put():
    straddle = compute_leg_payoff(S, "Straddle", "Long", 100, 0, 1)
    c = compute_leg_payoff(S, "Call", "Long", 100, 0, 1)
    p = compute_leg_payoff(S, "Put", "Long", 100, 0, 1)
    assert np.allclose(straddle, c + p)


def test_presets_use_known_instruments():
    for legs in STRATEGY_PRESETS.values():
        for inst, direction, *_ in legs.values():
            assert inst in INSTRUMENTS
            assert direction in ("Long", "Short")
