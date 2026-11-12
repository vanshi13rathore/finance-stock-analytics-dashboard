"""Tests for :mod:`src.charts`.

The chart builders are pure functions of pandas objects, so they can be
checked without a browser or a Streamlit server. These tests pin the parts a
redesign can silently break: trace identity, the shared ticker palette, fixed
scales and the empty-input paths.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src import charts, metrics, portfolio, theme

TICKERS = ["BAC", "JPM"]


@pytest.fixture
def prices() -> pd.DataFrame:
    """Two synthetic price series that overlap the 2008 crisis window."""
    index = pd.bdate_range("2007-06-01", periods=400)  # spans 2008–09
    rng = np.random.default_rng(7)
    frame = {
        ticker: 40.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.02, len(index))))
        for ticker in TICKERS
    }
    return pd.DataFrame(frame, index=index)


@pytest.fixture
def returns(prices: pd.DataFrame) -> pd.DataFrame:
    return metrics.daily_returns(prices)


@pytest.fixture
def summary(prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    return metrics.summary_table(prices, returns)


def trace_names(fig: go.Figure) -> list[str]:
    return [str(trace.name) for trace in fig.data]


# ---------------------------------------------------------------------------
# Prices tab
# ---------------------------------------------------------------------------
def test_price_history_one_trace_per_ticker_in_palette_colours(prices):
    fig = charts.price_history(prices)
    assert trace_names(fig) == TICKERS
    assert [t.line.color for t in fig.data] == [
        theme.ticker_color(t) for t in TICKERS
    ]
    assert fig.layout.yaxis.tickprefix == "$"
    assert fig.layout.yaxis.title.text == "Price (USD)"
    assert all("$" in t.hovertemplate for t in fig.data)


def test_price_history_log_scale(prices):
    fig = charts.price_history(prices, log_scale=True)
    assert fig.layout.yaxis.type == "log"
    assert "log" in fig.layout.yaxis.title.text.lower()


def test_price_history_shades_the_crisis_window_only_when_present(prices):
    assert any(shape.type == "rect" for shape in charts.price_history(prices).layout.shapes)

    calm = pd.DataFrame(
        prices.to_numpy(),
        index=pd.bdate_range("2012-01-02", periods=len(prices)),
        columns=prices.columns,
    )
    assert not any(shape.type == "rect" for shape in charts.price_history(calm).layout.shapes)


def test_normalized_rebases_and_marks_the_base(prices):
    fig = charts.normalized(metrics.normalized_prices(prices))
    assert trace_names(fig) == TICKERS
    assert any(shape.y0 == 100 for shape in fig.layout.shapes)
    assert "100" in fig.layout.yaxis.title.text


def test_cumulative_marks_one_dollar(prices, returns):
    fig = charts.cumulative(metrics.cumulative_returns(returns))
    assert trace_names(fig) == TICKERS
    assert any(shape.y0 == 1 for shape in fig.layout.shapes)
    assert fig.layout.yaxis.tickprefix == "$"


def test_moving_averages_labels_price_with_the_ticker_not_close(prices):
    ma = metrics.moving_averages(prices["BAC"], 30, 50)
    assert list(ma.columns)[0] == "Close"

    fig = charts.moving_averages(ma, ticker="BAC")
    assert trace_names(fig) == ["BAC", "30 Day MA", "50 Day MA"]
    # the price line must use BAC's identity colour, not a fallback colour
    assert fig.data[0].line.color == theme.ticker_color("BAC")


def test_daily_returns_colours_up_and_down_days(returns):
    fig = charts.daily_returns(returns, "BAC")
    colours = list(fig.data[0].marker.color)
    values = returns["BAC"].to_numpy()
    assert len(colours) == len(values)
    assert colours == [theme.POSITIVE if v >= 0 else theme.NEGATIVE for v in values]
    assert theme.POSITIVE in colours and theme.NEGATIVE in colours
    assert fig.layout.yaxis.tickformat == ".1%"


# ---------------------------------------------------------------------------
# Risk tab
# ---------------------------------------------------------------------------
def test_risk_return_uses_symbols_and_rich_hover(summary):
    fig = charts.risk_return(summary, 0.02)
    trace = fig.data[0]
    assert list(trace.marker.symbol) == [
        theme.ticker_symbol(str(t)) for t in summary.index
    ]
    assert list(trace.marker.color) == [
        theme.ticker_color(str(t)) for t in summary.index
    ]
    assert "Sortino" in trace.hovertemplate
    assert "Max drawdown" in trace.hovertemplate
    assert fig.layout.xaxis.tickformat == ".0%"


def test_drawdown_chart_is_an_underwater_chart(prices):
    fig = charts.drawdown(metrics.drawdown_series(prices))
    assert trace_names(fig) == TICKERS
    assert all(trace.fill == "tozeroy" for trace in fig.data)
    assert fig.layout.yaxis.tickformat == ".0%"


def test_rolling_volatility_is_annualized_percent(returns):
    fig = charts.rolling_volatility(metrics.rolling_volatility(returns, 30), 30)
    assert trace_names(fig) == TICKERS
    assert fig.layout.yaxis.tickformat == ".0%"
    assert "Annualized" in fig.layout.yaxis.title.text


def test_return_boxes_one_box_per_ticker(returns):
    fig = charts.return_boxes(returns)
    assert trace_names(fig) == TICKERS
    assert all(trace.type == "box" for trace in fig.data)


# ---------------------------------------------------------------------------
# Correlations tab
# ---------------------------------------------------------------------------
def test_correlation_heatmap_is_fixed_to_minus_one_plus_one(returns):
    corr = metrics.correlation_matrix(returns)
    fig = charts.correlation_heatmap(corr)
    heatmap = fig.data[0]

    assert isinstance(heatmap, go.Heatmap)
    assert heatmap.zmin == -1 and heatmap.zmax == 1 and heatmap.zmid == 0
    assert np.allclose(heatmap.z, corr.to_numpy())
    assert list(heatmap.x) == list(corr.columns)
    assert heatmap.texttemplate == "%{text:.2f}"
    assert "ρ" in heatmap.hovertemplate  # Greek rho, not an ASCII "p"
    assert [[stop[0], stop[1]] for stop in heatmap.colorscale] == theme.DIVERGING
    # the −1…+1 legend is HTML (theme.correlation_scale), not a clipped colorbar
    assert heatmap.showscale is False


# ---------------------------------------------------------------------------
# Portfolio tab
# ---------------------------------------------------------------------------
def test_portfolio_cloud_marks_max_sharpe_and_min_volatility(returns, summary):
    simulations, best = portfolio.random_portfolios(returns, n_portfolios=400, seed=3)
    assets = pd.DataFrame(
        {
            "return": summary["Ann. Return"].reindex(returns.columns),
            "volatility": summary["Ann. Volatility"].reindex(returns.columns),
        }
    ).dropna()

    fig = charts.portfolio_cloud(
        simulations,
        max_sharpe=(best.max_sharpe_vol, best.max_sharpe_return),
        min_vol=(best.min_vol_vol, best.min_vol_return),
        assets=assets,
    )
    names = trace_names(fig)
    assert names == ["Simulated portfolios", "Single banks", "Max Sharpe", "Min volatility"]
    assert len(fig.layout.annotations) == 2
    assert "Sharpe" in fig.data[0].hovertemplate
    assert fig.layout.xaxis.tickformat == ".0%"


def test_weights_bar_labels_percentages_and_sums_to_one():
    weights = pd.Series({"BAC": 0.4, "JPM": 0.35, "C": 0.25})
    fig = charts.weights_bar(weights)
    bar = fig.data[0]

    assert bar.orientation == "h"
    assert list(bar.text) == ["25.0%", "35.0%", "40.0%"]  # sorted ascending
    assert abs(sum(weights) - 1.0) < 1e-9
    assert fig.layout.xaxis.tickformat == ".0%"
    # colours follow ticker identity, not bar order
    colours = dict(zip(bar.y, bar.marker.color))
    assert colours["JPM"] == theme.ticker_color("JPM")


# ---------------------------------------------------------------------------
# Shared layout + empty input safety
# ---------------------------------------------------------------------------
def test_every_chart_applies_the_dashboard_template_and_fixed_height(prices, returns):
    figures = [
        charts.price_history(prices),
        charts.normalized(metrics.normalized_prices(prices)),
        charts.cumulative(metrics.cumulative_returns(returns)),
        charts.daily_returns(returns, "BAC"),
        charts.moving_averages(metrics.moving_averages(prices["BAC"]), "BAC"),
        charts.drawdown(metrics.drawdown_series(prices)),
        charts.rolling_volatility(metrics.rolling_volatility(returns)),
        charts.return_boxes(returns),
        charts.correlation_heatmap(metrics.correlation_matrix(returns)),
    ]
    for fig in figures:
        assert fig.layout.height and fig.layout.height > 100
        assert fig.layout.template is not None
        assert fig.layout.paper_bgcolor in (None, "rgba(0,0,0,0)")
        assert len(fig.data) > 0


def test_empty_inputs_do_not_raise(prices):
    empty = pd.DataFrame()
    empty_prices = prices.iloc[:0]
    empty_summary = pd.DataFrame(
        columns=["Ann. Return", "Ann. Volatility", "Sharpe", "Sortino", "Max Drawdown"]
    )

    figs = [
        charts.price_history(empty_prices),
        charts.normalized(empty_prices),
        charts.cumulative(empty_prices),
        charts.daily_returns(empty, "BAC"),
        charts.moving_averages(empty, "BAC"),
        charts.drawdown(empty_prices),
        charts.rolling_volatility(empty),
        charts.return_boxes(empty),
        charts.risk_return(empty_summary),
        charts.correlation_heatmap(empty),
        charts.portfolio_cloud(
            pd.DataFrame(columns=["return", "volatility", "sharpe"])
        ),
        charts.weights_bar(pd.Series(dtype=float)),
    ]
    for fig in figs:
        assert isinstance(fig, go.Figure)
