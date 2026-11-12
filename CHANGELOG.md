# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.4.0] - 2026-11-12 — Phase 3 QA, financial audit & GitHub preparation

Documentation and labelling release: **no financial formula was changed**, and
the dashboard design is untouched. Every metric was re-derived independently
from textbook definitions on the cached 2006–2015 dataset and matched the
implementation to machine precision (daily/cumulative returns, annualized
return and volatility, Sharpe, Sortino, max drawdown, VaR/CVaR, correlation,
portfolio weight maths, max-Sharpe/min-vol selection).

### Fixed

- **Untruthful data status.** The header chip claimed "Verified market prices"
  for any non-synthetic series, although no verification process exists. It now
  reads "Historical data loaded" (live download) or "Cached historical data"
  (stored snapshot), and "Simulated — not market data" for synthetic data, so
  the three provenances stay distinct. `tests/test_app.py` asserts the factual
  label and that the word "Verified" no longer appears.
- **Stale exported CSVs.** `data/summary.csv` and `data/correlation.csv` were
  left over from an earlier synthetic run: they still used the pre-Phase-1
  `VaR 95% (daily)` column name, reported WFC at 10.1% annualized return
  (current: 19.2%), and implied BAC–MS as the strongest pair. Both files were
  regenerated from the cached Yahoo `Adj Close` snapshot, so the documented
  numbers now match the code that produces them.

### Changed

- `README.md` rewritten around the implemented application: problem statement,
  objectives, technologies, data provenance, architecture, financial
  methodology, verified headline findings, screenshots, installation, testing,
  limitations and future improvements. The Monte Carlo panel is described as a
  random long-only simulation rather than a solved efficient frontier.
- `docs/methodology.md` states explicitly that arithmetic annualization is not
  CAGR (with the WFC/BAC figures where the two diverge), that the portfolio
  cloud is not an optimised frontier, and that full-sample inputs contain
  look-ahead bias.
- `docs/findings.md`, `docs/data.md`, `docs/user-guide.md`,
  `docs/api-reference.md`, `docs/architecture.md`, `docs/cli-reference.md` and
  `docs/getting-started.md` corrected to match the code: true test count (96),
  data provenance and verification status, current file layout, and
  frontier-related wording.
- `.gitignore` adds `.phase1_backup/` and an explicit `*.pyc` rule so the local
  Phase 1 safety copy and bytecode never reach version control.

### Tests

- 96 offline tests still pass (0 failed, 0 skipped, 1 expected `UserWarning`
  from the download-failure fallback test).

## [2.3.0] - 2026-11-07 — Phase 2 frontend redesign

A presentation-only release: every calculation, data path and portfolio function
is unchanged from 2.2.0.

### Added

- `src/theme.py` — design system: palette (deep-navy surfaces, one colour **and**
  one marker symbol per ticker), Inter-based type scale, injected CSS, KPI cards,
  metadata chips, provenance pill, empty/error panels, and a registered Plotly
  template (`fsa_dark`).
- `src/charts.py` — 12 interactive Plotly builders (price history, normalized,
  growth of $1, daily returns, moving averages, risk-vs-return, drawdown, rolling
  volatility, return boxes, correlation heatmap, portfolio cloud, weight bars)
  with unified hover, crisis-band shading and ticker-consistent colours.
- `.streamlit/config.toml` — dark base theme mirroring `theme.py` (primary colour,
  surfaces, categorical chart colours, border radius).
- Dashboard header with title, subtitle, provenance pill and metadata chips
  (banks, real window, trading sessions, source, price basis, status).
- KPI rows on every tab, sortable formatted tables with per-column definitions,
  CSV downloads for prices, risk metrics, correlations and allocations.
- Empty states for single-bank portfolio/correlation views and human-readable
  messages for invalid dates, identical moving-average windows and empty
  selections; raw tracebacks stay inside a “Diagnostics” expander.
- `tests/test_theme.py`, `tests/test_charts.py`, `tests/test_app.py` (54 new
  tests) and a local `screenshots/` set with all four tabs plus responsive
  states (kept out of version control; they predate the status-label fix).
- `theme.correlation_scale()` — a fixed −1…+1 HTML legend for the correlation
  heatmap (clear at any width, unlike a Plotly colour bar).

### Changed

- `app.py` rebuilt around the theme and chart modules: same widgets (bank
  selector, start/end dates, risk-free rate, short/long MA, rolling-volatility
  window, synthetic toggle), regrouped into Universe / Period / Assumptions /
  Data source sections with tooltips on every control.
- Matplotlib charts stay in `src/plots.py` for the notebook and CLI; the
  dashboard no longer uses them.
- Caching is split into `load_market_data` (per tickers/dates/source, 15-minute
  TTL for live downloads) and `analyse` / `simulate` (per price frame and
  parameters), so slider moves reuse prepared data.
- Portfolio copy is explicit that the cloud is a **Monte Carlo random long-only
  simulation**, not a solved efficient frontier, and that it is descriptive —
  not a backtest or a recommendation.
- `requirements-dev.txt` adds `plotly`.

### Fixed

- Multiselect tags rendered Streamlit's default blue because the CSS targeted
  the old BaseWeb markup; the current `[data-tag]` attribute is now styled (the
  BaseWeb selector is kept as a fallback).
- Rotated y-axis titles no longer crowd wide tick labels (`standoff` on the
  template axes) and colour-bar ticks are no longer clipped by the card edge.

### Tests

- 42 → 96 offline tests. New coverage: palette uniqueness/contrast, formatter
  NaN-safety, HTML escaping, Plotly template registration, chart trace/colour/
  scale contracts, empty-input safety, and app-level widget behaviour (date
  filtering, single-bank selection, slider reruns, validation errors, synthetic
  disclosure, download buttons).

## [2.2.0] - 2026-11-07 — Phase 1 audit (stability & financial validation)

### Fixed

- **Sidebar `sprintf` crash.** `st.slider(..., format="%.1%%")` is invalid
  printf for Streamlit's browser-side sprintf-js and threw
  `SyntaxError: [sprintf] unexpected placeholder`, which removed the whole
  risk-free slider from the sidebar. The slider now works in percent units and
  uses `format="%.1f%%"` (displaying `2.0%` for a 2% rate).
- **Sortino denominator.** Downside deviation is now the target semi-deviation
  `sqrt(mean(min(r − r_f, 0)²)) × √252`, not `std()` of the clipped series
  (which understated downside risk and inflated Sortino).
- **Cache ignored user selections.** `load_prices` returned `data/bank_prices.csv`
  whenever it existed, so the ticker and date controls had no effect. A cache is
  now reused only when it covers the requested tickers and dates, and it is
  sliced to the requested window.
- **Single-bank crash.** Selecting one bank crashed the Risk tab's return
  distribution plot (`AttributeError` from an ndarray axes object).
- **Invalid dates.** `start >= end` produced an empty synthetic frame and `NaT`
  dates; the loader now raises a clear `ValueError` and the dashboard explains
  the problem instead of rendering empty charts.
- **`normalized_prices` blanked a ticker** when its first price was NaN; each
  series is now rebased on its own first valid price.
- **VaR label.** The summary column is now `VaR 95% (daily return)` to make the
  sign convention (negative = loss) explicit.

### Changed

- Return and risk metrics now use **dividend/split-adjusted `Adj Close`**
  (total return) by default (`config.USE_ADJUSTED_PRICES`). Impact on
  2006–2015 annualized return: WFC 16.55% → 19.16%, JPM 14.49% → 17.01%,
  C −3.96% → −2.48%.
- Sharpe ratio numerator and denominator are both annualized on the 252-day
  convention, matching the documented formula.
- `load_prices_detailed()` returns a `LoadedPrices` dataclass
  (`close`, `source`, `price_basis`, `note`); `load_prices()` keeps its
  `(close, source)` tuple for the notebook.
- Dashboard labels the data source, price basis and actual date span, explains
  Yahoo's exclusive end date, and shows a prominent warning whenever synthetic
  demo data is displayed.
- Portfolio simulation is seeded from `config.RANDOM_SEED` (reproducible) and
  guarded against insufficient data; chart titles derive from the actual dates.

### Tests

- 23 → 42 offline tests, adding independent checks for Sortino/Sharpe
  definitions, drawdown, VaR/CVaR, moving averages, rolling volatility, cache
  slicing, adjusted-price preference, fallback labelling and the single-ticker
  plot regression.

## [2.1.0] - 2026-10-10

### Added

- Full documentation set in `docs/`: getting-started, user guide, CLI
  reference, methodology, data, API reference, architecture, findings, and
  troubleshooting guides.
- `CONTRIBUTING.md` with dev setup, workflow, and code/test/docs guidelines.
- `CHANGELOG.md` (this file).

## [2.0.0] - 2026-10-10

### Added

- `src/` package: `config`, `data`, `metrics`, `plots`, `portfolio` modules.
- Risk metrics: Sharpe/Sortino ratios, max drawdown, VaR/CVaR, rolling
  volatility, annualized return/volatility, best/worst days.
- Monte Carlo efficient frontier with max-Sharpe / min-volatility portfolios.
- `scripts/run_analysis.py` headless pipeline (charts + CSVs + findings).
- Streamlit dashboard (`app.py`) with sidebar controls and 4 tabs.
- `tests/` suite: 23 offline unit tests.
- `images/` with 10 generated charts; `data/` with summary/correlation CSVs.
- `requirements-dev.txt` (pytest, streamlit).

### Changed

- Rewrote `finance_project.ipynb` with a full markdown narrative (12 sections).
- Rewrote `README.md` (quickstart, methodology cheat-sheet, screenshots).
- Pinned `requirements.txt` with minimum versions; expanded `.gitignore`.

### Fixed

- Removed duplicated download cells; single `load_prices()` entry point.
- Layout-aware `yfinance` extraction (works across old/new versions).
- Global plot styling applied first; consistent style on all charts.
- Sampled scatter matrix (full pairplot was too slow on 2,600+ rows).

## [1.0.0] - earlier

- Initial single-notebook exploration: Yahoo download, daily returns,
  volatility, correlation heatmap, histograms, pairplot, moving averages,
  normalized prices, rolling volatility, cumulative returns.
