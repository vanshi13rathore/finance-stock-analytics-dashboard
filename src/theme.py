"""Design system for the dashboard: colours, typography, CSS, Plotly theme.

Everything visual lives here so the four tabs share one palette, one type
scale and one set of card/table styles. Nothing in this module computes
financial numbers — it only formats and styles.

The module is deliberately free of Streamlit imports: every helper returns a
string (HTML) or a Plotly object, which keeps it unit-testable without a
running Streamlit server.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = "#0A0F1A"            # app background (deep navy)
SURFACE = "#111A2B"       # cards, tables, chart panels
SURFACE_ALT = "#162032"   # raised surfaces, hover states
SIDEBAR = "#0C1322"
BORDER = "#223049"
GRID = "#1B2740"
TEXT = "#E8EEF9"          # primary text (≈15:1 on BG)
TEXT_BODY = "#C7D3E6"     # body copy
MUTED = "#93A3BA"         # secondary text (≈7:1 on BG)
FAINT = "#7E8EA6"         # micro labels (5.2:1 on cards — AA for small text)
ACCENT = "#6C8FFF"
POSITIVE = "#34D399"
NEGATIVE = "#FB7185"
WARNING = "#FBBF24"

FONT = (
    '"Inter", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    'Roboto, "Helvetica Neue", Arial, sans-serif'
)

# ---------------------------------------------------------------------------
# Ticker identity — one colour + one marker symbol for the whole app.
# Symbols matter for accessibility: colour is never the only channel.
# ---------------------------------------------------------------------------
TICKER_COLORS: dict[str, str] = {
    "BAC": "#5B8DEF",  # blue
    "C": "#F0B429",    # amber
    "GS": "#A78BFA",   # violet
    "JPM": "#2DD4BF",  # teal
    "MS": "#FB7185",   # rose
    "WFC": "#9CCC65",  # green
}

TICKER_SYMBOLS: dict[str, str] = {
    "BAC": "circle",
    "C": "square",
    "GS": "diamond",
    "JPM": "triangle-up",
    "MS": "cross",
    "WFC": "hexagon",
}

FALLBACK_COLORS: tuple[str, ...] = (
    "#5B8DEF", "#F0B429", "#A78BFA", "#2DD4BF", "#FB7185", "#9CCC65",
    "#7DD3FC", "#FCA5A5",
)

PLOTLY_TEMPLATE = "fsa_dark"

#: Shared Plotly config: no permanent toolbar, but scroll-zoom stays on.
PLOTLY_CONFIG: dict[str, object] = {
    "displayModeBar": False,
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
}

#: Diverging scale for correlations (negative = crimson, zero = surface,
#: positive = teal). Endpoints are deliberately mid-dark so the white cell
#: labels keep at least 4.5:1 contrast.
DIVERGING = [
    [0.0, "#B8425A"],
    [0.5, GRID],
    [1.0, "#0C8272"],
]


def ticker_color(ticker: str) -> str:
    """Colour for a ticker, stable across every chart."""
    if ticker in TICKER_COLORS:
        return TICKER_COLORS[ticker]
    idx = sum(ord(c) for c in str(ticker)) % len(FALLBACK_COLORS)
    return FALLBACK_COLORS[idx]


def ticker_symbol(ticker: str) -> str:
    """Marker symbol for a ticker (secondary encoding alongside colour)."""
    return TICKER_SYMBOLS.get(ticker, "circle")


def tint(color: str, factor: float) -> str:
    """Mix a hex colour towards white (``factor`` 0 = unchanged, 1 = white)."""
    factor = max(0.0, min(1.0, float(factor)))
    color = color.lstrip("#")
    channels = [int(color[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(c + (255 - c) * factor) for c in channels]
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def rgba(color: str, alpha: float) -> str:
    """``rgba()`` string for a hex colour, for translucent fills."""
    color = color.lstrip("#")
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# Formatters (NaN-safe, tabular numerals)
# ---------------------------------------------------------------------------
def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def fmt_pct(value: object, digits: int = 1, signed: bool = False) -> str:
    """``0.1234`` → ``"12.3%"`` (or ``"+12.3%"`` when ``signed``)."""
    number = _number(value)
    if number is None:
        return "—"
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number * 100:.{digits}f}%"


def fmt_ratio(value: object, digits: int = 2, signed: bool = False) -> str:
    """Format a unit-less ratio such as Sharpe or Sortino."""
    number = _number(value)
    if number is None:
        return "—"
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number:.{digits}f}"


def fmt_money(value: object, digits: int = 2) -> str:
    """``1.2345`` → ``"$1.23"``."""
    number = _number(value)
    if number is None:
        return "—"
    return f"${number:,.{digits}f}"


def fmt_int(value: object) -> str:
    """``2517`` → ``"2,517"``."""
    number = _number(value)
    if number is None:
        return "—"
    return f"{number:,.0f}"


def tone_of(value: object) -> str:
    """Map a signed value to a card tone: ``pos`` / ``neg`` / ``neutral``."""
    number = _number(value)
    if number is None:
        return "neutral"
    if number > 0:
        return "pos"
    if number < 0:
        return "neg"
    return "neutral"


# ---------------------------------------------------------------------------
# HTML fragments (pure strings; the app renders them with unsafe_allow_html)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KpiCard:
    """One KPI tile: label, formatted value, optional context line."""

    label: str
    value: str
    sub: str = ""
    tone: str = "neutral"  # neutral | pos | neg | acc
    swatch: str = ""       # ticker colour dot
    tooltip: str = ""


@dataclass(frozen=True)
class Section:
    """Heading + one-line description above a chart or table."""

    title: str
    description: str = ""


def kpi_grid(cards: Sequence[KpiCard]) -> str:
    """Render a responsive grid of KPI cards."""
    cells: list[str] = []
    for card in cards:
        swatch = (
            f'<span class="fsa-swatch" style="background:{card.swatch}"></span>'
            if card.swatch
            else ""
        )
        tooltip = f' title="{html.escape(card.tooltip)}"' if card.tooltip else ""
        sub = (
            f'<div class="fsa-kpi-sub">{html.escape(card.sub)}</div>'
            if card.sub
            else ""
        )
        cells.append(
            f'<div class="fsa-kpi is-{card.tone}"{tooltip}>'
            f'<div class="fsa-kpi-label">{swatch}{html.escape(card.label)}</div>'
            f'<div class="fsa-kpi-value">{html.escape(card.value)}</div>'
            f"{sub}</div>"
        )
    return f'<div class="fsa-kpis">{"".join(cells)}</div>'


def chips(items: Iterable[Sequence[str]]) -> str:
    """Render a row of metadata chips: ``(label, value[, tone])``."""
    parts: list[str] = []
    for item in items:
        label, value = item[0], item[1]
        tone = item[2] if len(item) > 2 else ""
        tone_class = f" {tone}" if tone in {"pos", "neg", "warn"} else ""
        parts.append(
            f'<span class="fsa-chip"><span class="k">{html.escape(label)}</span>'
            f'<span class="v{tone_class}">{html.escape(value)}</span></span>'
        )
    return f'<div class="fsa-chips">{"".join(parts)}</div>'


def status_pill(source: str) -> str:
    """Data-provenance pill: live Yahoo, cached CSV, or synthetic demo."""
    if source == "yahoo":
        label, css = "Yahoo Finance · live", "live"
    elif source == "cache":
        label, css = "Yahoo Finance · cached", "cache"
    else:
        label, css = "Synthetic demo data", "mock"
    return (
        f'<div class="fsa-pill {css}"><span class="dot"></span>'
        f"{html.escape(label)}</div>"
    )


def hero(title: str, subtitle: str, pill_html: str = "") -> str:
    """Page header: brand title, subtitle and the provenance pill."""
    return (
        '<div class="fsa-hero"><div class="fsa-hero-text">'
        f'<h1 class="fsa-title">{html.escape(title)}</h1>'
        f'<p class="fsa-subtitle">{html.escape(subtitle)}</p></div>'
        f"{pill_html}</div>"
    )


def section_html(section: Section) -> str:
    """Section heading block."""
    description = (
        f"<p>{html.escape(section.description)}</p>" if section.description else ""
    )
    return (
        f'<div class="fsa-sec"><h3>{html.escape(section.title)}</h3>'
        f"{description}</div>"
    )


def empty_state(message: str) -> str:
    """Muted panel used for empty/invalid states instead of a bare warning."""
    return f'<div class="fsa-empty">{html.escape(message)}</div>'


def correlation_scale() -> str:
    """Static −1…+1 legend for the correlation heatmap.

    The heatmap keeps a fixed scale, so a small HTML legend is clearer (and
    more reliable across container widths) than a Plotly colour bar, whose
    tick labels can be clipped by the chart card.
    """
    stops = ", ".join(
        f"{colour} {int(stop * 100)}%" for stop, colour in DIVERGING
    )
    return (
        '<div class="fsa-scale">'
        '<span class="end">−1</span>'
        f'<span class="bar" style="background:linear-gradient(90deg,{stops})"></span>'
        '<span class="end">+1</span>'
        '<span class="cap">negative = moves opposite · 0 = unrelated · '
        "positive = moves together</span>"
        "</div>"
    )


def legend_rows(tickers: Sequence[str], names: dict[str, str]) -> str:
    """Sidebar legend: colour + ticker + bank name."""
    rows = "".join(
        f'<div class="fsa-legend-row">'
        f'<span class="sym" style="background:{ticker_color(t)}"></span>'
        f"<b>{html.escape(t)}</b><span>{html.escape(names.get(t, ''))}</span></div>"
        for t in tickers
    )
    return f'<div class="fsa-legend">{rows}</div>'


def brand_block(name: str = "Finance Stock Analytics",
                tagline: str = "Market & portfolio analytics") -> str:
    """Compact brand lockup for the sidebar."""
    return (
        '<div class="fsa-brand"><div class="fsa-mark">FS</div><div>'
        f'<div class="fsa-brand-name">{html.escape(name)}</div>'
        f'<div class="fsa-brand-sub">{html.escape(tagline)}</div>'
        "</div></div>"
    )


def sidebar_label(text: str) -> str:
    """Small uppercase group label inside the sidebar."""
    return f'<div class="fsa-sb-label">{html.escape(text)}</div>'


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = f"""
<style>
/* ---------- app shell ---------- */
.stApp {{
  background:
    radial-gradient(1100px 520px at 8% -12%, {rgba(ACCENT, 0.14)}, rgba(10,15,26,0) 62%),
    {BG};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ right: 0.5rem; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
[data-testid="stStatusWidget"] {{ display: none; }}
[data-testid="stSidebar"] {{
  background: {SIDEBAR};
  border-right: 1px solid {BORDER};
}}
[data-testid="stSidebarUserContent"] {{ padding-top: 1.1rem; }}
[data-testid="stMainBlockContainer"], .block-container {{
  padding-top: 1.6rem;
  padding-bottom: 3rem;
  max-width: 1480px;
}}

/* ---------- typography ---------- */
html, body {{ font-family: {FONT}; }}
h1, h2, h3, h4, h5 {{ color: {TEXT} !important; letter-spacing: -0.01em; }}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{ color: {TEXT_BODY}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
  color: {MUTED};
}}
[data-testid="stWidgetLabel"] p {{
  color: {TEXT_BODY};
  font-size: 0.82rem;
  font-weight: 500;
}}

/* ---------- tabs ---------- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: 0.25rem;
  border-bottom: 1px solid {GRID};
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  height: 2.6rem;
  padding: 0 1rem;
  background: transparent;
  color: {MUTED};
  font-size: 0.9rem;
  font-weight: 500;
  border-radius: 8px 8px 0 0;
}}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
  color: {TEXT};
  background: {SURFACE};
}}
[data-testid="stTabs"] [aria-selected="true"] {{
  color: {TEXT} !important;
  background: {SURFACE};
}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
  background: {ACCENT};
  height: 2px;
  border-radius: 2px;
}}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background: {GRID}; }}

/* ---------- chart + table cards ---------- */
.stPlotlyChart {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 10px 12px 2px 12px;
}}
[data-testid="stDataFrame"] {{
  border: 1px solid {BORDER};
  border-radius: 12px;
  overflow: hidden;
}}

/* ---------- buttons ---------- */
[data-testid="stDownloadButton"] button,
.stButton button {{
  background: {SURFACE_ALT};
  color: {TEXT};
  border: 1px solid {BORDER};
  border-radius: 9px;
  font-weight: 500;
  font-size: 0.82rem;
  padding: 0.38rem 0.9rem;
}}
[data-testid="stDownloadButton"] button:hover,
.stButton button:hover {{
  border-color: {ACCENT};
  color: #FFFFFF;
  background: {SURFACE_ALT};
}}

/* ---------- alerts / expanders ---------- */
[data-testid="stAlert"] {{ border-radius: 10px; }}
[data-testid="stExpander"] details {{
  border: 1px solid {BORDER};
  border-radius: 10px;
  background: {rgba(SURFACE, 0.6)};
}}
[data-testid="stExpander"] summary {{
  color: {MUTED};
  font-size: 0.85rem;
  font-weight: 500;
}}

/* ---------- selectors ---------- */
/* Streamlit ≥1.5x renders multiselect tags as [data-tag] spans (the older
   BaseWeb [data-baseweb="tag"] markup is kept as a fallback). */
[data-testid="stMultiSelect"] [data-tag],
[data-testid="stMultiSelect"] [data-baseweb="tag"] {{
  background: {SURFACE_ALT} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px;
  color: {TEXT} !important;
  height: 1.55rem;
}}
[data-testid="stMultiSelect"] [data-tag] span,
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {{
  color: {TEXT} !important;
  font-size: 0.76rem;
  font-weight: 500;
  letter-spacing: 0.01em;
}}
[data-testid="stMultiSelect"] [data-tag] button,
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {{
  color: {FAINT} !important;
}}
[data-testid="stMultiSelect"] [data-tag] button:hover {{
  color: {TEXT} !important;
}}

/* ---------- sidebar brand + labels ---------- */
.fsa-brand {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.1rem 0 0.7rem;
}}
.fsa-mark {{
  width: 32px; height: 32px;
  border-radius: 9px;
  display: grid; place-items: center;
  background: linear-gradient(140deg, {ACCENT}, #2DD4BF);
  color: #07101F;
  font-weight: 800;
  font-size: 0.78rem;
  letter-spacing: 0.02em;
}}
.fsa-brand-name {{
  color: {TEXT}; font-size: 0.92rem; font-weight: 700; line-height: 1.15;
}}
.fsa-brand-sub {{
  color: {FAINT}; font-size: 0.66rem; letter-spacing: 0.1em;
  text-transform: uppercase; margin-top: 0.15rem;
}}
.fsa-sb-label {{
  font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: {FAINT}; font-weight: 600;
  margin: 1.05rem 0 0.3rem;
}}
.fsa-legend {{ display: flex; flex-direction: column; gap: 0.28rem; }}
.fsa-legend-row {{
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.76rem; color: {MUTED};
}}
.fsa-legend-row .sym {{
  width: 9px; height: 9px; border-radius: 2px; flex: 0 0 auto;
}}
.fsa-legend-row b {{
  color: {TEXT}; font-weight: 600; font-size: 0.76rem; min-width: 2.1rem;
}}

/* ---------- header ---------- */
.fsa-hero {{
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 1rem; padding: 0.1rem 0 0.9rem;
}}
.fsa-title {{
  margin: 0; font-size: 1.68rem; font-weight: 700; line-height: 1.18;
  letter-spacing: -0.02em; color: {TEXT};
}}
.fsa-subtitle {{
  margin: 0.35rem 0 0; color: {MUTED}; font-size: 0.93rem; max-width: 64ch;
}}
.fsa-pill {{
  display: inline-flex; align-items: center; gap: 0.45rem;
  padding: 0.32rem 0.72rem; border-radius: 999px;
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; border: 1px solid; white-space: nowrap;
}}
.fsa-pill .dot {{ width: 7px; height: 7px; border-radius: 50%; }}
.fsa-pill.live {{
  color: {POSITIVE}; border-color: {rgba(POSITIVE, 0.35)};
  background: {rgba(POSITIVE, 0.08)};
}}
.fsa-pill.live .dot {{ background: {POSITIVE}; }}
.fsa-pill.cache {{
  color: {ACCENT}; border-color: {rgba(ACCENT, 0.35)};
  background: {rgba(ACCENT, 0.08)};
}}
.fsa-pill.cache .dot {{ background: {ACCENT}; }}
.fsa-pill.mock {{
  color: {WARNING}; border-color: {rgba(WARNING, 0.4)};
  background: {rgba(WARNING, 0.09)};
}}
.fsa-pill.mock .dot {{ background: {WARNING}; }}

/* ---------- metadata chips ---------- */
.fsa-chips {{
  display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0 0 0.6rem;
}}
.fsa-chip {{
  display: inline-flex; align-items: baseline; gap: 0.45rem;
  padding: 0.32rem 0.65rem;
  border: 1px solid {BORDER}; background: {SURFACE};
  border-radius: 8px; font-size: 0.78rem; color: {MUTED};
}}
.fsa-chip .k {{
  font-size: 0.64rem; letter-spacing: 0.1em; text-transform: uppercase;
  color: {FAINT};
}}
.fsa-chip .v {{ color: {TEXT}; font-weight: 600; }}
.fsa-chip .v.pos {{ color: {POSITIVE}; }}
.fsa-chip .v.neg {{ color: {NEGATIVE}; }}
.fsa-chip .v.warn {{ color: {WARNING}; }}

/* ---------- KPI cards ---------- */
.fsa-kpis {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(158px, 1fr));
  gap: 0.6rem;
  margin: 0.15rem 0 1.1rem;
}}
.fsa-kpi {{
  position: relative; overflow: hidden;
  background: linear-gradient(180deg, #121C2E 0%, #0F1828 100%);
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 0.72rem 0.85rem 0.78rem;
}}
.fsa-kpi::before {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0;
  width: 2px; background: {ACCENT}; opacity: 0.45;
}}
.fsa-kpi-label {{
  display: flex; align-items: center; gap: 0.4rem;
  font-size: 0.65rem; letter-spacing: 0.11em; text-transform: uppercase;
  color: {FAINT}; font-weight: 600;
}}
.fsa-swatch {{
  width: 8px; height: 8px; border-radius: 2px; display: inline-block;
  flex: 0 0 auto;
}}
.fsa-kpi-value {{
  margin-top: 0.3rem;
  font-size: 1.3rem; font-weight: 650; line-height: 1.1;
  color: {TEXT};
  font-variant-numeric: tabular-nums;
}}
.fsa-kpi-sub {{
  margin-top: 0.22rem; font-size: 0.74rem; color: {MUTED};
}}
.fsa-kpi.is-pos .fsa-kpi-value {{ color: {POSITIVE}; }}
.fsa-kpi.is-neg .fsa-kpi-value {{ color: {NEGATIVE}; }}
.fsa-kpi.is-acc .fsa-kpi-value {{ color: {ACCENT}; }}

/* ---------- sections ---------- */
.fsa-sec {{ margin: 1.15rem 0 0.5rem; }}
.fsa-sec h3 {{
  margin: 0; font-size: 1.01rem; font-weight: 650; color: {TEXT};
}}
.fsa-sec p {{
  margin: 0.22rem 0 0; font-size: 0.81rem; color: {MUTED};
  max-width: 82ch;
}}

/* ---------- correlation scale legend ---------- */
.fsa-scale {{
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 0.5rem; margin: 0 0 0.6rem;
  font-size: 0.74rem; color: {MUTED};
}}
.fsa-scale .bar {{
  width: 190px; height: 8px; border-radius: 4px;
  border: 1px solid {BORDER};
}}
.fsa-scale .end {{ color: {TEXT_BODY}; font-variant-numeric: tabular-nums; }}
.fsa-scale .cap {{ color: {FAINT}; }}

/* ---------- empty state ---------- */
.fsa-empty {{
  border: 1px dashed {BORDER};
  border-radius: 12px;
  background: {rgba(SURFACE, 0.55)};
  color: {MUTED};
  padding: 1.05rem 1.2rem;
  font-size: 0.86rem;
  line-height: 1.45;
}}

/* ---------- responsive ---------- */
@media (max-width: 980px) {{
  .fsa-hero {{ flex-direction: column; }}
  .fsa-title {{ font-size: 1.45rem; }}
  .fsa-kpis {{ grid-template-columns: repeat(auto-fit, minmax(136px, 1fr)); }}
}}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"], .block-container {{
    padding-left: 0.85rem; padding-right: 0.85rem;
  }}
  .fsa-kpi-value {{ font-size: 1.12rem; }}
  .fsa-title {{ font-size: 1.35rem; }}
}}
</style>
"""


# ---------------------------------------------------------------------------
# Plotly theme
# ---------------------------------------------------------------------------
def register_plotly_template() -> str:
    """Register (idempotently) and return the dashboard's Plotly template name."""
    import plotly.graph_objects as go
    import plotly.io as pio

    if PLOTLY_TEMPLATE in pio.templates:
        return PLOTLY_TEMPLATE

    axis = dict(
        gridcolor=GRID,
        zerolinecolor=GRID,
        linecolor=BORDER,
        tickfont=dict(color=MUTED, size=10.5),
        # standoff keeps the rotated axis title clear of wide tick labels
        # ("$350", "-30.0%") even in narrow columns.
        title=dict(font=dict(color=MUTED, size=11), standoff=10),
        automargin=True,
    )

    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=TEXT_BODY),
        colorway=[ticker_color(t) for t in TICKER_COLORS],
        margin=dict(l=10, r=14, t=34, b=10),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=SURFACE_ALT,
            bordercolor=BORDER,
            font=dict(color=TEXT, size=12),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=MUTED),
            itemsizing="constant",
        ),
        xaxis={**axis, "showgrid": False},
        yaxis={**axis, "showgrid": True},
        dragmode="zoom",
    )
    pio.templates[PLOTLY_TEMPLATE] = template
    return PLOTLY_TEMPLATE
