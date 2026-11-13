# 📐 Metrics Reference

How every return, risk and relationship number in this project is computed, and
what it means. Implementations live in `src/metrics.py` — see the
[API Reference](api-reference.md) for signatures. Portfolio-specific maths is in
[Portfolio Simulation](portfolio-simulation.md).

## Conventions

| Convention | Value / rule |
|------------|--------------|
| Prices | Daily **closing** prices, **dividend- and split-adjusted** (`Adj Close`, i.e. total return) |
| Returns | **Simple** returns unless stated otherwise |
| Annualization | **252 trading days** per year (`TRADING_DAYS` in `src/config.py`) |
| Risk-free rate | **2%** per year (`RISK_FREE_RATE`) |
| Data provenance | Prices are **loaded, not verified** — Yahoo Finance is the only source |

Raw `Close` omits dividends and understates long-run returns; set
`config.USE_ADJUSTED_PRICES = False` to reproduce that older behaviour (see
[Limitations](#limitations)).

## Returns

### Daily returns — `daily_returns()`

```text
r_t = P_t / P_{t-1} − 1
```

Percentage gain or loss per trading day. The first row is dropped (no prior
price). No filling happens here: a missing price yields a missing return rather
than a silent zero. Gap filling happens at load time in
`data.clean_prices()` — see [Limitations](#limitations).

### Cumulative returns — `cumulative_returns()`

```text
Growth_t = ∏(1 + r_i)   for i = 1..t
```

Value of a $1 investment over time, shown as **Growth of $1** in the summary
table. Total return over the window is `Growth_end − 1`.

### Normalized prices — `normalized_prices()`

```text
Normalized_t = P_t / P_0 × 100
```

Rebases each ticker to 100 at its own first valid price, so banks with very
different price levels (GS ≈ $130 vs. BAC ≈ $45) can be compared on one chart.

## Risk and risk-adjusted return

### Annualized return and volatility

```text
Ann. return = mean(daily) × 252          (arithmetic, not CAGR)
Ann. vol    = std(daily, ddof=1) × √252  (sample standard deviation)
```

Volatility is the headline risk measure: higher values mean wilder day-to-day
swings.

**Arithmetic annualization is not CAGR.** `mean(daily) × 252` scales the average
daily arithmetic return; CAGR is the constant rate that turns the first price
into the last:

```text
CAGR = (P_end / P_start)^(252 / n) − 1
```

The two differ materially for volatile series. Over the cached 2006–2015 sample,
WFC's arithmetic annualized return is **+19.2%** while its CAGR is **+8.3%**, and
BAC's is **+8.6%** against a CAGR of **−7.9%** (it ended the decade 56% below its
starting price). Every table in this project reports the arithmetic figure and
labels it an annualized mean return; use CAGR when defending a "what did an
investor actually earn" claim.

### Sharpe ratio — `sharpe_ratio()`

```text
Sharpe = (Ann. return − r_f) / Ann. vol
```

Excess return per unit of volatility, with both terms annualized on the same
252-day basis, so the ratio is unit-free. **> 1** is good, **> 2** very good,
**< 0** means the asset underperformed cash on a risk-adjusted basis. NaN when
volatility is zero.

### Sortino ratio — `sortino_ratio()`

Same numerator as Sharpe, but the denominator is **downside deviation** measured
against the risk-free target and averaged over *all* observations:

```text
r_excess,t = r_t − r_f,daily        where r_f,daily = (1 + r_f)^(1/252) − 1
dd         = √( mean( min(r_excess,t, 0)² ) ) × √252
Sortino    = (Ann. return − r_f) / dd
```

This rewards assets whose volatility comes from up-days. `dd` is **not** the
standard deviation of the clipped series — that subtracts the mean of the
downside values, understates the denominator and inflates Sortino.

The numerator uses the arithmetic annualized return while the target is
converted to a daily rate geometrically; the mismatch is a few basis points and
is the usual textbook convention, not a calculation error.

### Maximum drawdown — `max_drawdown()`

```text
Drawdown_t = (P_t − max(P_0..P_t)) / max(P_0..P_t)
Max DD     = min(Drawdown)
```

Worst peak-to-trough loss — the pain a buy-and-hold investor actually felt.
Always ≤ 0; `−0.85` means "fell 85% from its peak".

### Value at Risk and Expected Shortfall — `value_at_risk()` / `conditional_var()`

| Measure | Definition | Sign convention |
|---------|------------|-----------------|
| VaR 95% (daily return) | 5th percentile of daily returns | Signed return: a loss is **negative** (e.g. −0.035 = a 3.5% one-day loss) |
| CVaR / expected shortfall | Average signed return on the worst-5% days | Always ≤ VaR |

Both are **historical** (empirical quantiles), not parametric: no normality
assumption is made, which matters because return distributions have fat tails.
They describe losses seen in *this* sample only — a loss larger than any observed
day is invisible to them.

### Rolling volatility — `rolling_volatility()`

30-day rolling standard deviation of returns, annualized (×√252). Shows *when*
risk spiked; the 2008–2009 surge is the dominant feature.

## Relationships and trends

### Correlation — `correlation_matrix()`

Pearson correlation of daily returns, using pairwise complete observations, so a
missing return in one bank only removes that pair's day. Banks in the same sector
typically score ~0.6–0.9: they rise and fall together, which limits
within-sector diversification.

### Moving averages — `moving_averages()`

Simple 30-day and 50-day rolling means of price. When the short average crosses
above (below) the long one, technicians call it a *golden cross* (*death cross*)
— a crude momentum signal, shown for illustration, not as advice.

### Best and worst days — `best_worst_days()`

Largest single-day gain and loss per ticker, with dates (NaNs excluded). Worst
days cluster in 2008–2009.

## Limitations

1. **Price basis.** The default is dividend-adjusted `Adj Close` (total return).
   Scanning raw `Close` understates return for dividend payers (notably WFC, JPM)
   by roughly 2–3 percentage points a year over 2006–2015. Adjusted prices also
   assume dividends are reinvested.
2. **Single data source.** Yahoo Finance only, with no independent
   cross-verification; Yahoo occasionally restates historical prices.
3. **Sample dependence.** Every statistic describes 2006–2015, a window dominated
   by one crisis. A different period gives different answers.
4. **Survivorship bias.** The six banks all survived 2008; failed banks (Lehman,
   Bear Stearns…) are absent, which flatters the sector.
5. **Look-ahead in portfolios.** The simulation uses full-sample inputs — see
   [Portfolio Simulation](portfolio-simulation.md).
6. **Gap filling.** `clean_prices()` forward/back-fills gaps of up to five trading
   days (short suspensions), so a handful of prices are carried values, not
   observations. Back-filling at the start of a series can pull an early price
   backwards in time.
7. **Arithmetic annualization.** Annualized mean returns are not compounded growth
   rates; see the CAGR note above.
8. **Correlation ≠ causation.** Co-movement reflects shared sector and market
   exposure, not one bank driving another.
9. **Simulation assumptions.** The portfolio tab assumes buy-and-hold, no
   transaction costs, no taxes, no rebalancing and stable inputs; uniform random
   sampling only approximates the achievable region.
10. **Not investment advice.** This is an educational analysis of historical data.
