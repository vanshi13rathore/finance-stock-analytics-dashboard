"""Unit tests for src.metrics, src.portfolio, src.data and src.plots.

Everything here uses small deterministic fixtures — no network access.
Expected values are derived by hand from the mathematical definitions, not by
calling the function under test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend before pyplot is imported anywhere

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import data as data_mod
from src import metrics, plots, portfolio


@pytest.fixture()
def prices() -> pd.DataFrame:
    """Deterministic 2-ticker price fixture (60 business days)."""
    return data_mod.generate_synthetic_prices(
        ["AAA", "BBB"], start="2020-01-01", end="2020-03-31", seed=7
    )


@pytest.fixture()
def returns(prices: pd.DataFrame) -> pd.DataFrame:
    return metrics.daily_returns(prices)


# --- returns ---------------------------------------------------------------
def test_daily_returns_shape(prices, returns):
    assert len(returns) == len(prices) - 1
    assert list(returns.columns) == ["AAA", "BBB"]


def test_daily_returns_values():
    px = pd.DataFrame({"A": [100.0, 110.0, 99.0]})
    r = metrics.daily_returns(px)
    assert r["A"].tolist() == pytest.approx([0.10, -0.10])


def test_cumulative_returns():
    r = pd.DataFrame({"A": [0.10, -0.10]})
    cum = metrics.cumulative_returns(r)
    assert cum["A"].tolist() == pytest.approx([1.10, 0.99])


def test_normalized_prices(prices):
    norm = metrics.normalized_prices(prices)
    assert (norm.iloc[0] == 100.0).all()
    assert (norm > 0).all().all()


# --- risk / reward -----------------------------------------------------------
def test_annualized_volatility_matches_manual(returns):
    expected = returns.std() * np.sqrt(252)
    pd.testing.assert_series_equal(
        metrics.annualized_volatility(returns), expected, check_names=False
    )


def test_sharpe_positive_for_uptrend():
    rng = np.random.default_rng(0)
    r = pd.DataFrame({"A": 0.01 + 0.001 * rng.standard_normal(500)})
    assert metrics.sharpe_ratio(r)["A"] > 2.0


def test_sharpe_nan_for_flat_series():
    r = pd.DataFrame({"A": np.zeros(100)})
    assert np.isnan(metrics.sharpe_ratio(r)["A"])


def test_sortino_ignores_upside():
    r = pd.DataFrame({"A": [0.05, 0.05, -0.01, -0.01]})
    assert metrics.sortino_ratio(r)["A"] > metrics.sharpe_ratio(r)["A"]


# --- drawdown / tail risk ------------------------------------------------------
def test_max_drawdown_known_series():
    px = pd.DataFrame({"A": [100.0, 120.0, 90.0, 110.0]})
    assert metrics.max_drawdown(px)["A"] == pytest.approx(-0.25)


def test_drawdown_never_positive(prices):
    dd = metrics.drawdown_series(prices)
    assert (dd <= 1e-12).all().all()


def test_var_cvar_ordering(returns):
    var = metrics.value_at_risk(returns)
    cvar = metrics.conditional_var(returns)
    assert (cvar <= var).all()  # expected shortfall is worse than VaR
    assert (var < 0).all()


# --- helpers -------------------------------------------------------------------
def test_rolling_volatility_window(returns):
    rv = metrics.rolling_volatility(returns, window=10)
    assert rv.iloc[:9].isna().all().all()
    assert rv.iloc[9:].notna().all().all()


def test_moving_averages_columns(prices):
    ma = metrics.moving_averages(prices["AAA"], short=5, long=10)
    assert list(ma.columns) == ["Close", "5 Day MA", "10 Day MA"]
    assert ma["5 Day MA"].iloc[:4].isna().all()


def test_correlation_matrix_properties(returns):
    corr = metrics.correlation_matrix(returns)
    assert corr.shape == (2, 2)
    assert np.allclose(np.diag(corr), 1.0)
    assert corr.equals(corr.T)


def test_best_worst_days(prices, returns):
    bw = metrics.best_worst_days(returns)
    assert list(bw.columns) == [
        "best_day_return", "best_day_date",
        "worst_day_return", "worst_day_date",
    ]
    assert (bw["best_day_return"] >= bw["worst_day_return"]).all()


def test_summary_table_sorted_by_sharpe(prices, returns):
    summary = metrics.summary_table(prices, returns)
    assert summary["Sharpe"].is_monotonic_decreasing
    assert set(summary.columns) >= {
        "Ann. Return", "Ann. Volatility", "Sharpe",
        "Max Drawdown", "Growth of $1",
    }


# --- portfolio -------------------------------------------------------------------
def test_portfolio_performance_known_case():
    mean = pd.Series({"A": 0.001, "B": 0.002})
    cov = pd.DataFrame(np.eye(2) * 0.0001, index=["A", "B"], columns=["A", "B"])
    ret, vol, sharpe = portfolio.portfolio_performance(
        np.array([0.5, 0.5]), mean, cov, risk_free_rate=0.0
    )
    assert ret == pytest.approx(0.0015 * 252)
    assert vol == pytest.approx(np.sqrt(0.5 * 0.0001) * np.sqrt(252))
    assert sharpe == pytest.approx(ret / vol)


def test_random_portfolios_weights_sum_to_one(returns):
    sims, best = portfolio.random_portfolios(returns, n_portfolios=200, seed=1)
    assert len(sims) == 200
    assert best.max_sharpe_weights.sum() == pytest.approx(1.0)
    assert best.min_vol_weights.sum() == pytest.approx(1.0)
    assert (best.max_sharpe_weights >= 0).all()
    assert sims["sharpe"].max() == pytest.approx(best.max_sharpe_ratio)


def test_random_portfolios_reproducible(returns):
    sims1, _ = portfolio.random_portfolios(returns, n_portfolios=50, seed=3)
    sims2, _ = portfolio.random_portfolios(returns, n_portfolios=50, seed=3)
    pd.testing.assert_frame_equal(sims1, sims2)


# --- data ------------------------------------------------------------------------
def _fake_raw(layout: str) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=5)
    if layout == "ticker_first":
        cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["Open", "Close"]])
    else:
        cols = pd.MultiIndex.from_product([["Open", "Close"], ["AAA", "BBB"]])
    return pd.DataFrame(np.arange(20).reshape(5, 4).astype(float),
                        index=idx, columns=cols)


@pytest.mark.parametrize("layout", ["ticker_first", "price_first"])
def test_extract_close_handles_both_yfinance_layouts(layout):
    close = data_mod.extract_close(_fake_raw(layout))
    assert list(close.columns) == ["AAA", "BBB"]
    assert len(close) == 5


def test_generate_synthetic_is_deterministic():
    a = data_mod.generate_synthetic_prices(["BAC", "C"], seed=42)
    b = data_mod.generate_synthetic_prices(["BAC", "C"], seed=42)
    pd.testing.assert_frame_equal(a, b)
    assert (a > 0).all().all()
    assert len(a) > 2000  # ~10 years of business days


def test_clean_prices_fills_small_gaps():
    idx = pd.bdate_range("2020-01-01", periods=10)
    px = pd.DataFrame({"A": np.arange(10, dtype=float)}, index=idx)
    px.iloc[3:5] = np.nan
    with pytest.warns(UserWarning, match="missing price"):
        cleaned = data_mod.clean_prices(px)
    assert cleaned.isna().sum().sum() == 0


# --- Phase 1 regression tests: financial definitions ----------------------------
def test_daily_returns_are_per_ticker_and_leak_no_fills():
    px = pd.DataFrame({"A": [100.0, 110.0], "B": [50.0, 45.0]})
    r = metrics.daily_returns(px)
    assert r["A"].iloc[0] == pytest.approx(0.10)
    assert r["B"].iloc[0] == pytest.approx(-0.10)

    gapped = pd.DataFrame({"A": [100.0, np.nan, 120.0]})
    gapped_r = metrics.daily_returns(gapped)["A"]
    assert gapped_r.isna().all()  # a missing price must not become a 0% return


def test_normalized_prices_use_each_columns_first_valid_price():
    px = pd.DataFrame({"A": [100.0, 101.0], "B": [np.nan, 50.0]})
    norm = metrics.normalized_prices(px)
    assert norm["A"].tolist() == pytest.approx([100.0, 101.0])
    assert np.isnan(norm["B"].iloc[0])  # no invented price before the first quote
    assert norm["B"].iloc[1] == pytest.approx(100.0)


def test_annualized_return_and_volatility_use_252_days():
    r = pd.DataFrame({"A": [0.01, -0.01, 0.02, -0.02]})
    assert metrics.annualized_return(r)["A"] == pytest.approx(
        np.mean(r["A"]) * 252)
    assert metrics.annualized_volatility(r)["A"] == pytest.approx(
        np.sqrt(np.var(r["A"], ddof=1) * 252))


def test_sharpe_matches_annualized_definition():
    r = pd.DataFrame({"A": [0.01, -0.005, 0.02, 0.0, -0.01]})
    ann_ret = float(np.mean(r["A"]) * 252)
    ann_vol = float(np.sqrt(np.var(r["A"], ddof=1) * 252))
    assert metrics.sharpe_ratio(r, 0.02)["A"] == pytest.approx(
        (ann_ret - 0.02) / ann_vol)


def test_sortino_uses_target_downside_deviation():
    r = pd.DataFrame({"A": [0.10, -0.10, 0.2222, -0.10, -0.10]})
    daily_rf = (1 + 0.02) ** (1 / 252) - 1
    excess = r["A"].to_numpy() - daily_rf
    downside_dev = np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)) * np.sqrt(252)
    expected = (np.mean(r["A"]) * 252 - 0.02) / downside_dev
    assert metrics.sortino_ratio(r, 0.02)["A"] == pytest.approx(expected)


def test_sortino_is_not_std_of_clipped_excess_returns():
    """Guards the Phase 1 bug: std() of the clipped series is not downside dev."""
    r = pd.DataFrame({"A": [0.05, 0.05, -0.01, -0.01]})
    daily_rf = (1 + 0.02) ** (1 / 252) - 1
    excess = r["A"] - daily_rf
    correct = np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)) * np.sqrt(252)
    buggy = excess.clip(upper=0).std() * np.sqrt(252)
    assert not np.isclose(correct, buggy)

    implemented = (np.mean(r["A"]) * 252 - 0.02) / metrics.sortino_ratio(r, 0.02)["A"]
    assert implemented == pytest.approx(correct)


def test_drawdown_is_zero_at_peaks_and_negative_in_declines():
    px = pd.DataFrame({"A": [100.0, 120.0, 90.0, 130.0]})
    dd = metrics.drawdown_series(px)["A"]
    assert dd.tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])
    assert metrics.max_drawdown(px)["A"] == pytest.approx(-0.25)


def test_var_is_a_negative_return_quantile():
    r = pd.DataFrame({"A": [-0.10, -0.05, 0.0, 0.05, 0.10]})
    var = metrics.value_at_risk(r, 0.25)["A"]
    assert var == pytest.approx(-0.05)  # signed daily return, loss is negative
    assert var < 0


def test_cvar_is_the_mean_of_the_tail_at_or_below_var():
    r = pd.DataFrame({"A": [-0.10, -0.05, 0.0, 0.05, 0.10]})
    var = metrics.value_at_risk(r, 0.25)["A"]
    tail = r["A"][r["A"] <= var]
    cvar = metrics.conditional_var(r, 0.25)["A"]
    assert cvar == pytest.approx(np.mean(tail))
    assert cvar <= var


def test_best_worst_days_ignore_nan():
    idx = pd.bdate_range("2020-01-01", periods=4)
    r = pd.DataFrame({"A": [0.01, np.nan, -0.03, 0.02]}, index=idx)
    bw = metrics.best_worst_days(r)
    assert bw.loc["A", "best_day_return"] == pytest.approx(0.02)
    assert bw.loc["A", "worst_day_return"] == pytest.approx(-0.03)
    assert bw.loc["A", "worst_day_date"] == idx[2]


def test_moving_average_values_and_warmup():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    ma = metrics.moving_averages(s, short=2, long=3)
    assert np.isnan(ma["2 Day MA"].iloc[0])
    assert ma["2 Day MA"].iloc[1] == pytest.approx(1.5)
    assert ma["3 Day MA"].iloc[2] == pytest.approx(2.0)
    assert ma["3 Day MA"].iloc[3] == pytest.approx(3.0)


def test_rolling_volatility_annualizes_the_window():
    rng = np.random.default_rng(1)
    r = pd.DataFrame({"A": 0.01 * rng.standard_normal(40)})
    rv = metrics.rolling_volatility(r, window=20)["A"]
    assert np.isnan(rv.iloc[18])
    manual = np.sqrt(np.var(r["A"].iloc[:20], ddof=1)) * np.sqrt(252)
    assert rv.iloc[19] == pytest.approx(manual)


# --- Phase 1 regression tests: portfolio + data pipeline -----------------------
def test_reported_portfolio_metrics_match_its_weights(returns):
    sims, best = portfolio.random_portfolios(returns, n_portfolios=400, seed=11)
    for weights in (best.max_sharpe_weights, best.min_vol_weights):
        assert weights.sum() == pytest.approx(1.0)
        assert (weights >= 0).all()  # long-only claim must hold
    w = best.max_sharpe_weights.to_numpy()
    ret = float(w @ returns.mean().to_numpy() * 252)
    vol = float(np.sqrt(w @ returns.cov().to_numpy() @ w) * np.sqrt(252))
    assert best.max_sharpe_return == pytest.approx(ret)
    assert best.max_sharpe_vol == pytest.approx(vol)
    assert best.max_sharpe_ratio == pytest.approx((ret - 0.02) / vol)
    assert sims["volatility"].min() == pytest.approx(best.min_vol_vol)


def test_extract_prices_prefers_adjusted_close():
    idx = pd.bdate_range("2020-01-01", periods=3)
    cols = pd.MultiIndex.from_product([["Adj Close", "Close"], ["AAA"]])
    raw = pd.DataFrame([[10.0, 12.0], [11.0, 13.0], [12.0, 14.0]],
                       index=idx, columns=cols)
    prices, basis = data_mod.extract_prices(raw)
    assert basis == "Adj Close"
    assert prices["AAA"].tolist() == [10.0, 11.0, 12.0]

    raw_close, close_basis = data_mod.extract_prices(raw, prefer_adjusted=False)
    assert close_basis == "Close"
    assert raw_close["AAA"].tolist() == [12.0, 13.0, 14.0]


def test_load_prices_slices_cache_to_the_requested_window(tmp_path):
    """A covering cache must be cut to the request, not returned wholesale."""
    idx = pd.bdate_range("2020-01-01", periods=60)
    values = np.arange(120, dtype=float).reshape(60, 2) + 10
    raw = pd.DataFrame(values, index=idx,
                       columns=pd.MultiIndex.from_product(
                           [["Adj Close"], ["AAA", "BBB"]]))
    cache = tmp_path / "cache.csv"
    raw.to_csv(cache)

    loaded = data_mod.load_prices_detailed(
        ["AAA"], "2020-02-03", "2020-02-14", cache_path=cache)
    assert loaded.source == "cache"
    assert list(loaded.close.columns) == ["AAA"]
    assert loaded.close.index.min() >= pd.Timestamp("2020-02-03")
    assert loaded.close.index.max() < pd.Timestamp("2020-02-14")  # end exclusive
    assert len(loaded.close) == 9


def test_failed_download_returns_clearly_labelled_synthetic(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(data_mod, "download_prices", boom)
    loaded = data_mod.load_prices_detailed(
        ["AAA"], "2020-01-01", "2020-03-01", cache_path=None)
    assert loaded.source == "synthetic"
    assert loaded.price_basis == "synthetic"
    assert "SYNTHETIC" in loaded.note.upper()  # never silently presented as market data
    assert not loaded.close.empty


def test_failed_download_without_fallback_raises(monkeypatch):
    monkeypatch.setattr(
        data_mod, "download_prices",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(data_mod.DataDownloadError):
        data_mod.load_prices_detailed(["AAA"], "2020-01-01", "2020-03-01",
                                      cache_path=None, synthetic_fallback=False)


def test_load_prices_rejects_invalid_requests():
    with pytest.raises(ValueError, match="must be before"):
        data_mod.load_prices_detailed(["AAA"], "2021-01-01", "2020-01-01",
                                      cache_path=None)
    with pytest.raises(ValueError):
        data_mod.load_prices_detailed([], "2020-01-01", "2021-01-01",
                                      cache_path=None)


def test_return_distribution_plot_handles_single_ticker():
    """The Risk tab crashed when exactly one bank was selected."""
    fig, axes = plots.plot_return_distributions(
        pd.DataFrame({"AAA": [0.01, -0.02, 0.0, 0.03]}))
    assert len(list(axes)) == 3
    import matplotlib.pyplot as plt

    plt.close(fig)


# --- Phase 3: data-source provenance -----------------------------------------
def _raw_download(tickers, periods=40, start="2020-01-01"):
    """A yfinance-shaped raw frame: MultiIndex (ticker, field), Adj Close present."""
    idx = pd.bdate_range(start, periods=periods)
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([tickers, fields])
    data = np.zeros((periods, len(tickers) * len(fields)))
    for i, ticker in enumerate(tickers):
        base = np.linspace(10.0, 20.0, periods) * (i + 1)
        for j, field in enumerate(fields):
            data[:, i * len(fields) + j] = base if field != "Volume" else 1_000.0
    return pd.DataFrame(data, index=idx, columns=cols)


def test_successful_download_is_labelled_yahoo(monkeypatch):
    """A real (here: stubbed network) response must be reported as live Yahoo data."""
    raw = _raw_download(["AAA", "BBB"])
    monkeypatch.setattr(data_mod, "download_prices", lambda *a, **k: raw)

    loaded = data_mod.load_prices_detailed(
        ["AAA", "BBB"], "2020-01-01", "2020-03-01", cache_path=None, use_cache=False)

    assert loaded.source == "yahoo"
    assert loaded.price_basis == "Adj Close"
    assert list(loaded.close.columns) == ["AAA", "BBB"]  # caller's order preserved
    assert loaded.note == ""
    assert not loaded.close.isna().any().any()


def test_covering_cache_is_labelled_cache_and_skips_the_download(tmp_path, monkeypatch):
    raw = _raw_download(["AAA"], periods=80)
    cache = tmp_path / "cache.csv"
    raw.to_csv(cache)

    def forbidden(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("download called even though the cache covers the request")

    monkeypatch.setattr(data_mod, "download_prices", forbidden)
    loaded = data_mod.load_prices_detailed(["AAA"], "2020-01-20", "2020-02-20",
                                           cache_path=cache)
    assert loaded.source == "cache"
    assert loaded.note == ""


def test_cache_missing_a_ticker_is_not_reused(tmp_path, monkeypatch):
    """A cache that only covers part of the request must not masquerade as the answer."""
    raw = _raw_download(["AAA"], periods=80)
    cache = tmp_path / "cache.csv"
    raw.to_csv(cache)

    monkeypatch.setattr(data_mod, "download_prices",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(data_mod.DataDownloadError):
        data_mod.load_prices_detailed(["AAA", "BBB"], "2020-01-20", "2020-02-20",
                                      cache_path=cache, synthetic_fallback=False)


def test_fallback_never_claims_live_or_cached(monkeypatch):
    monkeypatch.setattr(data_mod, "download_prices",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    loaded = data_mod.load_prices_detailed(["AAA"], "2020-01-01", "2020-03-01",
                                           cache_path=None)
    assert loaded.source == "synthetic"
    assert loaded.source not in {"yahoo", "cache"}
    assert loaded.price_basis == "synthetic"


def test_ticker_missing_from_the_response_is_dropped_with_a_warning(monkeypatch):
    raw = _raw_download(["AAA"])  # BBB requested but absent upstream
    monkeypatch.setattr(data_mod, "download_prices", lambda *a, **k: raw)
    with pytest.warns(UserWarning, match="No data returned"):
        loaded = data_mod.load_prices_detailed(
            ["AAA", "BBB"], "2020-01-01", "2020-03-01", cache_path=None, use_cache=False)
    assert list(loaded.close.columns) == ["AAA"]
    assert loaded.source == "yahoo"


def test_empty_download_frame_raises_without_fallback(monkeypatch):
    monkeypatch.setattr(data_mod, "download_prices", lambda *a, **k: pd.DataFrame())
    with pytest.raises(data_mod.DataDownloadError):
        data_mod.load_prices_detailed(["AAA"], "2020-01-01", "2020-03-01",
                                      cache_path=None, use_cache=False,
                                      synthetic_fallback=False)


# --- Phase 3: financial metric edge cases ------------------------------------
def test_single_observation_yields_no_risk_metrics():
    """One return gives no dispersion: volatility/Sharpe/Sortino must be NaN, not 0."""
    prices = pd.DataFrame({"AAA": [10.0, 11.0]})       # exactly one daily return
    rets = metrics.daily_returns(prices)
    assert len(rets) == 1
    assert np.isnan(metrics.annualized_volatility(rets)["AAA"])
    assert np.isnan(metrics.sharpe_ratio(rets)["AAA"])
    assert np.isnan(metrics.sortino_ratio(rets)["AAA"])


def test_sortino_is_nan_when_no_day_falls_below_the_target():
    rets = pd.DataFrame({"AAA": [0.02, 0.01, 0.03]})
    assert np.isnan(metrics.sortino_ratio(rets, 0.02)["AAA"])


def test_var_of_constant_returns_equals_that_return():
    """With no dispersion the 5th percentile is the value itself - even if positive."""
    rets = pd.DataFrame({"AAA": [0.01] * 30})
    assert metrics.value_at_risk(rets, 0.05)["AAA"] == pytest.approx(0.01)
    assert metrics.conditional_var(rets, 0.05)["AAA"] == pytest.approx(0.01)


def test_drawdown_of_a_flat_series_is_zero():
    prices = pd.DataFrame({"AAA": [10.0] * 10})
    assert metrics.max_drawdown(prices)["AAA"] == pytest.approx(0.0)
    assert (metrics.drawdown_series(prices)["AAA"] == 0).all()


def test_sharpe_treats_the_risk_free_rate_as_annual():
    rng = np.random.default_rng(3)
    rets = pd.DataFrame({"AAA": rng.normal(0.0005, 0.01, 300)})
    rf = 0.05
    vol = rets["AAA"].std() * np.sqrt(252)
    expected = (rets["AAA"].mean() * 252 - rf) / vol
    assert metrics.sharpe_ratio(rets, rf)["AAA"] == pytest.approx(expected)


def test_annualized_return_is_arithmetic_and_not_cagr():
    """+100% then -50%: compounded growth is 0, so arithmetic annualization differs."""
    prices = pd.DataFrame({"AAA": [100.0, 200.0, 100.0]})
    rets = metrics.daily_returns(prices)
    growth = metrics.cumulative_returns(rets)["AAA"].iloc[-1]
    assert growth == pytest.approx(1.0)                       # no compounded return
    assert metrics.annualized_return(rets)["AAA"] == pytest.approx(
        rets["AAA"].mean() * 252)
    # Round trip: the price ends where it started, so CAGR is 0 while the
    # arithmetic annualized mean is large and positive.
    cagr = (prices["AAA"].iloc[-1] / prices["AAA"].iloc[0]) ** (252 / (len(prices) - 1)) - 1
    assert cagr == pytest.approx(0.0)
    assert metrics.annualized_return(rets)["AAA"] == pytest.approx(63.0)
    assert metrics.annualized_return(rets)["AAA"] > cagr

    # A losing path: arithmetic annualization stays positive while CAGR is
    # deeply negative - the reason the summary column is "Ann. Return", not CAGR.
    losing = pd.DataFrame({"AAA": [100.0, 150.0, 90.0]})
    l_rets = metrics.daily_returns(losing)
    l_cagr = (losing["AAA"].iloc[-1] / losing["AAA"].iloc[0]) ** (
        252 / (len(losing) - 1)) - 1
    assert metrics.annualized_return(l_rets)["AAA"] == pytest.approx(0.05 * 252)
    assert metrics.annualized_return(l_rets)["AAA"] > 0 > l_cagr


# --- Phase 3: portfolio simulation assumptions -------------------------------
def test_single_asset_simulation_is_fully_invested():
    rng = np.random.default_rng(7)
    rets = pd.DataFrame({"AAA": rng.normal(0.0004, 0.012, 250)})
    sims, best = portfolio.random_portfolios(rets, n_portfolios=50, seed=5)

    assert best.max_sharpe_weights["AAA"] == pytest.approx(1.0)
    assert best.min_vol_weights["AAA"] == pytest.approx(1.0)
    assert best.min_vol_vol == pytest.approx(rets["AAA"].std(ddof=1) * np.sqrt(252))
    assert best.min_vol_return == pytest.approx(rets["AAA"].mean() * 252)


def test_portfolio_volatility_includes_the_covariance_term():
    rets = pd.DataFrame({"AAA": [0.01, -0.02, 0.015, 0.0, 0.005],
                         "BBB": [0.02, -0.01, 0.0, 0.01, -0.005]})
    w = np.array([0.5, 0.5])
    ret, vol, sharpe = portfolio.portfolio_performance(w, rets.mean(), rets.cov(), 0.02)
    manual_var = (0.25 * rets["AAA"].var() + 0.25 * rets["BBB"].var()
                  + 0.5 * rets["AAA"].cov(rets["BBB"]))
    assert vol == pytest.approx(np.sqrt(manual_var) * np.sqrt(252))
    assert ret == pytest.approx(0.5 * (rets["AAA"].mean() + rets["BBB"].mean()) * 252)
    assert sharpe == pytest.approx((ret - 0.02) / vol)


def test_reported_best_portfolios_are_the_best_sampled_mixes():
    rng = np.random.default_rng(13)
    rets = pd.DataFrame(rng.normal(0.0003, 0.01, (200, 4)),
                        columns=["AAA", "BBB", "CCC", "DDD"])
    sims, best = portfolio.random_portfolios(rets, n_portfolios=500, seed=3)

    assert best.max_sharpe_ratio == pytest.approx(sims["sharpe"].max())
    assert best.min_vol_vol == pytest.approx(sims["volatility"].min())
    assert (best.max_sharpe_weights >= 0).all()
    assert best.max_sharpe_weights.sum() == pytest.approx(1.0)
