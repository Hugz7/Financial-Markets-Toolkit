"""
models/payoffs.py — Payoff-at-maturity engine for multi-leg strategies.

Pure NumPy: no Streamlit, no I/O. Used by the Payoff Analyzer view.
"""

import numpy as np

# ── Available Instruments ──────────────────────────────────────
INSTRUMENTS = [
    "None", "Call", "Put", "Forward",
    "Digital Call", "Digital Put",
    "Barrier KI Call", "Barrier KI Put",
    "Barrier KO Call", "Barrier KO Put",
    "One-Touch Up", "No-Touch Up",
    "One-Touch Down", "No-Touch Down",
    "Gap Call", "Range Accrual",
    "Autocall Coupon", "Bond",
    "Reverse Convertible", "Straddle",
]

DIRECTIONS = ["Long", "Short"]

# ── Strategy Presets ───────────────────────────────────────────
NO_PRESET = "── Select a preset ──"

# Each preset: dict of leg_index -> (instrument, direction, K, barrier, T, premium, qty)
STRATEGY_PRESETS = {
    NO_PRESET: {},
    "Bull Call Spread": {
        0: ("Call", "Long", 100, 0, 1, 3.0, 1),
        1: ("Call", "Short", 110, 0, 1, 1.5, 1),
    },
    "Bear Put Spread": {
        0: ("Put", "Long", 100, 0, 1, 3.5, 1),
        1: ("Put", "Short", 90, 0, 1, 1.5, 1),
    },
    "Long Straddle": {
        0: ("Call", "Long", 100, 0, 1, 5.0, 1),
        1: ("Put", "Long", 100, 0, 1, 5.0, 1),
    },
    "Long Strangle": {
        0: ("Call", "Long", 110, 0, 1, 2.0, 1),
        1: ("Put", "Long", 90, 0, 1, 2.0, 1),
    },
    "Butterfly (Call)": {
        0: ("Call", "Long", 90, 0, 1, 7.0, 1),
        1: ("Call", "Short", 100, 0, 1, 4.0, 2),
        2: ("Call", "Long", 110, 0, 1, 2.0, 1),
    },
    "Iron Condor": {
        0: ("Put", "Long", 80, 0, 1, 0.5, 1),
        1: ("Put", "Short", 90, 0, 1, 2.0, 1),
        2: ("Call", "Short", 110, 0, 1, 2.0, 1),
        3: ("Call", "Long", 120, 0, 1, 0.5, 1),
    },
    "Collar": {
        0: ("Forward", "Long", 100, 0, 1, 0, 1),
        1: ("Put", "Long", 90, 0, 1, 2.0, 1),
        2: ("Call", "Short", 110, 0, 1, 2.0, 1),
    },
    "Risk Reversal": {
        0: ("Call", "Long", 110, 0, 1, 2.0, 1),
        1: ("Put", "Short", 90, 0, 1, 2.0, 1),
    },
    "Protective Put": {
        0: ("Forward", "Long", 100, 0, 1, 0, 1),
        1: ("Put", "Long", 95, 0, 1, 3.0, 1),
    },
    "Covered Call": {
        0: ("Forward", "Long", 100, 0, 1, 0, 1),
        1: ("Call", "Short", 110, 0, 1, 3.0, 1),
    },
    "Call Ratio Spread 1×2": {
        0: ("Call", "Long", 100, 0, 1, 5.0, 1),
        1: ("Call", "Short", 110, 0, 1, 2.5, 2),
    },
    "Jade Lizard": {
        0: ("Put", "Short", 90, 0, 1, 2.0, 1),
        1: ("Call", "Short", 110, 0, 1, 2.0, 1),
        2: ("Call", "Long", 120, 0, 1, 0.5, 1),
    },
    "Digital Bet (Up)": {
        0: ("Digital Call", "Long", 105, 10, 1, 4.0, 1),
    },
    "Knock-In Call": {
        0: ("Barrier KI Call", "Long", 100, 110, 1, 3.0, 1),
    },
}


def compute_leg_payoff(S_arr, instrument, direction, K, barrier, qty):
    """Compute payoff array for a single leg across spot prices."""
    if qty == 0 or instrument == "None":
        return np.zeros_like(S_arr)

    sign = 1 if direction == "Long" else -1

    if instrument == "Call":
        payoff = np.maximum(S_arr - K, 0)
    elif instrument == "Put":
        payoff = np.maximum(K - S_arr, 0)
    elif instrument == "Forward":
        payoff = S_arr - K
    elif instrument == "Digital Call":
        payoff = np.where(S_arr > K, barrier, 0.0)
    elif instrument == "Digital Put":
        payoff = np.where(S_arr < K, barrier, 0.0)
    elif instrument == "Barrier KI Call":
        payoff = np.where(S_arr > barrier, np.maximum(S_arr - K, 0), 0.0)
    elif instrument == "Barrier KI Put":
        payoff = np.where(S_arr < barrier, np.maximum(K - S_arr, 0), 0.0)
    elif instrument == "Barrier KO Call":
        payoff = np.where(S_arr < barrier, np.maximum(S_arr - K, 0), 0.0)
    elif instrument == "Barrier KO Put":
        payoff = np.where(S_arr > barrier, np.maximum(K - S_arr, 0), 0.0)
    elif instrument == "One-Touch Up":
        payoff = np.where(S_arr > barrier, 1.0, 0.0)
    elif instrument == "No-Touch Up":
        payoff = np.where(S_arr < barrier, 1.0, 0.0)
    elif instrument == "One-Touch Down":
        payoff = np.where(S_arr < barrier, 1.0, 0.0)
    elif instrument == "No-Touch Down":
        payoff = np.where(S_arr > barrier, 1.0, 0.0)
    elif instrument == "Gap Call":
        payoff = np.where(S_arr > barrier, S_arr - K, 0.0)
    elif instrument == "Range Accrual":
        payoff = np.where((S_arr > K) & (S_arr < barrier), 1.0, 0.0)
    elif instrument == "Autocall Coupon":
        payoff = np.where(S_arr >= K, barrier / 100.0, 0.0)
    elif instrument == "Bond":
        # Zero-coupon bond: pays face value K at maturity, flat payoff
        payoff = K * np.ones_like(S_arr)
    elif instrument == "Reverse Convertible":
        payoff = np.where(S_arr >= K, barrier, np.minimum(S_arr, K))
    elif instrument == "Straddle":
        payoff = np.abs(S_arr - K)
    else:
        payoff = np.zeros_like(S_arr)

    return sign * qty * payoff
