"""
exotic_options.py — Closed-form pricing for 15 exotic options.
All formulas include continuous dividend yield q.
"""

import numpy as np
from scipy.stats import norm
from models.black_scholes import (
    call_price, put_price, call_greeks, put_greeks,
    digital_call_price, digital_put_price,
    digital_call_greeks, digital_put_greeks, d1d2,
)


def one_touch_up(S, H, T, r, sigma, q=0.0):
    """
    One-Touch Up barrier option (pays 1 at maturity if S ever touches H).
    Uses reflection principle:
    OT = e^(-rT) * [N((mu*T - b)/(sig*sqrt(T))) + exp(2*mu*b/sig^2) * N((-mu*T - b)/(sig*sqrt(T)))]
    where mu = r - q - sig^2/2, b = ln(H/S)
    """
    if S >= H:
        return np.exp(-r * T)
    if T <= 0 or sigma <= 0:
        return 0.0
    mu = r - q - sigma**2 / 2
    b = np.log(H / S)
    sT = sigma * np.sqrt(T)
    erT = np.exp(-r * T)
    term1 = norm.cdf((mu * T - b) / sT)
    term2 = np.exp(2 * mu * b / sigma**2) * norm.cdf((-mu * T - b) / sT)
    return erT * (term1 + term2)


def no_touch_up(S, H, T, r, sigma, q=0.0):
    """No-Touch Up = e^(-rT) - One-Touch Up."""
    return np.exp(-r * T) - one_touch_up(S, H, T, r, sigma, q)


def one_touch_down(S, L, T, r, sigma, q=0.0):
    """
    One-Touch Down barrier option (pays 1 at maturity if S ever touches L).
    OT_down = e^(-rT) * [N((-mu*T - c)/(sig*sqrt(T))) + exp(-2*mu*c/sig^2) * N((mu*T - c)/(sig*sqrt(T)))]
    where c = ln(S/L)
    """
    if S <= L:
        return np.exp(-r * T)
    if T <= 0 or sigma <= 0:
        return 0.0
    mu = r - q - sigma**2 / 2
    c = np.log(S / L)
    sT = sigma * np.sqrt(T)
    erT = np.exp(-r * T)
    term1 = norm.cdf((-mu * T - c) / sT)
    term2 = np.exp(-2 * mu * c / sigma**2) * norm.cdf((mu * T - c) / sT)
    return erT * (term1 + term2)


def no_touch_down(S, L, T, r, sigma, q=0.0):
    """No-Touch Down = e^(-rT) - One-Touch Down."""
    return np.exp(-r * T) - one_touch_down(S, L, T, r, sigma, q)


def double_no_touch(S, L, H, T, r, sigma, q=0.0):
    """
    Double No-Touch: pays 1 at maturity if S never touches L or H.
    Approximation: max(0, NT_up + NT_down - e^(-rT)).
    """
    nt_u = no_touch_up(S, H, T, r, sigma, q)
    nt_d = no_touch_down(S, L, T, r, sigma, q)
    return max(0.0, nt_u + nt_d - np.exp(-r * T))


def asian_geometric_call(S, K, T, r, sigma, q=0.0):
    """
    Asian call on geometric average (Kemna-Vorst).
    sigma_hat = sigma / sqrt(3)
    b_hat = 0.5 * (r - q - sigma^2/6)
    Then standard BSM with adjusted parameters.
    """
    if T <= 0:
        return max(S - K, 0)
    sigma_hat = sigma / np.sqrt(3)
    b_hat = 0.5 * (r - q - sigma**2 / 6)
    d1 = (np.log(S / K) + (b_hat + sigma_hat**2 / 2) * T) / (sigma_hat * np.sqrt(T))
    d2 = d1 - sigma_hat * np.sqrt(T)
    return (np.exp((b_hat - r) * T) * S * norm.cdf(d1)
            - np.exp(-r * T) * K * norm.cdf(d2))


def lookback_call_floating(S, T, r, sigma, q=0.0, S_min=None):
    """
    Lookback call with floating strike (Goldman-Sosin-Gatto).
    Payoff = S_T - min(S_t). At inception S_min = S.
    """
    if S_min is None:
        S_min = S
    if T <= 0:
        return max(S - S_min, 0)
    eqT = np.exp(-q * T)
    erT = np.exp(-r * T)
    a1 = (np.log(S / S_min) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    a2 = a1 - sigma * np.sqrt(T)
    rq = r - q
    if abs(rq) > 1e-10:
        eta = sigma**2 / (2 * rq)
        val = (S * eqT * norm.cdf(a1) - S_min * erT * norm.cdf(a2)
               + S * erT * eta * (
                   (S / S_min) ** (-2 * rq / sigma**2)
                   * norm.cdf(-a1 + 2 * rq * np.sqrt(T) / sigma)
                   - np.exp(rq * T) * norm.cdf(-a1)))
    else:
        val = (S * eqT * norm.cdf(a1) - S_min * erT * norm.cdf(a2)
               + S * sigma * np.sqrt(T) * erT
               * (norm.pdf(a1) + a1 * norm.cdf(a1)))
    return max(val, 0)


def chooser_option(S, K, T, r, sigma, q=0.0, t_c=0.5):
    """
    Chooser option (Rubinstein): at t_c holder picks call or put.
    Price = Call(S,K,T) + K·e^(-rT)·N(-d2(tc)) - S·e^(-qT)·N(-d1(tc))
    """
    if T <= 0:
        return max(max(S - K, 0), max(K - S, 0))
    C = call_price(S, K, T, r, sigma, q)
    eqT = np.exp(-q * T)
    erT = np.exp(-r * T)
    d1_tc = (np.log(S / K) + (r - q) * T + sigma**2 * t_c / 2) / (sigma * np.sqrt(t_c))
    d2_tc = d1_tc - sigma * np.sqrt(t_c)
    return C + K * erT * norm.cdf(-d2_tc) - S * eqT * norm.cdf(-d1_tc)


def gap_call(S, K, T, r, sigma, q=0.0, K_gap=105):
    """
    Gap call: triggers at K_gap, pays S_T - K if S_T > K_gap.
    GC = S·e^(-qT)·N(d1(K_gap)) - K·e^(-rT)·N(d2(K_gap))
    """
    if T <= 0:
        return (S - K) if S > K_gap else 0.0
    d1 = (np.log(S / K_gap) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def power_option(S, T, r, sigma, q=0.0, n=2):
    """
    Power option: E[e^(-rT) * S_T^n].
    = e^(-rT) * S^n * exp[n*(r-q)*T + n*(n-1)*sigma^2*T/2]
    """
    return (np.exp(-r * T) * S**n
            * np.exp(n * (r - q) * T + n * (n - 1) * sigma**2 * T / 2))


def range_accrual(S, L, H, T, r, sigma, q=0.0):
    """
    Range accrual: P(L < S_T < H) * e^(-rT).
    ln(S_T) ~ N(ln(S) + (r-q-sig^2/2)*T, sig^2*T)
    """
    if T <= 0:
        return np.exp(-r * T) if L < S < H else 0.0
    mu_log = np.log(S) + (r - q - sigma**2 / 2) * T
    sig_log = sigma * np.sqrt(T)
    p = norm.cdf((np.log(H) - mu_log) / sig_log) - norm.cdf((np.log(L) - mu_log) / sig_log)
    return p * np.exp(-r * T)


def price_all_exotics(S, K, T, r, sigma, q, H_up, H_down, Q_pay,
                      sig2, rho, S2, n_pow, t_c, K_gap):
    """
    Price all 15 exotic options. Returns list of dicts.
    """
    results = []

    # 1. European Call
    cp = call_price(S, K, T, r, sigma, q)
    cg = call_greeks(S, K, T, r, sigma, q)
    results.append(dict(name="European Call (BSM)", method="Black-Scholes",
                        price=cp, **cg))

    # 2. European Put
    pp = put_price(S, K, T, r, sigma, q)
    pg = put_greeks(S, K, T, r, sigma, q)
    results.append(dict(name="European Put (BSM)", method="Black-Scholes",
                        price=pp, **pg))

    # 3. Digital Call
    dc = digital_call_price(S, K, T, r, sigma, q, Q_pay)
    dcg = digital_call_greeks(S, K, T, r, sigma, q, Q_pay)
    results.append(dict(name="Digital Call", method="BSM: Q·e⁻ʳᵀ·N(d₂)",
                        price=dc, **dcg))

    # 4. Digital Put
    dp = digital_put_price(S, K, T, r, sigma, q, Q_pay)
    dpg = digital_put_greeks(S, K, T, r, sigma, q, Q_pay)
    results.append(dict(name="Digital Put", method="BSM: Q·e⁻ʳᵀ·N(-d₂)",
                        price=dp, **dpg))

    # 5-8. Barrier / Touch options
    otu = one_touch_up(S, H_up, T, r, sigma, q)
    results.append(dict(name="One-Touch (Up)", method="Reflection principle",
                        price=otu, delta=None, gamma=None, vega=None, theta=None, rho=None))

    ntu = no_touch_up(S, H_up, T, r, sigma, q)
    results.append(dict(name="No-Touch (Up)", method="1 − OT(Up)",
                        price=ntu, delta=None, gamma=None, vega=None, theta=None, rho=None))

    otd = one_touch_down(S, H_down, T, r, sigma, q)
    results.append(dict(name="One-Touch (Down)", method="Reflection principle",
                        price=otd, delta=None, gamma=None, vega=None, theta=None, rho=None))

    ntd = no_touch_down(S, H_down, T, r, sigma, q)
    results.append(dict(name="No-Touch (Down)", method="1 − OT(Down)",
                        price=ntd, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 9. Double No-Touch
    dnt = double_no_touch(S, H_down, H_up, T, r, sigma, q)
    results.append(dict(name="Double No-Touch", method="NT_up + NT_down − e⁻ʳᵀ",
                        price=dnt, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 10. Asian Geometric Call
    agc = asian_geometric_call(S, K, T, r, sigma, q)
    results.append(dict(name="Asian Call (Geometric)", method="Kemna-Vorst",
                        price=agc, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 11. Lookback Call (floating)
    lbc = lookback_call_floating(S, T, r, sigma, q)
    results.append(dict(name="Lookback Call (Floating)", method="Goldman-Sosin-Gatto",
                        price=lbc, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 12. Chooser
    ch = chooser_option(S, K, T, r, sigma, q, t_c)
    results.append(dict(name="Chooser Option", method="Rubinstein",
                        price=ch, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 13. Gap Call
    gc = gap_call(S, K, T, r, sigma, q, K_gap)
    results.append(dict(name="Gap Call", method="BSM adjusted (trigger ≠ strike)",
                        price=gc, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 14. Power Option
    po = power_option(S, T, r, sigma, q, n_pow)
    results.append(dict(name=f"Power Option (S^{n_pow})", method="Moment generating fn.",
                        price=po, delta=None, gamma=None, vega=None, theta=None, rho=None))

    # 15. Range Accrual
    ra = range_accrual(S, H_down, H_up, T, r, sigma, q)
    results.append(dict(name="Range Accrual", method="Log-normal CDF",
                        price=ra, delta=None, gamma=None, vega=None, theta=None, rho=None))

    return results
