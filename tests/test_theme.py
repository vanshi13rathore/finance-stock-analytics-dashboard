"""Tests for :mod:`src.theme` — palette, formatters and HTML fragments.

These are display-only helpers: nothing here touches financial maths, so the
assertions focus on stability (one colour per ticker), NaN safety and HTML
escaping (labels come from user-facing config).
"""

from __future__ import annotations

import math

import pytest

from src import theme


# ---------------------------------------------------------------------------
# Ticker identity
# ---------------------------------------------------------------------------
def test_every_bank_has_a_unique_hex_colour():
    colours = [theme.ticker_color(t) for t in theme.TICKER_COLORS]
    assert len(colours) == len(theme.TICKER_COLORS) == 6
    assert len(set(colours)) == 6
    for colour in colours:
        assert colour.startswith("#") and len(colour) == 7


def test_ticker_colour_is_stable_across_calls():
    assert theme.ticker_color("JPM") == theme.ticker_color("JPM")


def test_unknown_ticker_gets_a_deterministic_fallback_colour():
    first = theme.ticker_color("XYZ")
    assert first == theme.ticker_color("XYZ")
    assert first in theme.FALLBACK_COLORS


def test_ticker_symbols_are_distinct_enough_for_accessibility():
    symbols = [theme.ticker_symbol(t) for t in theme.TICKER_COLORS]
    assert len(set(symbols)) >= 5  # colour is never the only channel
    assert theme.ticker_symbol("NOT_A_BANK") == "circle"


def test_tint_mixes_towards_white_and_clamps():
    assert theme.tint("#000000", 0.0) == "#000000"
    assert theme.tint("#000000", 1.0) == "#FFFFFF"
    assert theme.tint("#000000", 5.0) == "#FFFFFF"  # clamped, not overflow


def test_rgba_formats_alpha():
    assert theme.rgba("#FF0000", 0.5) == "rgba(255,0,0,0.5)"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
def test_fmt_pct_basic_and_signed():
    assert theme.fmt_pct(0.1234) == "12.3%"
    assert theme.fmt_pct(0.1234, 2) == "12.34%"
    assert theme.fmt_pct(0.1234, 1, signed=True) == "+12.3%"
    assert theme.fmt_pct(-0.05, 1, signed=True) == "-5.0%"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "n/a"])
def test_formatters_are_nan_safe(bad):
    assert theme.fmt_pct(bad) == "—"
    assert theme.fmt_ratio(bad) == "—"
    assert theme.fmt_money(bad) == "—"
    assert theme.fmt_int(bad) == "—"


def test_fmt_ratio_and_money():
    assert theme.fmt_ratio(0.3647) == "0.36"
    assert theme.fmt_ratio(-0.1111, 2, signed=True) == "-0.11"
    assert theme.fmt_money(2.2245) == "$2.22"
    assert theme.fmt_money(1234.5, 0) == "$1,234"


def test_fmt_int_groups_thousands():
    assert theme.fmt_int(2517) == "2,517"


def test_tone_of():
    assert theme.tone_of(0.1) == "pos"
    assert theme.tone_of(-0.1) == "neg"
    assert theme.tone_of(0) == "neutral"
    assert theme.tone_of(float("nan")) == "neutral"


# ---------------------------------------------------------------------------
# HTML fragments
# ---------------------------------------------------------------------------
def test_kpi_grid_renders_cards_with_tone_and_swatch():
    html = theme.kpi_grid(
        [
            theme.KpiCard(label="WFC", value="+121.9%", sub="vol 47.9%", tone="pos", swatch="#9CCC65"),
            theme.KpiCard(label="C", value="-87.8%", tone="neg", tooltip="Citigroup"),
        ]
    )
    assert html.count('class="fsa-kpi is-') == 2
    assert "is-pos" in html and "is-neg" in html
    assert 'style="background:#9CCC65"' in html
    assert 'title="Citigroup"' in html


def test_kpi_grid_escapes_labels():
    html = theme.kpi_grid([theme.KpiCard(label="<script>x</script>", value="1")])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_chips_render_tone_classes_only_for_known_tones():
    html = theme.chips([("SESSIONS", "2,517"), ("STATUS", "Simulated", "warn")])
    assert "fsa-chip" in html
    assert 'class="v warn"' in html
    assert html.count("<span") >= 4


def test_status_pill_labels_by_source():
    assert "live" in theme.status_pill("yahoo").lower()
    assert "cached" in theme.status_pill("cache").lower()
    assert "synthetic" in theme.status_pill("synthetic").lower()
    assert "fsa-pill mock" in theme.status_pill("synthetic")


def test_hero_escapes_title_and_includes_subtitle():
    html = theme.hero("A & B", "Sub")
    assert "A &amp; B" in html
    assert "Sub" in html
    assert "fsa-hero" in html


def test_section_html_description_optional():
    assert "fsa-sec" in theme.section_html(theme.Section("Title"))
    assert "<p>" not in theme.section_html(theme.Section("Title"))
    assert "<p>Desc</p>" in theme.section_html(theme.Section("Title", "Desc"))


def test_filter_rows_and_empty_state():
    rows = theme.legend_rows(["BAC", "C"], {"BAC": "Bank of America"})
    assert rows.count("fsa-legend-row") == 2
    assert "Bank of America" in rows
    assert "fsa-empty" in theme.empty_state("no data")


# ---------------------------------------------------------------------------
# CSS + Plotly template
# ---------------------------------------------------------------------------
def test_css_uses_the_palette_and_supports_current_multiselect_markup():
    css = theme.CSS
    assert theme.BG in css
    assert theme.TICKER_COLORS["JPM"] in css or theme.ACCENT in css
    # Streamlit ≥1.5x tags carry data-tag; the old BaseWeb attr stays as fallback
    assert "[data-tag]" in css
    assert 'data-baseweb="tag"' in css


def test_plotly_template_is_registered_once():
    import plotly.io as pio

    name = theme.register_plotly_template()
    assert name == theme.PLOTLY_TEMPLATE
    assert name in pio.templates
    assert theme.register_plotly_template() == name

    layout = pio.templates[name].layout
    assert layout.paper_bgcolor == "rgba(0,0,0,0)"  # chart cards supply the panel
    assert layout.yaxis.automargin is True
    assert layout.yaxis.title.standoff == 10
    assert list(layout.colorway)[:6] == [
        theme.ticker_color(t) for t in theme.TICKER_COLORS
    ]


def test_plotly_config_disables_toolbar_but_keeps_scroll_zoom():
    assert theme.PLOTLY_CONFIG["displayModeBar"] is False
    assert theme.PLOTLY_CONFIG["scrollZoom"] is True
    assert theme.PLOTLY_CONFIG["responsive"] is True


def test_correlation_scale_legend_describes_the_fixed_range():
    html = theme.correlation_scale()

    assert "fsa-scale" in html
    assert "−1" in html and "+1" in html
    assert "linear-gradient" in html
    assert theme.DIVERGING[0][1] in html and theme.DIVERGING[-1][1] in html
    assert "unrelated" in html  # zero is described, not just coloured


def test_diverging_scale_is_symmetric_around_zero():
    stops = [stop[0] for stop in theme.DIVERGING]
    assert stops == sorted(stops)
    assert stops[0] == 0.0 and stops[-1] == 1.0 and 0.5 in stops


def test_palette_contrast_is_reasonable():
    """Text colours must be clearly lighter than the card background."""

    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def ratio(a: str, b: str) -> float:
        la, lb = luminance(a), luminance(b)
        lighter, darker = max(la, lb), min(la, lb)
        return (lighter + 0.05) / (darker + 0.05)

    assert ratio(theme.TEXT, theme.SURFACE) >= 7.0
    assert ratio(theme.MUTED, theme.SURFACE) >= 4.5
    # FAINT is used for 0.65rem uppercase KPI labels, so it must clear AA too
    assert ratio(theme.FAINT, theme.SURFACE) >= 4.5
    assert math.isfinite(ratio(theme.TEXT_BODY, theme.BG))
