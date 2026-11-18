"""
ui/theme.py — Design tokens and the Plotly chart template.

Apple "Pro" dark aesthetic: true-black canvas, graphite materials, SF type,
system accent blue. Every colour in the app comes from here. Views never
hard-code hex values: they use `C.<token>` for UI colours, `SERIES[i]` for
chart series (in fixed order), and `C.pos` / `C.neg` for gain / loss.

SERIES uses Apple's system hues stepped to a readable lightness band and
ordered so every adjacent pair stays distinguishable under colour-vision
deficiency (validated against the #1C1C1E chart surface).
"""

from types import SimpleNamespace

import plotly.graph_objects as go
import plotly.io as pio

C = SimpleNamespace(
    # Canvas & materials (Apple dark system greys)
    bg="#000000",
    surface="#1C1C1E",
    surface_2="#2C2C2E",
    surface_3="#3A3A3C",
    border="#38383A",
    border_soft="#2C2C2E",
    # Labels
    text="#F5F5F7",
    text_2="#D2D2D7",
    muted="#A1A1A6",
    subtle="#6E6E73",
    # Accent
    accent="#0A84FF",
    accent_2="#2997FF",
    accent_soft="rgba(10,132,255,0.16)",
    # Semantic (Apple system colours, dark appearance)
    pos="#30D158",
    neg="#FF453A",
    warn="#FF9F0A",
    info="#0A84FF",
    # Chart chrome
    grid="rgba(255,255,255,0.06)",
    axis="rgba(255,255,255,0.14)",
)

# Categorical series colours — assign in this order, never cycle past 8.
SERIES = [
    "#0A84FF",  # blue
    "#D27306",  # orange
    "#BF5AF2",  # purple
    "#239E45",  # green
    "#6E6CF0",  # indigo
    "#FF375F",  # pink
    "#2A93C2",  # teal
    "#A88600",  # yellow
]

# Sequential (single hue, deep → bright on black) for surfaces / heatmaps.
SEQUENTIAL = [
    [0.0, "#06274D"], [0.25, "#0A4A8F"], [0.5, "#0A84FF"],
    [0.75, "#64B4FF"], [1.0, "#CFE6FF"],
]

# Diverging (orange ↔ neutral graphite ↔ blue) for signed quantities.
DIVERGING = [
    [0.0, "#D27306"], [0.5, "#3A3A3C"], [1.0, "#0A84FF"],
]

FONT_STACK = ("-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', "
              "Inter, 'Helvetica Neue', sans-serif")
MONO_STACK = "'SF Mono', 'JetBrains Mono', ui-monospace, Menlo, monospace"


def rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' → 'rgba(r,g,b,a)' for translucent fills."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def tone_color(value: float) -> str:
    """Gain / loss colour for a signed number."""
    if value != value or value == 0:  # NaN or zero
        return C.muted
    return C.pos if value > 0 else C.neg


def _build_template() -> go.layout.Template:
    axis = dict(
        gridcolor=C.grid, gridwidth=1,
        linecolor=C.axis, linewidth=1, showline=False,
        zerolinecolor=C.axis, zerolinewidth=1,
        ticks="", ticklen=0,
        tickfont=dict(color=C.subtle, size=11),
        title=dict(font=dict(color=C.muted, size=11), standoff=10),
        automargin=True,
    )
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        colorway=SERIES,
        font=dict(family=FONT_STACK, color=C.text_2, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        # Title pinned to the top of the figure; the legend sits in its own band
        # just above the plot area, so the two never overlap.
        title=dict(font=dict(size=17, color=C.text, family=FONT_STACK, weight=600),
                   x=0, xref="paper", xanchor="left",
                   y=1, yref="container", yanchor="top", pad=dict(t=18)),
        # Generous margins: charts sit inside glass cards (see styles.css).
        margin=dict(l=22, r=22, t=92, b=18),
        xaxis=axis,
        yaxis=axis,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            font=dict(color=C.muted, size=12),
            itemsizing="constant",
        ),
        hoverlabel=dict(
            bgcolor="rgba(44,44,46,0.92)", bordercolor="rgba(255,255,255,0.12)",
            font=dict(family=FONT_STACK, color=C.text, size=12),
        ),
        hovermode="x unified",
        scene=dict(
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.subtle),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.subtle),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.subtle),
        ),
        colorscale=dict(sequential=SEQUENTIAL, diverging=DIVERGING),
        bargap=0.3,
        transition=dict(duration=500, easing="cubic-in-out"),
    )
    # Lines stay linear: smoothing would round payoff kinks and misstate the data.
    tpl.data.scatter = [go.Scatter(line=dict(width=2.25),
                                   marker=dict(size=8, line=dict(width=2, color=C.bg)))]
    tpl.data.bar = [go.Bar(marker=dict(line=dict(width=0), cornerradius=4))]
    return tpl


def register_plotly_template() -> None:
    """Register the 'fmt' template and make it the process-wide default."""
    pio.templates["fmt"] = _build_template()
    pio.templates.default = "fmt"


register_plotly_template()
