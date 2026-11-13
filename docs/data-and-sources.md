# 💾 Data & Sources

Where the numbers come from, how they're stored, and how the project stays
reproducible with or without internet.

## Sources (in priority order)

`data.load_prices_detailed()` resolves data in this order and **always reports**
which source was used (`cache`, `yahoo`, or `synthetic`), together with the
price basis (`Adj Close` / `Close` / `synthetic`) and a note explaining any
fallback:

```text
1. Local CSV cache (data/bank_prices.csv)   ─┐
2. Live Yahoo Finance download via yfinance  ─┼─→ clean → analyze
3. Built-in synthetic demo data (fallback)  ─┘
```

| Source | When it's used | Reproducible? |
|--------|---------------|---------------|
| `cache` | Cache exists **and contains every requested ticker for the requested dates** | ✅ Yes (frozen snapshot) |
| `yahoo` | No usable cache; internet + Yahoo reachable | ⚠️ Mostly (Yahoo occasionally revises history) |
| `synthetic` | Download fails, or `--synthetic` / dashboard toggle | ✅ Yes (fixed seed `99`) |

A cache is only reused when it **covers** the current request; otherwise the
data are re-downloaded (and the app says so). A cache that spans more than the
request is cut down to the selected dates, so the ticker/date controls always
take effect — they are never silently overridden by an old CSV.

### Verification status — read this before quoting a number

Yahoo Finance is the project's **only** price source. Nothing in this codebase
cross-checks those prices against a second provider, an exchange feed or a
regulatory filing, so:

- prices are **loaded**, not **verified**;
- the dashboard's status chip therefore reads *"Historical data loaded"* (live
  download) or *"Cached historical data"* (stored snapshot), and
  *"Simulated — not market data"* for synthetic data — it never claims
  verification;
- Yahoo may restate historical prices between downloads, so a live run and a
  cached run can differ slightly for the same dates.

Adding a genuine verification step (a second source plus a tolerance check) is
listed under [Future improvements](../README.md#-future-improvements) in the
README.

## Live data (Yahoo Finance)

- **Tickers:** `BAC, C, GS, JPM, MS, WFC` (see `BANK_NAMES` in `src/config.py`
  for full names).
- **Period:** `2006-01-01` → `2016-01-01` (~2,517 trading days), chosen to cover
  the 2008 financial crisis with pre/post context. Yahoo treats `end` as
  **exclusive**, so the last close is the final trading day *before* it
  (`2015-12-31` for the default range) — this is why the charts stop in 2015.
- **Fields downloaded:** Open, High, Low, Close, Adj Close, Volume
  (`auto_adjust=False`); the analysis uses **Adj Close** (dividend- and
  split-adjusted total return, `config.USE_ADJUSTED_PRICES`).
- Downloaded with `group_by="ticker", threads=False` for reliability.
  `data.extract_close()` also accepts the newer `(price, ticker)` layout and
  single-ticker flat frames, so yfinance upgrades don't break it.

### Cache file: `data/bank_prices.csv` (git-ignored)

The raw download is saved automatically so re-runs are instant and don't hammer
the API. Delete it (or pass `--no-cache`) to force a fresh download.

## Cleaning (`data.clean_prices()`)

1. Sort by date, drop duplicated timestamps.
2. Forward/backward-fill gaps up to **5 trading days** (short suspensions).
3. Drop any remaining all-NaN rows.
4. Emit a warning reporting how many points were filled/dropped.

Filled values are carried prices, not observations. The backward fill also
applies at the very start of a series, which can pull an early price backwards
in time; it exists only to keep short suspensions from truncating the window.

## Synthetic demo data (`data.generate_synthetic_prices()`)

Used when Yahoo is unreachable (offline sandbox, rate limits) or explicitly
requested. Properties:

- **Geometric Brownian motion** on business days with per-ticker drift,
  volatility, and starting price.
- A **shared market factor** produces realistic ~0.6 cross-bank correlations.
- A **2008–2009 crisis regime** (2.5× volatility + negative drift) reproduces
  the real sample's narrative: volatility spike, deep drawdowns, slow recovery.
- **Deterministic:** default seed `99` gives identical data on every machine.
  (Seed was chosen so the demo mirrors reality: C riskiest, GS calmest.)

> The committed `images/` were generated from this demo data in an offline
> environment. `data/summary.csv` and `data/correlation.csv`, by contrast, are
> generated from the cached Yahoo snapshot described above (source label
> `cache`). With internet access, re-run the pipeline to regenerate the charts
> from live data. Synthetic runs are always labelled: the dashboard shows a
> warning banner and a "Synthetic demo data" pill. Synthetic prices are never
> mixed with, or presented as, Yahoo Finance data.

## Output schemas

### `data/summary.csv`

One row per ticker (sorted by Sharpe), from `metrics.summary_table()`:

| Column | Meaning | Unit |
|--------|---------|------|
| Ann. Return | Annualized mean return | decimal/year |
| Ann. Volatility | Annualized std of returns | decimal/year |
| Sharpe | Sharpe ratio (rf = 2%) | ratio |
| Sortino | Sortino ratio | ratio |
| Max Drawdown | Worst peak-to-trough loss | decimal (≤ 0) |
| VaR 95% (daily return) | 5th percentile of daily returns, **negative = loss** | decimal/day |
| Best Day / Worst Day | Extreme single-day returns | decimal/day |
| Growth of $1 | Final cumulative return | USD |

### `data/correlation.csv`

Symmetric 6×6 Pearson correlation matrix of daily returns (1.0 on the diagonal).

### `images/*.png`

Ten charts; see the [CLI Reference](cli-reference.md#files) for the full list.
