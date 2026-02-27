"""
black_scholes.py — Black-Scholes-Merton pricing engine with full Greeks.
All formulas include continuous dividend yield q.
"""

import numpy as np
from scipy.stats import norm


def d1d2(S, K, T, r, sigma, q=0.0):
    """Compute d1 and d2 for BSM formula."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0, 0.0
    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


def call_price(S, K, T, r, sigma, q=0.0):
    """European call price: C = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)"""
    if T <= 0:
        return max(S - K, 0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def put_price(S, K, T, r, sigma, q=0.0):
    """European put price: P = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)"""
    if T <= 0:
        return max(K - S, 0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def call_greeks(S, K, T, r, sigma, q=0.0):
    """Return dict of Greeks for European call."""
    if T <= 0 or sigma <= 0:
        return dict(delta=1.0 if S > K else 0.0, gamma=0, vega=0, theta=0, rho=0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    eqT = np.exp(-q * T)
    erT = np.exp(-r * T)
    nd1 = norm.pdf(d1)
    Nd1 = norm.cdf(d1)
    Nd2 = norm.cdf(d2)
    return dict(
        delta=eqT * Nd1,
        gamma=eqT * nd1 / (S * sigma * np.sqrt(T)),
        vega=S * eqT * nd1 * np.sqrt(T) / 100,
        theta=(-S * eqT * nd1 * sigma / (2 * np.sqrt(T))
               - r * K * erT * Nd2 + q * S * eqT * Nd1) / 365,
        rho=K * T * erT * Nd2 / 100,
    )


def put_greeks(S, K, T, r, sigma, q=0.0):
    """Return dict of Greeks for European put."""
    if T <= 0 or sigma <= 0:
        return dict(delta=-1.0 if S < K else 0.0, gamma=0, vega=0, theta=0, rho=0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    eqT = np.exp(-q * T)
    erT = np.exp(-r * T)
    nd1 = norm.pdf(d1)
    Nd1m = norm.cdf(-d1)
    Nd2m = norm.cdf(-d2)
    return dict(
        delta=-eqT * Nd1m,
        gamma=eqT * nd1 / (S * sigma * np.sqrt(T)),
        vega=S * eqT * nd1 * np.sqrt(T) / 100,
        theta=(-S * eqT * nd1 * sigma / (2 * np.sqrt(T))
               + r * K * erT * Nd2m - q * S * eqT * Nd1m) / 365,
        rho=-K * T * erT * Nd2m / 100,
    )


def digital_call_price(S, K, T, r, sigma, q=0.0, Q=1.0):
    """Digital (binary) call: DC = Q·e^(-rT)·N(d2)"""
    if T <= 0:
        return Q if S > K else 0.0
    _, d2 = d1d2(S, K, T, r, sigma, q)
    return Q * np.exp(-r * T) * norm.cdf(d2)


def digital_put_price(S, K, T, r, sigma, q=0.0, Q=1.0):
    """Digital (binary) put: DP = Q·e^(-rT)·N(-d2)"""
    if T <= 0:
        return Q if S < K else 0.0
    _, d2 = d1d2(S, K, T, r, sigma, q)
    return Q * np.exp(-r * T) * norm.cdf(-d2)


def digital_call_greeks(S, K, T, r, sigma, q=0.0, Q=1.0):
    """Greeks for digital call."""
    if T <= 0 or sigma <= 0:
        return dict(delta=0, gamma=0, vega=0, theta=0, rho=0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    erT = np.exp(-r * T)
    nd2 = norm.pdf(d2)
    Nd2 = norm.cdf(d2)
    return dict(
        delta=Q * erT * nd2 / (S * sigma * np.sqrt(T)),
        gamma=-Q * erT * nd2 * d2 / (S**2 * sigma**2 * T),
        vega=-Q * erT * nd2 * d1 / (sigma * 100),
        theta=Q * erT * (nd2 * (d1 / (2 * T) + r) + r * Nd2) / 365,
        rho=-Q * T * erT * Nd2 / 100,
    )


def digital_put_greeks(S, K, T, r, sigma, q=0.0, Q=1.0):
    """Greeks for digital put."""
    if T <= 0 or sigma <= 0:
        return dict(delta=0, gamma=0, vega=0, theta=0, rho=0)
    d1, d2 = d1d2(S, K, T, r, sigma, q)
    erT = np.exp(-r * T)
    nd2 = norm.pdf(d2)
    Nd2m = norm.cdf(-d2)
    return dict(
        delta=-Q * erT * nd2 / (S * sigma * np.sqrt(T)),
        gamma=Q * erT * nd2 * d2 / (S**2 * sigma**2 * T),
        vega=Q * erT * nd2 * d1 / (sigma * 100),
        theta=-Q * erT * (nd2 * (d1 / (2 * T) + r) - r * Nd2m) / 365,
        rho=Q * T * erT * Nd2m / 100,
    )


# ── Black-76 (options on futures / forwards) ──────────────────────────────

def black76_call(F, K, T, r, sigma):
    """Black-76 call on a forward F: C = e^(-rT)[F·N(d1) - K·N(d2)]"""
    if T <= 0:
        return max(F - K, 0.0)
    if F <= 0 or K <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(F / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return np.exp(-r * T) * (F * norm.cdf(d1) - K * norm.cdf(d2))


def black76_put(F, K, T, r, sigma):
    """Black-76 put on a forward F: P = e^(-rT)[K·N(-d2) - F·N(-d1)]"""
    if T <= 0:
        return max(K - F, 0.0)
    if F <= 0 or K <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(F / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return np.exp(-r * T) * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def black76_greeks(F, K, T, r, sigma, is_call=True):
    """Greeks for Black-76 (w.r.t. the forward price F)."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return dict(delta=0, gamma=0, vega=0, theta=0, rho=0)
    d1 = (np.log(F / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    erT = np.exp(-r * T)
    nd1 = norm.pdf(d1)
    sign = 1 if is_call else -1
    Nd = norm.cdf(sign * d1)
    return dict(
        delta=sign * erT * Nd,
        gamma=erT * nd1 / (F * sigma * np.sqrt(T)),
        vega=erT * F * nd1 * np.sqrt(T) / 100,
        theta=(-erT * F * nd1 * sigma / (2 * np.sqrt(T))
               + r * (black76_call(F, K, T, r, sigma) if is_call
                      else black76_put(F, K, T, r, sigma))) / 365,
        rho=0,  # no sensitivity to r in forward-based model
    )


# ── Bachelier (Normal) model ───────────────────────────────────────────────

def bachelier_call(F, K, T, r, sigma_n):
    """Bachelier call: C = e^(-rT)[(F-K)·N(d) + σ_n·√T·n(d)]
    sigma_n is the *normal* (absolute) volatility = σ_lognormal * F approximately."""
    if T <= 0:
        return max(F - K, 0.0)
    if sigma_n <= 0:
        return max(F - K, 0.0) * np.exp(-r * T)
    d = (F - K) / (sigma_n * np.sqrt(T))
    return np.exp(-r * T) * ((F - K) * norm.cdf(d) + sigma_n * np.sqrt(T) * norm.pdf(d))


def bachelier_put(F, K, T, r, sigma_n):
    """Bachelier put: P = e^(-rT)[(K-F)·N(-d) + σ_n·√T·n(d)]"""
    if T <= 0:
        return max(K - F, 0.0)
    if sigma_n <= 0:
        return max(K - F, 0.0) * np.exp(-r * T)
    d = (F - K) / (sigma_n * np.sqrt(T))
    return np.exp(-r * T) * ((K - F) * norm.cdf(-d) + sigma_n * np.sqrt(T) * norm.pdf(d))


def bachelier_greeks(F, K, T, r, sigma_n, is_call=True):
    """Greeks for Bachelier model."""
    if T <= 0 or sigma_n <= 0:
        return dict(delta=0, gamma=0, vega=0, theta=0, rho=0)
    d = (F - K) / (sigma_n * np.sqrt(T))
    erT = np.exp(-r * T)
    nd = norm.pdf(d)
    sign = 1 if is_call else -1
    return dict(
        delta=sign * erT * norm.cdf(sign * d),
        gamma=erT * nd / (sigma_n * np.sqrt(T)),
        vega=erT * np.sqrt(T) * nd / 100,
        theta=(-erT * sigma_n * nd / (2 * np.sqrt(T))
               + r * (bachelier_call(F, K, T, r, sigma_n) if is_call
                      else bachelier_put(F, K, T, r, sigma_n))) / 365,
        rho=0,
    )


def implied_vol(price, S, K, T, r, q=0.0, is_call=True, tol=1e-8, max_iter=100):
    """Newton-Raphson solver for implied volatility."""
    sigma = 0.20  # initial guess
    for _ in range(max_iter):
        if is_call:
            p = call_price(S, K, T, r, sigma, q)
            g = call_greeks(S, K, T, r, sigma, q)
        else:
            p = put_price(S, K, T, r, sigma, q)
            g = put_greeks(S, K, T, r, sigma, q)
        vega = g["vega"] * 100  # undo /100 scaling
        if abs(vega) < 1e-12:
            break
        sigma -= (p - price) / vega
        sigma = max(sigma, 0.001)
        if abs(p - price) < tol:
            break
    return sigma
