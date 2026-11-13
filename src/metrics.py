"""Core financial metrics: returns, risk, and risk-adjusted performance.

All functions are pure (no network, no plotting) so they are easy to test
and reuse from the notebook, the CLI, and the dashboard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------
def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns: ``P_t / P_{t-1} - 1`` (first row dropped).

    Prices are used as given: no extra forward-filling happens here, so a
    missing price yields a missing return instead of a fake zero. (``data.
    clean_prices`` fills gaps of up to five trading days when loading.)
    """
    return prices.pct_change().iloc[1:]


def cumulative_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Growth of a $1 investment: ``cumprod(1 + r)``."""
    return (1 + returns).cumprod()


def normalized_prices(prices: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase every series to ``base`` at its own first available price.

    Using each column's first *valid* price (rather than row 0 of the frame)
    keeps a ticker comparable when its history starts later or begins with a
    NaN; previously one missing value blanked that ticker's whole line.
    """
    first_prices = prices.apply(
        lambda col: (
            col.loc[col.first_valid_index()]
            if col.first_valid_index() is not None
            else np.nan
        )
    )
    return prices / first_prices * base


# ---------------------------------------------------------------------------
# Annualized risk / reward
# ---------------------------------------------------------------------------
def annualized_return(returns: pd.DataFrame) -> pd.Series:
    """Annualized mean return: ``mean(daily) × 252`` (arithmetic, not CAGR)."""
    return returns.mean() * TRADING_DAYS


def annualized_volatility(returns: pd.DataFrame) -> pd.Series:
    """Annualized volatility = std of daily returns × √252."""
    return returns.std() * np.sqrt(TRADING_DAYS)


def sharpe_ratio(
    returns: pd.DataFrame, risk_free_rate: float = 0.02
) -> pd.Series:
    """Annualized Sharpe ratio: ``(ann_return − rf) / ann_vol``.

    Both numerator and denominator are annualized from daily data with the
    same 252-day convention, so the ratio is unit-free. NaN where vol = 0.
    """
    vol = annualized_volatility(returns)
    return (annualized_return(returns) - risk_free_rate) / vol.replace(0, np.nan)


def sortino_ratio(
    returns: pd.DataFrame, risk_free_rate: float = 0.02
) -> pd.Series:
    """Annualized Sortino ratio: excess return per unit of downside deviation.

    Downside deviation is the *target* semi-deviation measured around zero
    (the risk-free target), averaged over **all** observations::

        dd = sqrt( mean( min(r_t − r_f,daily, 0)² ) ) × √252
        Sortino = (Ann. return − r_f) / dd

    Note: an earlier version used ``std()`` of the clipped series, which
    subtracts the mean of the downside values and therefore understates the
    denominator (overstating Sortino). See docs/metrics-reference.md.
    """
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = returns - daily_rf
    downside_dev = np.sqrt((excess.clip(upper=0) ** 2).mean()) * np.sqrt(
        TRADING_DAYS
    )
    return (annualized_return(returns) - risk_free_rate) / downside_dev.replace(
        0, np.nan
    )


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------
def drawdown_series(prices: pd.DataFrame) -> pd.DataFrame:
    """Drawdown series: ``(P − running_max) / running_max`` (≤ 0)."""
    running_max = prices.cummax()
    return (prices - running_max) / running_max


def max_drawdown(prices: pd.DataFrame) -> pd.Series:
    """Maximum (most negative) drawdown per ticker."""
    return drawdown_series(prices).min()


# ---------------------------------------------------------------------------
# Tail risk
# ---------------------------------------------------------------------------
def value_at_risk(returns: pd.DataFrame, level: float = 0.05) -> pd.Series:
    """Historical daily VaR: the ``level``-quantile of **returns** (≤ 0).

    Convention: the value is a *signed daily return*, so a loss shows up as a
    negative number (e.g. −0.035 = a 3.5% one-day loss). It is not a positive
    "loss amount"; the summary column name says so explicitly.
    """
    return returns.quantile(level)


def conditional_var(returns: pd.DataFrame, level: float = 0.05) -> pd.Series:
    """Historical daily CVaR (expected shortfall): mean of the worst ``level`` tail.

    Same sign convention as :func:`value_at_risk`: the average signed return on
    the days at or below the VaR quantile, so it is always ≤ VaR.
    """
    var = value_at_risk(returns, level)
    return pd.Series(
        {
            col: returns.loc[returns[col] <= var[col], col].mean()
            for col in returns.columns
        }
    )


# ---------------------------------------------------------------------------
# Rolling / trend helpers
# ---------------------------------------------------------------------------
def rolling_volatility(returns: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Annualized rolling standard deviation of returns."""
    return returns.rolling(window).std() * np.sqrt(TRADING_DAYS)


def moving_averages(
    series: pd.Series, short: int = 30, long: int = 50
) -> pd.DataFrame:
    """Price plus short/long simple moving averages."""
    return pd.DataFrame(
        {
            "Close": series,
            f"{short} Day MA": series.rolling(short).mean(),
            f"{long} Day MA": series.rolling(long).mean(),
        }
    )


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns."""
    return returns.corr()


def best_worst_days(returns: pd.DataFrame) -> pd.DataFrame:
    """Best/worst single-day return (value + date) per ticker."""
    return pd.DataFrame(
        {
            "best_day_return": returns.max(),
            "best_day_date": returns.idxmax(),
            "worst_day_return": returns.min(),
            "worst_day_date": returns.idxmin(),
        }
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def summary_table(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    var_level: float = 0.05,
) -> pd.DataFrame:
    """One-row-per-ticker overview of return, risk, and tail risk."""
    table = pd.DataFrame(
        {
            "Ann. Return": annualized_return(returns),
            "Ann. Volatility": annualized_volatility(returns),
            "Sharpe": sharpe_ratio(returns, risk_free_rate),
            "Sortino": sortino_ratio(returns, risk_free_rate),
            "Max Drawdown": max_drawdown(prices),
            f"VaR {int((1 - var_level) * 100)}% (daily return)": value_at_risk(
                returns, var_level
            ),
            "Best Day": returns.max(),
            "Worst Day": returns.min(),
            "Growth of $1": cumulative_returns(returns).iloc[-1],
        }
    )
    return table.sort_values("Sharpe", ascending=False)
