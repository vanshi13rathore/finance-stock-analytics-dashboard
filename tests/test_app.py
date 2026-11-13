"""App-level tests: drive the real Streamlit script with ``AppTest``.

These cover the wiring a frontend rewrite can break without touching a single
financial formula — date filtering, ticker selection, slider reruns, the
synthetic-data disclosure and the invalid-input guards.

They read the cached CSV in ``data/`` (no network access).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"


def run_app() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_markdown(at: AppTest) -> str:
    return " ".join(block.value for block in at.markdown)


def slider(at: AppTest, label: str):
    """Look sliders up by label — element order is rendering order."""
    return next(item for item in at.slider if item.label == label)


# ---------------------------------------------------------------------------
# Default render
# ---------------------------------------------------------------------------
def test_default_dashboard_renders_every_tab():
    at = run_app()

    assert [tab.label for tab in at.tabs] == [
        "Prices",
        "Risk",
        "Correlations",
        "Portfolio",
    ]
    assert len(at.get("plotly_chart")) == 13
    assert len(at.dataframe) == 5

    markdown = all_markdown(at)
    assert "Finance Stock Analytics" in markdown
    assert "Historical performance, risk and portfolio analysis" in markdown
    assert markdown.count('class="fsa-kpi is-') == 19  # 6 + 4 + 3 + 3 + 3
    assert "Yahoo Finance · cached" in markdown or "Yahoo Finance · live" in markdown
    assert not at.error


def test_header_reports_window_sessions_and_basis():
    at = run_app()
    markdown = all_markdown(at)

    assert "03 Jan 2006 → 31 Dec 2015" in markdown  # Yahoo end date is exclusive
    assert "2,517" in markdown
    assert "Adj Close" in markdown
    # Factual provenance only: prices are loaded, never independently verified.
    assert (
        "Historical data loaded" in markdown
        or "Cached historical data" in markdown
    )
    assert "Verified" not in markdown


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
def test_date_filter_changes_the_window_and_row_count():
    at = run_app()
    before_charts = len(at.get("plotly_chart"))

    at.date_input[1].set_value(dt.date(2012, 1, 1)).run()
    assert not at.exception

    markdown = all_markdown(at)
    assert "30 Dec 2011" in markdown  # last close before the exclusive end date
    assert "2,517" not in markdown
    assert len(at.get("plotly_chart")) == before_charts  # same charts, less data


def test_single_bank_selection_keeps_prices_and_empties_portfolio():
    at = run_app()
    at.multiselect[0].set_value(["BAC"]).run()
    assert not at.exception

    markdown = all_markdown(at)
    assert "Portfolio simulation needs at least two banks" in markdown
    assert "Correlation analysis needs at least two banks" in markdown
    assert "BAC daily returns" in markdown  # focus chart still renders


def test_two_bank_selection_still_simulates():
    at = run_app()
    at.multiselect[0].set_value(["JPM", "MS"]).run()
    assert not at.exception

    assert len(at.get("plotly_chart")) == 13
    captions = " ".join(c.value for c in at.caption)
    assert "random long-only portfolios" in captions


def test_risk_free_slider_reruns_analysis():
    at = run_app()
    before = all_markdown(at)

    slider(at, "Risk-free rate (%)").set_value(5.0).run()
    assert not at.exception

    after = all_markdown(at)
    assert after != before  # higher risk-free rate lowers every Sharpe ratio
    assert "Sharpe 0.36" in before and "Sharpe 0.36" not in after


def test_moving_average_windows_must_differ():
    at = run_app()
    slider(at, "Short moving average").set_value(50).run()  # short == long
    assert not at.exception

    assert any("must be different" in err.value for err in at.error)


def test_invalid_date_range_is_reported_not_traced():
    at = run_app()
    at.date_input[0].set_value(dt.date(2016, 1, 1)).run()
    assert not at.exception

    assert any("must be before end date" in err.value for err in at.error)
    assert len(at.get("plotly_chart")) == 0


def test_empty_selection_is_reported():
    at = run_app()
    at.multiselect[0].set_value([]).run()
    assert not at.exception

    assert any("at least one bank" in err.value for err in at.error)


# ---------------------------------------------------------------------------
# Synthetic data disclosure
# ---------------------------------------------------------------------------
def test_synthetic_mode_is_explicitly_disclosed():
    at = run_app()
    at.checkbox[0].check().run()
    assert not at.exception

    markdown = all_markdown(at)
    warnings = " ".join(w.value for w in at.warning)
    assert "Synthetic demo data" in markdown
    assert "not" in warnings and "market data" in warnings
    assert "Simulated" in markdown
    assert len(at.get("plotly_chart")) == 13


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
def test_download_buttons_are_present():
    at = run_app()
    labels = [button.label for button in at.get("download_button")]
    assert "Download risk metrics (CSV)" in labels
    assert "Download correlations (CSV)" in labels
    assert "Download allocations (CSV)" in labels
    assert "Download price data (CSV)" in labels


# ---------------------------------------------------------------------------
# Portfolio terminology
# ---------------------------------------------------------------------------
def test_portfolio_tab_labels_the_simulation_honestly():
    """The tab must describe a random simulation, not a solved efficient frontier."""
    at = run_app()
    markdown = all_markdown(at)
    # Strip markdown emphasis and line breaks so the wording itself is asserted.
    flat = " ".join(markdown.replace("*", "").split())

    assert "Monte Carlo Portfolio Simulation — Risk vs. Return" in flat
    assert "randomly generated long-only portfolio" in flat
    assert "not an optimised frontier" in flat
    assert "not a solved efficient frontier" in flat
    assert "not predictions of future returns" in flat
    assert "no transaction" in flat and "rebalancing" in flat
