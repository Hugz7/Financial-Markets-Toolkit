"""
monte_carlo.py — GBM Monte Carlo simulation engine.
Log-Euler scheme: S(t+dt) = S(t) * exp[(r-q-σ²/2)dt + σ√dt·Z]
"""

import numpy as np
from scipy.stats import norm, skew, kurtosis
from models.black_scholes import call_price, put_price


def simulate_gbm(S0, r, q, sigma, T, n_sims, n_steps, seed=42):
    """
    Generate GBM paths using log-Euler scheme.
    Returns array of shape (n_sims, n_steps+1) including S0.
    """
    rng = np.random.RandomState(seed)
    dt = T / n_steps
    Z = rng.randn(n_sims, n_steps)
    drift = (r - q - sigma**2 / 2) * dt
    diffusion = sigma * np.sqrt(dt)
    log_returns = drift + diffusion * Z
    log_S = np.log(S0) + np.cumsum(log_returns, axis=1)
    S_paths = np.exp(log_S)
    return np.column_stack([np.full(n_sims, S0), S_paths])


def price_options_mc(S_paths, K, r, T, H_up=120, H_down=80):
    """
    Price multiple option types from simulated paths.
    Returns list of dicts with MC price, std error, confidence intervals.
    """
    erT = np.exp(-r * T)
    S_T = S_paths[:, -1]
    n = len(S_T)

    def mc_stats(payoffs, name, exact=None):
        price = erT * np.mean(payoffs)
        se = erT * np.std(payoffs) / np.sqrt(n)
        return dict(
            name=name, price=price, se=se,
            ci_low=price - 1.96 * se, ci_high=price + 1.96 * se,
            exact=exact,
            error_pct=abs(price - exact) / exact * 100 if exact else None,
        )

    def mc_stats_binary(indicator, name):
        p = np.mean(indicator)
        price = erT * p
        se = erT * np.sqrt(p * (1 - p) / n)
        return dict(
            name=name, price=price, se=se,
            ci_low=price - 1.96 * se, ci_high=price + 1.96 * se,
            exact=None, error_pct=None,
        )

    bsm_call = call_price(S_paths[0, 0], K, T, r,
                           estimate_vol_from_paths(S_paths, T),
                           q=0)
    # Use exact BSM for comparison
    results = []

    # European Call
    payoffs_call = np.maximum(S_T - K, 0)
    results.append(mc_stats(payoffs_call, "European Call"))

    # European Put
    payoffs_put = np.maximum(K - S_T, 0)
    results.append(mc_stats(payoffs_put, "European Put"))

    # Asian Call (Arithmetic average)
    S_avg = np.mean(S_paths[:, 1:], axis=1)
    payoffs_asian = np.maximum(S_avg - K, 0)
    results.append(mc_stats(payoffs_asian, "Asian Call (Arithmetic)"))

    # Lookback Call (floating strike)
    S_min = np.min(S_paths, axis=1)
    payoffs_lb = S_T - S_min
    results.append(mc_stats(payoffs_lb, "Lookback Call (Floating)"))

    # Up-and-Out Call
    S_max = np.max(S_paths, axis=1)
    knocked_out = S_max >= H_up
    payoffs_uoc = np.where(knocked_out, 0, np.maximum(S_T - K, 0))
    results.append(mc_stats(payoffs_uoc, "Up-and-Out Call (H={})".format(H_up)))

    # Down-and-In Put
    knocked_in = S_min <= H_down
    payoffs_dip = np.where(knocked_in, np.maximum(K - S_T, 0), 0)
    results.append(mc_stats(payoffs_dip, "Down-and-In Put (L={})".format(H_down)))

    # Double No-Touch
    not_touched = (S_max < H_up) & (S_min > H_down)
    results.append(mc_stats_binary(not_touched, "Double No-Touch"))

    # One-Touch Up
    touched_up = S_max >= H_up
    results.append(mc_stats_binary(touched_up, "One-Touch (Up)"))

    return results


def estimate_vol_from_paths(S_paths, T):
    """Estimate realized vol from paths (for reference only)."""
    n_steps = S_paths.shape[1] - 1
    dt = T / n_steps
    log_returns = np.diff(np.log(S_paths[0, :]))
    return np.std(log_returns) / np.sqrt(dt)


def terminal_distribution_stats(S_T, K):
    """Compute statistics of the terminal distribution S_T."""
    sorted_ST = np.sort(S_T)
    n = len(S_T)
    es5_idx = max(1, int(0.05 * n))

    return dict(
        mean=np.mean(S_T),
        std=np.std(S_T),
        median=np.median(S_T),
        skewness=float(skew(S_T)),
        kurtosis=float(kurtosis(S_T) + 3),  # raw kurtosis
        p5=np.percentile(S_T, 5),
        p25=np.percentile(S_T, 25),
        p75=np.percentile(S_T, 75),
        p95=np.percentile(S_T, 95),
        prob_above_K=np.mean(S_T > K),
        prob_above_120pct=np.mean(S_T > 1.2 * K),
        prob_below_80pct=np.mean(S_T < 0.8 * K),
        expected_shortfall_5=np.mean(sorted_ST[:es5_idx]),
    )


def convergence_analysis(S_paths, K, r, T, sizes=None):
    """Run convergence analysis for European call at various path counts."""
    if sizes is None:
        sizes = [100, 500, 1000, 2500, 5000, 10000, 25000, 50000]

    erT = np.exp(-r * T)
    S_T = S_paths[:, -1]
    n_max = len(S_T)

    results = []
    for n in sizes:
        if n > n_max:
            break
        payoffs = np.maximum(S_T[:n] - K, 0)
        mc_p = erT * np.mean(payoffs)
        mc_se = erT * np.std(payoffs) / np.sqrt(n)
        results.append(dict(n_paths=n, mc_price=mc_p, std_error=mc_se))
    return results


def sample_paths(S_paths, n_sample=10, monthly_steps=21):
    """Extract n sample paths at monthly frequency."""
    n_steps = S_paths.shape[1] - 1
    indices = [0] + list(range(monthly_steps, n_steps + 1, monthly_steps))
    if indices[-1] != n_steps:
        indices.append(n_steps)
    return S_paths[:n_sample, indices]


def histogram_data(S_T, n_bins=25):
    """Compute histogram of terminal distribution."""
    counts, edges = np.histogram(S_T, bins=n_bins)
    return [
        dict(bin_low=edges[i], bin_high=edges[i + 1],
             count=int(counts[i]), freq=100 * counts[i] / len(S_T))
        for i in range(n_bins)
    ]
