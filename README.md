# Financial Markets Toolkit

A Streamlit web app for pricing, analysing, and simulating financial derivatives and structured products. Provides institutional-grade tools for options, bonds, swaps, and exotic instruments with live market data integration.

## Features

| Page | What it does |
|------|-------------|
| **Market Monitor** | Live quotes for 9 major assets (equities, FX, rates, vol, crypto) + financial news feeds |
| **Payoff Analyzer** | Multi-leg option strategy builder with 20 pre-built strategy presets and interactive payoff chart |
| **Exotic Pricer** | Closed-form pricing for 15 exotic option types (touch, barrier, Asian, lookback, chooser, gap, power, range accrual) across 3 models (BSM, Black-76, Bachelier) |
| **Vol Smile** | Live implied-vol smile from real option chains (via yfinance), 2D/3D vol surface, skew metrics |
| **Swaps** | Full cashflow schedules, NPV, correct DV01, and break-even rate for IRS Pay/Receive Fixed, Basis Swap (float-for-float), and XCCY Swap (domestic fixed vs foreign float) |
| **Forwards** | Equity, FX, and commodity forward pricing with term structure and sensitivity analysis |
| **Monte Carlo** | GBM path simulation, pricing of 8 option types, convergence analysis vs analytical BSM benchmarks, terminal distribution statistics |
| **Yield Curve** | Zero-coupon curve bootstrapping from market instruments |

## Tech stack

- **Python 3.10+**
- **Streamlit** — interactive web UI
- **NumPy / SciPy** — numerical pricing engines
- **Pandas** — data manipulation
- **Plotly** — interactive financial charts
- **yfinance** — live market data and option chains
- **feedparser** — financial news RSS aggregation

## Pricing models

| Model | Location | Used for |
|-------|----------|---------|
| Black-Scholes-Merton | `models/black_scholes.py` | European options, Greeks, implied vol (Newton-Raphson) |
| Black-76 | `models/black_scholes.py` | Options on forwards/futures |
| Bachelier (Normal) | `models/black_scholes.py` | Options on assets that can go negative |
| Goldman-Sosin-Gatto | `models/exotic_options.py` | Lookback call (floating strike) |
| Kemna-Vorst | `models/exotic_options.py` | Asian geometric average call |
| Rubinstein | `models/exotic_options.py` | Chooser option |
| Reflection principle | `models/exotic_options.py` | One-Touch / No-Touch barriers |
| Log-Euler GBM | `models/monte_carlo.py` | Monte Carlo path simulation |
| Discount factor annuity | `models/swaps.py` | Swap NPV, DV01, break-even rate |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run main.py
```

The app opens at `http://localhost:8501`.

## Running tests

```bash
pip install pytest
pytest -q
```

The test suite covers:

- **Put-call parity** and known BSM reference values
- **Implied vol round-trip** (price → IV → price)
- **Touch/no-touch identity**: OT + NT = e^{-rT}
- **Gap call** equals vanilla call when trigger = strike
- **Monte Carlo convergence**: European call/put within 95% CI of analytical BSM (100k paths, fixed seed)
- **Swap DV01** matches 1bp finite-difference bump within 1%
- **Break-even rate** produces NPV ≈ 0 when used as the fixed rate
- **Swap type differentiation**: Basis and XCCY produce different cashflows from IRS

## Project structure

```
.
├── main.py                   # Streamlit entry point and page router
├── config.py                 # Colour palette, constants, require() validation helper
├── requirements.txt
├── models/
│   ├── black_scholes.py      # BSM, Black-76, Bachelier, Greeks, implied vol
│   ├── exotic_options.py     # 15 exotic option types (closed-form)
│   ├── forwards.py           # Equity, FX, commodity forwards
│   ├── monte_carlo.py        # GBM simulator, payoff pricing, convergence
│   └── swaps.py              # IRS, Basis, XCCY swap cashflows and metrics
├── pages/
│   ├── home_dashboard.py
│   ├── structured_products.py
│   ├── exotic_pricer.py
│   ├── vol_smile_page.py
│   ├── swaps_page.py
│   ├── forwards_page.py
│   ├── monte_carlo_page.py
│   ├── yield_curve_page.py
│   └── roadmap.py
└── tests/
    ├── test_black_scholes.py
    ├── test_exotics.py
    ├── test_monte_carlo.py
    └── test_swaps.py
```
