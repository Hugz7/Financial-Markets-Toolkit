"""
config.py — Shared styles, constants, and color palette for the app.
"""

# ── Color Palette ──────────────────────────────────────────────
DARK_BG    = "#080C14"        # near-black main background
CARD_BG    = "#0F1923"        # dark card background
ACCENT_GOLD  = "#F0B429"      # amber — kept for compatibility
ACCENT_BLUE  = "#38BDF8"      # sky-blue
ACCENT_GREEN = "#10D48A"      # emerald green
ACCENT_RED   = "#FF4D6D"      # rose-red
ACCENT_CYAN  = "#00E5FF"      # electric cyan — primary accent
TEXT_WHITE   = "#E8EDF5"      # near-white text
TEXT_GREY    = "#5A6A82"      # muted text

# ── Plotly Chart Template ──────────────────────────────────────
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(8,12,20,0.85)",
    font=dict(family="'Inter', 'SF Pro Display', Arial, sans-serif",
              color=TEXT_WHITE, size=12),
    margin=dict(l=60, r=30, t=50, b=50),
    legend=dict(bgcolor="rgba(15,25,35,0.8)", bordercolor="#1E3A55",
                borderwidth=1, font=dict(size=11)),
)

# Grid styling applied via fig.update_xaxes / fig.update_yaxes after update_layout
GRID_STYLE = dict(gridcolor="#1A2E45", zerolinecolor="#1A2E45", zerolinewidth=1)

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
# Each preset: dict of leg_index -> (instrument, direction, K, barrier, T, premium, qty)
STRATEGY_PRESETS = {
    "── Select a preset ──": {},
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

# ── Swap Types ─────────────────────────────────────────────────
SWAP_TYPES = ["IRS Pay Fixed", "IRS Receive Fixed", "Basis Swap", "XCCY Swap"]
DAY_COUNTS = ["30/360", "ACT/360", "ACT/365"]
