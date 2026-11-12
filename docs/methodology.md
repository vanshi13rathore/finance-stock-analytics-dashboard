# 📐 Methodology

How every number in this project is computed, and what it means. All
implementations live in `src/metrics.py` / `src/portfolio.py` (see
[API Reference](api-reference.md)); this page explains the *why*.

## Conventions

- **Prices** are daily *closing* prices, **dividend- and split-adjusted**
  (`Adj Close`, i.e. total return). Raw `Close` omits dividends and would
  understate long-run returns — see [Limitations](#limitations). Set
  `config.USE_ADJUSTED_PRICES = False` to reproduce the older raw-`Close`
  behaviour.
- **Prices are loaded, not verified.** Yahoo Finance is a single upstream
  source; the project performs no cross-check against another provider, so no
  output is described as "verified" market data.
- **Returns** are *simple* returns unless stated otherwise.
- **Annualization** assumes **252 trading days** per year
  (`TRADING_DAYS` in `src/config.py`).
- Default **risk-free rate** is **2%** per year (`RISK_FREE_RATE`).

## Returns

### Daily returns — `daily_returns()`

```text
r_t = P_t / P_{t-1} − 1
```

Percentage gain/loss per trading day. The first row is dropped (no prior price).
No extra filling happens here: a missing price yields a missing return rather
than a silent zero. (`data.clean_prices()` fills gaps of up to five trading days
at load time — see [Limitations](#limitations).) This is the foundation of all
risk math.

### Cumulative returns — `cumulative_returns()`

```text
Growth_t = ∏(1 + r_i)   for i = 1..t
```

Value of a $1 investment over time. The final value appears as **Growth of $1**
in the summary table. The total return over the window is
`Growth_end − 1`.

### Normalized prices — `normalized_prices()`

```text
Normalized_t = P_t / P_0 × 100
```

Rebases every ticker to 100 at its own first *valid* price so banks with very
different price levels (e.g. GS ~$130 vs. BAC ~$45) can be compared on one
chart.

## Risk and risk-adjusted return

### Annualized return / volatility

```text
Ann. return = mean(daily) × 252          (arithmetic, not CAGR)
Ann. vol    = std(daily, ddof=1) × √252  (sample standard deviation)
```

Volatility (standard deviation of returns) is the headline risk measure: higher
values mean wilder day-to-day swings.

**Arithmetic annualization is not CAGR.** `mean(daily) × 252` scales the average
daily arithmetic return; CAGR (compound annual growth rate) is the constant rate
that turns the first price into the last:

```text
CAGR = (P_end / P_start)^(252 / n) − 1
```

The two differ materially for volatile series. Over the cached 2006–2015 sample,
WFC's arithmetic annualized return is **+19.2%** while its CAGR is **+8.3%**, and
BAC's is **+8.6%** against a CAGR of **−7.9%** (it ended the decade 56% below its
starting price). Every table in this project uses the arithmetic figure and calls
it an annualized mean return; where a compounded rate is needed (defending a
"what did an investor actually earn" claim), use CAGR.

### Sharpe ratio — `sharpe_ratio()`

```text
Sharpe = (Ann. return − r_f) / Ann. vol
```

Excess return per unit of volatility, with both terms annualized on the same
252-day basis (so the ratio is unit-free). **> 1** is good, **> 2** very good,
**< 0** means the asset underperformed cash on a risk-adjusted basis. NaN when
volatility is zero.

### Sortino ratio — `sortino_ratio()`

Same numerator as Sharpe, but the denominator is **downside deviation** measured
against the risk-free target, averaged over *all* observations:

```text
r_excess,t = r_t − r_f,daily        where r_f,daily = (1 + r_f)^(1/252) − 1
dd         = √( mean( min(r_excess,t, 0)² ) ) × √252
Sortino    = (Ann. return − r_f) / dd
```

Rewards assets whose volatility comes from up-days. Note that `dd` is **not**
the standard deviation of the clipped series (that subtracts the mean of the
downside values and understates the denominator, inflating Sortino) — an earlier
version of this project made exactly that mistake.

The numerator uses the arithmetic annualized return while the target is
converted to a daily rate geometrically; the mismatch is a few basis points on
the numerator and is the usual textbook convention, not a calculation error.

### Maximum drawdown — `max_drawdown()`

```text
Drawdown_t = (P_t − max(P_0..P_t)) / max(P_0..P_t)
Max DD     = min(Drawdown)
```

Worst peak-to-trough loss — the pain a buy-and-hold investor actually felt.
Always ≤ 0; e.g. −0.85 means "fell 85% from its peak".

### Value at Risk / Expected Shortfall — `value_at_risk()` / `conditional_var()`

- **VaR 95% (daily return):** the 5th percentile of daily returns — the loss
  that is exceeded only ~5% of days. Reported as a **signed daily return**, so a
  loss is negative (e.g. −0.035 = a 3.5% one-day loss), not a positive loss
  amount. The summary column name says "daily return" to make this explicit.
- **CVaR (a.k.a. expected shortfall):** the *average* signed return on those
  worst-5% days — always ≤ VaR.

Both are **historical** (empirical quantiles), not parametric — no normality
assumption is made, which matters because return distributions have fat tails
(see the histograms in the notebook). They describe losses seen in *this*
sample only; a loss larger than any observed day is invisible to them.

### Rolling volatility — `rolling_volatility()`

30-day rolling standard deviation of returns, annualized (×√252). Shows *when*
risk spiked — the 2008–2009 surge is the dominant feature.

## Relationships and trends

### Correlation — `correlation_matrix()`

Pearson correlation of daily returns (pairwise complete observations, so a
missing return in one bank only removes that pair's day). Banks in the same
sector typically score ~0.6–0.9: they rise and fall together, which limits
within-sector diversification.

### Moving averages — `moving_averages()`

Simple 30-day and 50-day rolling means of price. When the short average crosses
above (below) the long one, technicians call it a *golden cross* (*death
cross*) — a crude momentum signal, shown here for illustration, not as advice.

### Best / worst days — `best_worst_days()`

Largest single-day gain and loss per ticker, with dates (NaNs excluded). Worst
days cluster in 2008–2009.

## Portfolios (`src/portfolio.py`)

### Method: Monte Carlo search — **not** a solved efficient frontier

1. Draw `N` (default 5,000) random **long-only** weight vectors (weights ≥ 0,
   normalised to sum to 1).
2. Annualize each portfolio's return/volatility from the sample mean vector and
   covariance matrix of daily returns.
3. Report the **max-Sharpe** and **min-volatility** portfolios *found among the
   sampled mixes*, and scatter all `N` as a risk–return cloud coloured by Sharpe.

What this method does and does not deliver:

- It is deliberately optimizer-free (no scipy dependency). The scatter only
  **approximates** the achievable risk–return region; with 5,000 draws the
  boundary is blurry and a denser or constrained solver would find better mixes.
- The two highlighted portfolios are **best-of-sample**, selected by
  `argmax(sharpe)` and `argmin(volatility)` over the simulated set. They are
  **not** mathematically optimal portfolios, and the curve they sit on is **not**
  a computed efficient frontier.
- Weights use **full-sample** means and covariances, i.e. information no 2006
  investor had. The exercise is descriptive, contains look-ahead bias, is not a
  backtest, and makes **no claim about future performance**.
- Nothing here is investment advice or a trading recommendation.

For exact constrained optima (target return, max weight, no shorting), see
Future Work in the [README](../README.md).

### Portfolio math — `portfolio_performance()`

```text
R_p = w · μ × 252                  (annualized return)
σ_p = √(wᵀ Σ w) × √252             (annualized volatility)
Sharpe_p = (R_p − r_f) / σ_p
```

where `μ` and `Σ` are the sample mean and covariance of daily returns.

## Limitations

1. **Price basis** — the default is dividend-adjusted `Adj Close` (total
   return). Scanning raw `Close` instead understates return for dividend payers
   (notably WFC, JPM) by roughly 2–3 percentage points a year over 2006–2015.
   Adjusted prices also assume dividends are reinvested.
2. **Single data source** — Yahoo Finance only, with no independent
   cross-verification; Yahoo occasionally restates historical prices.
3. **Sample dependence** — every statistic describes 2006–2015, a window
   dominated by one crisis. A different period gives different answers.
4. **Survivorship bias** — the six banks all survived 2008; failed banks
   (Lehman, Bear Stearns…) are absent, flattering the sector.
5. **Look-ahead in portfolios** — as above: full-sample inputs, illustrative only.
6. **Gap filling** — `clean_prices()` forward/back-fills gaps of up to five
   trading days (short suspensions), so a handful of prices are carried values,
   not observations. Back-filling at the start of a series can pull an early
   price backwards in time.
7. **Arithmetic annualization** — annualized mean returns are not compounded
   growth rates; see the CAGR note above.
8. **Correlation ≠ causation** — co-movement reflects shared sector/market
   exposure, not one bank driving another.
9. **Not investment advice** — this is an educational analysis of historical data.
