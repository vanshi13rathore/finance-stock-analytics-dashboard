# 📖 User Guide

This guide walks through the three ways to use the project: the **notebook**,
the **dashboard**, and `src/` **as a library**. (For the headless pipeline, see
the [CLI Reference](cli-reference.md).)

---

## 1. The notebook (`finance_project.ipynb`)

The notebook is the narrative version of the analysis — the best place to
understand *what* is computed and *why*.

### Section map

| # | Section | What it covers |
|---|---------|----------------|
| 0 | Setup | Imports, global plot style, tickers/period |
| 1 | Data collection | `load_prices()` + data-overview table |
| 2 | Price exploration | Raw closing-price trends, 2008 crisis band |
| 3 | Returns | Daily, normalized (base 100), cumulative (growth of $1) |
| 4 | Risk analysis | Summary table, best/worst days, rolling vol, drawdown, risk-vs-return |
| 5 | Correlation & distributions | Heatmap, histograms with ±3σ guides, sampled scatter matrix |
| 6 | Trend | BAC with 30/50-day moving averages |
| 7 | Portfolio simulation | Monte Carlo Portfolio Simulation — Risk vs. Return (random weights, max-Sharpe) |
| 8 | Key findings | Auto-derived bullet findings (never goes stale) |

### Tips

- **Run top to bottom.** Later cells depend on `close`, `returns`, `summary`,
  and `corr` created earlier.
- The notebook prints its **data source** (`yahoo` / `cache` / `synthetic`).
  Numbers in section 8 are derived from the data, so they update automatically
  if the source changes.
- To analyze **different tickers or dates**, edit the `load_prices(...)` call
  (or `src/config.py`) and re-run all cells.

---

## 2. The dashboard (`app.py`)

```bash
pip install -r requirements.txt   # includes streamlit + plotly
streamlit run app.py
```

### Header

The header always answers “what am I looking at?”: the provenance pill
(**Yahoo Finance · live**, **Yahoo Finance · cached**, or **Synthetic demo data**)
and chips for the selected banks, the real price window, the number of trading
sessions, the price basis (`Adj Close`) and a status line — *"Historical data
loaded"*, *"Cached historical data"* or *"Simulated — not market data"*. The
status describes provenance only: prices are not independently verified against
another data source. A caption explains that Yahoo treats the end date as
exclusive.

### Sidebar controls

| Group | Control | Effect |
|-------|---------|--------|
| Universe | Banks (multi-select) | Which tickers to analyze |
| Period | Start / End dates | Sample period |
| Assumptions | Risk-free rate | Used for Sharpe/Sortino and the portfolio simulation |
| | Short / Long MA windows | Moving-average chart (must differ) |
| | Rolling-vol window | Rolling-volatility chart |
| Data source | Use synthetic demo data | Force offline mode (ignores Yahoo/cache) |

Below the controls the sidebar shows the ticker colour legend, so chart colours
can be mapped back to banks at a glance.

### Tabs

1. **Prices** — six KPI cards, adjusted closes (crisis band, optional log axis),
   normalized performance, growth of $1, moving averages and daily returns for a
   focus bank, plus a price-overview table and CSV download
2. **Risk** — risk cards, sortable metrics table (hover a header for its
   definition), risk-vs-return bubble chart, underwater drawdown, rolling
   volatility, return distributions, best/worst days, CSV download
3. **Correlations** — average/strongest/weakest-pair cards, Plotly heatmap fixed
   to −1…+1, correlation matrix + CSV, and a plain-English interpretation
4. **Portfolio** — **Monte Carlo Portfolio Simulation — Risk vs. Return**: a
   risk-vs-return cloud of randomly generated long-only weights, with adjustable
   simulation count, the best-of-sample max-Sharpe and min-volatility allocations
   shown as percentages, and an allocation table + CSV. The cloud approximates
   the achievable region; it is not a solved efficient frontier and not a
   forecast.

### Reading the charts

- Hover any point for exact values; the hover label follows the ticker colours.
- Drag to pan and scroll to zoom (no toolbar, so the layout stays clean).
- Every chart uses the same ticker colour **and** marker shape, so the tabs read
  as one product.
- If a selection cannot support a view (e.g. one bank in Portfolio), the tab
  explains what is missing instead of failing.

---

## 3. Using `src/` as a library

Every interface above is a thin wrapper around `src/`. You can drive the same
code from your own scripts:

```python
from src import config, data, metrics, plots, portfolio

# Load (cache → Yahoo → synthetic fallback)
close, source = data.load_prices(
    config.BANKS, config.START_DATE, config.END_DATE,
    cache_path=config.CACHE_FILE,
)
print("source:", source)

# Analyze
returns = metrics.daily_returns(close)
summary = metrics.summary_table(close, returns)
print(summary.round(4))

# Visualize (returns fig/ax; pass savepath= to write a PNG)
plots.setup_style()
fig, ax = plots.plot_correlation_heatmap(metrics.correlation_matrix(returns))

# Simulate portfolios
sims, best = portfolio.random_portfolios(returns, n_portfolios=5_000)
print(best.max_sharpe_weights.round(4))
```

### Changing defaults

All shared constants live in `src/config.py` (tickers, dates, risk-free rate,
window sizes, seeds, paths). Import them instead of hard-coding values:

```python
from src import config
print(config.BANKS, config.RISK_FREE_RATE, config.MA_SHORT_WINDOW)
```

See the [API Reference](api-reference.md) for every public function, and
[Metrics Reference](metrics-reference.md) for what each metric means.
