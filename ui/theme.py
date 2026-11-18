"""
ui/theme.py — Design tokens and the Plotly chart template.

Every colour in the app comes from here. Views never hard-code hex values:
they use `C.<token>` for UI colours, `SERIES[i]` for chart series (in fixed
order), and `C.pos` / `C.neg` for gain / loss.

The categorical palette is the validated dark-mode set (CVD-safe adjacent
pairs, >= 3:1 against the chart surface).
"""

from types import SimpleNamespace

import plotly.graph_objects as go
import plotly.io as pio

C = SimpleNamespace(
    # Surfaces
    bg="#0B0D11",
    surface="#12151C",
    surface_2="#151922",
    surface_3="#1B202B",
    border="#252A35",
    border_soft="#1E232C",
    # Text
    text="#E7E9EE",
    text_2="#B4BAC6",
    muted="#8A92A0",
    subtle="#5F6775",
    # Accent
    accent="#5B8DEF",
    accent_soft="rgba(91,141,239,0.14)",
    # Semantic (text-grade — readable on dark surfaces)
    pos="#2FBF71",
    neg="#EF5B67",
    warn="#E8A93B",
    info="#5B8DEF",
    # Chart chrome
    grid="#1C212B",
    axis="#2A303C",
)

# Categorical series colours — assign in this order, never cycle past 8.
SERIES = [
    "#3987e5",  # blue
    "#d95926",  # orange
    "#199e70",  # aqua
    "#c98500",  # yellow
    "#d55181",  # magenta
    "#0ca30c",  # green
    "#9085e9",  # violet
    "#e66767",  # red
]

# Sequential (single hue, dark → light on a dark surface) for surfaces / heatmaps.
SEQUENTIAL = [
    [0.0, "#184f95"], [0.25, "#256abf"], [0.5, "#3987e5"],
    [0.75, "#6da7ec"], [1.0, "#b7d3f6"],
]

# Diverging (orange ↔ neutral ↔ blue) for signed quantities.
DIVERGING = [
    [0.0, "#d95926"], [0.5, "#383835"], [1.0, "#3987e5"],
]

FONT_STACK = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
MONO_STACK = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"


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
        linecolor=C.axis, linewidth=1, showline=True,
        zerolinecolor=C.axis, zerolinewidth=1,
        tickcolor=C.axis, ticks="outside", ticklen=4,
        tickfont=dict(color=C.muted, size=11),
        title=dict(font=dict(color=C.muted, size=11), standoff=8),
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
        title=dict(font=dict(size=14, color=C.text), x=0, xref="paper", xanchor="left",
                   y=1, yref="container", yanchor="top", pad=dict(t=10)),
        margin=dict(l=8, r=8, t=76, b=8),
        xaxis=axis,
        yaxis=axis,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            font=dict(color=C.text_2, size=11),
        ),
        hoverlabel=dict(
            bgcolor=C.surface_3, bordercolor=C.border,
            font=dict(family=FONT_STACK, color=C.text, size=12),
        ),
        hovermode="x unified",
        scene=dict(
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.muted),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.muted),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=C.grid,
                       zerolinecolor=C.axis, color=C.muted),
        ),
        colorscale=dict(sequential=SEQUENTIAL, diverging=DIVERGING),
        bargap=0.25,
    )
    tpl.data.scatter = [go.Scatter(line=dict(width=2), marker=dict(size=8))]
    tpl.data.bar = [go.Bar(marker=dict(line=dict(width=0)))]
    return tpl


def register_plotly_template() -> None:
    """Register the 'fmt' template and make it the process-wide default."""
    pio.templates["fmt"] = _build_template()
    pio.templates.default = "fmt"


register_plotly_template()
