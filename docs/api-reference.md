# 🧩 API Reference

Public interface of the `src/` package. All functions are imported as:

```python
from src import config, data, metrics, plots, charts, portfolio, theme
```

For the *meaning* of each metric, see [Metrics Reference](metrics-reference.md).

---

## `src.config` — constants

Single source of truth for tickers, dates, parameters, and paths.

| Name | Value | Purpose |
|------|-------|---------|
| `BANKS` | `["BAC","C","GS","JPM","MS","WFC"]` | Default universe |
| `BANK_NAMES` | dict | Ticker → full bank name |
| `START_DATE` / `END_DATE` | `"2006-01-01"` / `"2016-01-01"` | Default sample period |
| `TRADING_DAYS` | `252` | Annualization factor |
| `RISK_FREE_RATE` | `0.02` | Annual risk-free rate |
| `USE_ADJUSTED_PRICES` | `True` | Use `Adj Close` (total return) instead of raw `Close` |
| `MA_SHORT_WINDOW` / `MA_LONG_WINDOW` | `30` / `50` | Moving-average windows |
| `ROLLING_VOL_WINDOW` | `30` | Rolling-volatility window |
| `VAR_LEVEL` | `0.05` | VaR/CVaR tail level |
| `N_MONTE_CARLO_PORTFOLIOS` | `5000` | Monte Carlo simulation count |
| `RANDOM_SEED` | `99` | Synthetic-data seed |
| `ROOT_DIR` / `DATA_DIR` / `IMAGES_DIR` | `Path` | Key directories |
| `CACHE_FILE` / `SUMMARY_FILE` | `Path` | `data/bank_prices.csv`, `data/summary.csv` |

---

## `src.data` — loading & cleaning

```python
load_prices_detailed(tickers, start, end, cache_path=None, use_cache=True,
                     synthetic_fallback=True,
                     prefer_adjusted=True) -> LoadedPrices
```

One-stop loader: tries **valid cache → Yahoo → synthetic** and returns a
`LoadedPrices` dataclass with `close` (dates × tickers), `source`
(`"cache"`/`"yahoo"`/`"synthetic"`), `price_basis` (`"Adj Close"`,
`"Close"` or `"synthetic"`) and a human-readable `note`. A cache is only reused
when it contains every requested ticker and covers the requested dates; it is
then sliced to that window (`end` exclusive). Raises `ValueError` for an empty
ticker list or `start >= end`, and `DataDownloadError` when downloading fails
and `synthetic_fallback=False`.

```python
load_prices(tickers, start, end, cache_path=None, use_cache=True,
            synthetic_fallback=True,
            prefer_adjusted=True) -> tuple[pd.DataFrame, str]
```

Backwards-compatible wrapper returning `(close_prices, source)` — used by the
notebook. Prefer `load_prices_detailed()` in new code.

```python
download_prices(tickers, start, end, auto_adjust=False,
                cache_path=None) -> pd.DataFrame
```

Raw `yfinance` download that optionally writes a CSV cache (it never *reads*
one — cache validation lives in `load_prices_detailed`). Raises
`DataDownloadError` if the result is empty.

```python
extract_close(raw, price_col="Close") -> pd.DataFrame
extract_prices(raw, prefer_adjusted=True) -> tuple[pd.DataFrame, str]
```

Extract the (dates × tickers) price frame from a raw download. Handles
`(ticker, price)`, `(price, ticker)`, and flat single-ticker layouts.
`extract_prices` returns `(prices, price_basis)` and prefers `Adj Close`,
falling back to `Close` with a warning.

```python
clean_prices(close, max_fill_days=5) -> pd.DataFrame
```

Sorts, de-duplicates, fills gaps ≤ 5 days, drops all-NaN rows (warns about
fixes applied).

```python
generate_synthetic_prices(tickers, start="2006-01-01",
                          end="2016-01-01", seed=99) -> pd.DataFrame
```

Deterministic business-day prices (GBM + shared market factor + 2008–2009
crisis regime). Used for offline demos and tests.

```python
describe_data(close) -> pd.DataFrame
```

Overview table: date range, row count, missing values, first/last price.

```python
class DataDownloadError(RuntimeError)
```

Raised when downloading fails and no fallback is allowed.

---

## `src.metrics` — returns & risk (pure functions, fully tested)

All take/return pandas objects; tickers as columns.

| Function | Signature | Returns |
|----------|-----------|---------|
| `daily_returns` | `(prices)` | Daily `pct_change` (first row dropped) |
| `cumulative_returns` | `(returns)` | Growth of $1 |
| `normalized_prices` | `(prices, base=100.0)` | Rebasing to `base` at t₀ |
| `annualized_return` | `(returns)` | Mean × 252 (arithmetic, not CAGR) |
| `annualized_volatility` | `(returns)` | Std × √252 |
| `sharpe_ratio` | `(returns, risk_free_rate=0.02)` | Annualized Sharpe (NaN if vol = 0) |
| `sortino_ratio` | `(returns, risk_free_rate=0.02)` | Annualized Sortino (target downside deviation) |
| `drawdown_series` | `(prices)` | `(P − running_max) / running_max` |
| `max_drawdown` | `(prices)` | Worst drawdown per ticker |
| `value_at_risk` | `(returns, level=0.05)` | Historical daily VaR (signed return, ≤ 0) |
| `conditional_var` | `(returns, level=0.05)` | Historical daily CVaR |
| `rolling_volatility` | `(returns, window=30)` | Annualized rolling std |
| `moving_averages` | `(series, short=30, long=50)` | `Close` + short/long MA columns |
| `correlation_matrix` | `(returns)` | Pearson correlation |
| `best_worst_days` | `(returns)` | Extreme returns + dates |
| `summary_table` | `(prices, returns, risk_free_rate=0.02, var_level=0.05)` | Overview table sorted by Sharpe |

---

## `src.plots` — charts

Call `plots.setup_style()` once first. Every `plot_*` returns `(fig, ax)` (or
`(fig, axes)`) and writes a PNG when `savepath=` is given (parent dirs created
automatically). Time-series charts shade the 2008–2009 crisis band.

| Function | Input | Chart |
|----------|-------|-------|
| `setup_style()` | — | Global seaborn/matplotlib style |
| `plot_price_history` | `close` | Closing-price trends |
| `plot_normalized` | `normalized` | Rebased performance |
| `plot_cumulative` | `cumulative` | Growth of $1 |
| `plot_correlation_heatmap` | `corr` | Annotated heatmap |
| `plot_return_distributions` | `returns` | Histogram grid + KDE + ±3σ |
| `plot_pairwise_scatter` | `returns, sample=500, seed=42` | Sampled scatter matrix |
| `plot_moving_averages` | `ma, ticker` | Price + short/long MAs |
| `plot_rolling_volatility` | `rolling_vol, window=30` | Annualized rolling vol |
| `plot_drawdown` | `drawdown` | Underwater chart |
| `plot_risk_return` | `summary` | Vol-vs-return scatter (size ∝ Sharpe) |
| `plot_efficient_frontier` | `simulations` | Risk–return cloud colored by Sharpe (legacy name) |

---

## `src.theme` — dashboard design system (display only)

No financial maths; every helper returns an HTML string or a Plotly object, so it
can be unit-tested without Streamlit.

| Name | Purpose |
|------|---------|
| `BG`, `SURFACE`, `BORDER`, `TEXT`, `MUTED`, `ACCENT`, `POSITIVE`, `NEGATIVE`, `WARNING` | Palette tokens |
| `TICKER_COLORS`, `TICKER_SYMBOLS` | One colour + one marker shape per bank |
| `DIVERGING` | −1…+1 correlation colour scale |
| `PLOTLY_TEMPLATE`, `PLOTLY_CONFIG` | Template name (`fsa_dark`) and chart config |

```python
ticker_color(ticker) -> str
ticker_symbol(ticker) -> str
tint(color, factor) -> str
rgba(color, alpha) -> str
```

```python
fmt_pct(value, digits=1, signed=False) -> str   # 0.1234 -> "12.3%"
fmt_ratio(value, digits=2, signed=False) -> str # 0.3647 -> "0.36"
fmt_money(value, digits=2) -> str               # 1.2345 -> "$1.23"
fmt_int(value) -> str                           # 2517   -> "2,517"
tone_of(value) -> str                           # "pos" | "neg" | "neutral"
```

All formatters return `"—"` for `NaN`, `inf` or non-numeric input.

```python
kpi_grid(cards) -> str            # responsive KPI tiles (KpiCard dataclass)
chips(items) -> str               # metadata chips: (label, value[, tone])
status_pill(source) -> str        # "yahoo" | "cache" | anything else (synthetic)
hero(title, subtitle, pill_html) -> str
section_html(Section(title, description)) -> str
empty_state(message) -> str
legend_rows(tickers, names) -> str
brand_block(name, tagline) -> str
sidebar_label(text) -> str
register_plotly_template() -> str # idempotent, returns "fsa_dark"
CSS                               # injected stylesheet
```

---

## `src.charts` — interactive Plotly figures (display only)

Every builder returns a `plotly.graph_objects.Figure` with the dashboard
template, fixed height, unified hover and ticker-consistent colours. They never
download data or compute metrics — pass in the frames from `src.metrics` /
`src.portfolio`.

| Function | Input | Tab |
|----------|-------|-----|
| `price_history(close, basis, log_scale=False)` | Adj closes | Prices |
| `normalized(normalized_prices, base=100)` | `metrics.normalized_prices` | Prices |
| `cumulative(cumulative_returns)` | `metrics.cumulative_returns` | Prices |
| `daily_returns(returns, ticker)` | daily returns + focus ticker | Prices |
| `moving_averages(ma, ticker=None)` | `metrics.moving_averages` | Prices |
| `risk_return(summary, risk_free_rate)` | `metrics.summary_table` | Risk |
| `drawdown(drawdown_series)` | `metrics.drawdown_series` | Risk |
| `rolling_volatility(rolling_vol, window)` | `metrics.rolling_volatility` | Risk |
| `return_boxes(returns)` | daily returns | Risk |
| `correlation_heatmap(corr)` | `metrics.correlation_matrix` | Correlations |
| `portfolio_cloud(simulations, max_sharpe, min_vol, assets)` | `portfolio.random_portfolios` | Portfolio |
| `weights_bar(weights)` | allocation weights | Portfolio |

```python
from src import charts
theme.register_plotly_template()
fig = charts.price_history(close, "Adj Close", log_scale=True)
```

---

## `src.portfolio` — Monte Carlo portfolios (no scipy needed)

```python
portfolio_performance(weights, mean_returns, cov,
                      risk_free_rate=0.02) -> tuple[float, float, float]
```

Annualized `(return, volatility, Sharpe)` for a weight vector.

```python
random_portfolios(returns, n_portfolios=5000,
                  risk_free_rate=0.02, seed=42) -> tuple[pd.DataFrame, PortfolioResult]
```

Simulates random long-only portfolios (weights ≥ 0, summing to 1) and returns
`(simulations, best)`, where `simulations` has `return` / `volatility` /
`sharpe` columns and `best` is a `PortfolioResult` with the best-of-sample
max-Sharpe and min-vol weights + stats. This is a Monte Carlo search, **not** a
solved efficient frontier and **not** a forecast.

---

## Minimal end-to-end example

```python
from src import config, data, metrics, plots, portfolio

close, source = data.load_prices(config.BANKS, config.START_DATE,
                                 config.END_DATE, config.CACHE_FILE)
rets = metrics.daily_returns(close)
summary = metrics.summary_table(close, rets)

plots.setup_style()
plots.plot_risk_return(summary, savepath="images/risk_return.png")

sims, best = portfolio.random_portfolios(rets)
plots.plot_efficient_frontier(sims, savepath="images/efficient_frontier.png")
```
