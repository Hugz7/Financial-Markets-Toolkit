# Markets Toolkit

A Streamlit app for pricing, analysing and simulating derivatives and rates products: options and exotics, volatility smiles, yield curves, swaps, forwards and Monte Carlo, plus a live market monitor.

## Pages

| Section | Page | What it does |
|---------|------|-------------|
| Markets | **Market Monitor** | Cross-asset quotes (equities, vol, rates, FX, commodities, crypto) and headlines from 8 financial RSS feeds |
| Options | **Payoff Analyzer** | Multi-leg strategy builder with 14 presets and a P&L-at-maturity chart |
| Options | **Exotic Pricer** | 15 exotic options in closed form, vanillas under BSM, Black-76 and Bachelier |
| Options | **Volatility Smile** | Implied-vol smiles, term structure and surface from live option chains |
| Rates & Forwards | **Yield Curve** | Zero-curve bootstrapping, forwards and spread interpretation |
| Rates & Forwards | **Swaps** | Cashflows, NPV, DV01 and break-even rate for IRS, basis and cross-currency swaps |
| Rates & Forwards | **Forwards** | Equity, FX and commodity forwards with term structure and sensitivities |
| Simulation | **Monte Carlo** | GBM paths, 8 payoffs priced with confidence intervals, convergence vs BSM |
| Project | **Roadmap** | Editable list of planned features |

## Architecture

```
main.py              entry point: page config, theme, st.navigation
.streamlit/          native theme (colours, fonts, radii) — config.toml
assets/              logo and icon
ui/                  presentation layer
  theme.py             design tokens, chart palette, Plotly "fmt" template
  components.py        page_header, section, Stat/stat_grid, callout, chart, …
  formatting.py        number formatting (money, pct, bp)
  styles.css           the few global styles the native theme can't express
views/               one module per page, each exposing render()
services/            data access, cached: market quotes, news, option chains, persistence
models/              pure pricing maths — no Streamlit, no I/O, unit-tested
tests/               pytest suite for models/
```

The dependency direction is one-way: `views → ui, services, models`; `services → models`; `models` depends on nothing in the app. Views contain no inline HTML or hard-coded colours: every colour comes from `ui/theme.py`, and every chart is rendered through `ui.components.chart`, which applies the shared template.

## Design

The look follows Apple's "Pro" product pages:

- **Canvas and texture**: a true-black background with slowly drifting coloured light and a faint film-grain overlay.
- **Materials and depth**: translucent graphite panels with background blur, top-edge highlights and layered shadows; cards lift on hover.
- **Typography**: SF Pro on Apple devices (Inter elsewhere), large gradient headlines, and two-tone section titles ("Valuation. Grey continuation.").
- **Navigation**: a translucent top bar with section menus, which becomes a drawer on phones.
- **Motion**: staggered rise-in on load, scroll-driven reveals for sections and charts (where the browser supports them), and pill and segmented controls. All motion is disabled under `prefers-reduced-motion`.

Chart colours use Apple's system hues, stepped to a readable lightness and ordered so adjacent series stay distinguishable for colour-blind readers (checked against the chart surface). They are assigned in fixed order.

## Setup

```bash
pip install -r requirements.txt
streamlit run main.py
```

The app opens at `http://localhost:8501`. The Market Monitor and Volatility Smile pages need internet access (Yahoo Finance and RSS feeds); every other page works offline.

## Tests

```bash
pytest -q
```

Covers put-call parity, BSM reference values, implied-vol round-trips, touch/no-touch identities, Monte Carlo convergence against BSM, swap DV01 against a 1 bp bump, break-even rates, swap-type differentiation and payoff sanity checks.

## Pricing models

| Model | Module | Used for |
|-------|--------|---------|
| Black-Scholes-Merton | `models/black_scholes.py` | European options, Greeks, implied vol |
| Black-76 | `models/black_scholes.py` | Options on forwards/futures |
| Bachelier | `models/black_scholes.py` | Normal-model options |
| Reflection principle | `models/exotic_options.py` | One-touch / no-touch |
| Kemna-Vorst | `models/exotic_options.py` | Geometric Asian call |
| Goldman-Sosin-Gatto | `models/exotic_options.py` | Floating-strike lookback |
| Rubinstein | `models/exotic_options.py` | Chooser option |
| Log-Euler GBM | `models/monte_carlo.py` | Path simulation |
| Bootstrapping | `models/yield_curve.py` | Zero and forward curves |
| Annuity discounting | `models/swaps.py` | Swap NPV, DV01, break-even rate |
