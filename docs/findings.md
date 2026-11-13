# 📊 Findings

Key results from the analysis, how to interpret them, and how to reproduce them.

## Data behind these numbers

The headline table below comes from **`data/summary.csv` and
`data/correlation.csv`, regenerated from the cached Yahoo Finance snapshot**
(`data/bank_prices.csv`, `Adj Close`, 2,517 sessions, 2006-01-03 → 2015-12-31,
risk-free rate 2%). Source label: `cache` — a stored Yahoo Finance download, not
a live request and **not independently verified** against another provider.

## Headline results (cached Yahoo data, 2006–2015)

| Bank | Ann. mean return | Ann. volatility | Sharpe | Sortino | Max drawdown |
|------|------------------|-----------------|--------|---------|--------------|
| WFC | +19.2% | 47.9% | 0.36 | 0.57 | −79.0% |
| JPM | +17.0% | 43.9% | 0.34 | 0.52 | −68.1% |
| MS | +13.9% | 59.9% | 0.20 | 0.32 | −87.1% |
| GS | +12.5% | 40.3% | 0.26 | 0.39 | −78.8% |
| BAC | +8.6% | 58.2% | 0.11 | 0.17 | −93.4% |
| C | −2.5% | 61.4% | −0.07 | −0.11 | −98.0% |

Annualized returns are **arithmetic** (`mean(daily) × 252`), not CAGR — see
[Metrics Reference](metrics-reference.md#annualized-return-and-volatility). Over this window
the compounded rates are lower, and negative for BAC (−7.9%) even though its
arithmetic figure is positive.

| # | Finding | Where to see it |
|---|---------|-----------------|
| 1 | **Citigroup (C)** had the **highest volatility** (61.4%) and the deepest drawdown (−98.0%), and was the only bank with a negative annualized mean return | Summary table, `risk_return.png` |
| 2 | **Goldman Sachs (GS)** was the **most stable** (lowest volatility, 40.3%) | Summary table, `risk_return.png` |
| 3 | **BAC–WFC** had the **strongest positive correlation** (0.83) | `correlation_heatmap.png` |
| 4 | **Volatility spiked in 2008–2009** across all banks | `rolling_volatility.png`, `drawdown.png` |
| 5 | Banks are **strongly correlated** (average pairwise 0.72, range 0.60 MS–WFC to 0.83 BAC–WFC), limiting within-sector diversification | Heatmap + portfolio cloud |

## How to read the charts

- **Risk vs. return** (`risk_return.png`) — ideal assets sit top-left (high
  return, low risk). Bubble size ∝ Sharpe ratio: bigger means better
  risk-adjusted compensation.
- **Rolling volatility** (`rolling_volatility.png`) — the 2008–2009 surge
  dwarfs everything else; post-2012 volatility stays structurally lower.
- **Drawdown** (`drawdown.png`) — depth below previous peak. C and BAC fell
  furthest and took longest to surface.
- **Return distributions** (`return_distributions.png`) — roughly bell-shaped
  but with **fat tails**: ±3σ days occur far more often than a normal model
  predicts (that's why we use historical, not parametric, VaR).
- **Monte Carlo portfolio cloud** (`efficient_frontier.png`, legacy filename) — each dot is
  a random long-only mix; ★ marks the best-of-sample max-Sharpe and
  min-volatility mixes. Because correlations are high, the cloud is relatively
  flat: mixing banks cuts volatility only modestly versus holding the best
  single bank. This is a **random Monte Carlo sample, not a solved efficient
  frontier**.

## Reproducing these results

```bash
# Cached or live data (the CSVs in data/ come from the cached snapshot)
python scripts/run_analysis.py

# Offline demo (deterministic seed 99 — same charts on every machine)
python scripts/run_analysis.py --synthetic --no-cache
```

The notebook's section 8 derives the same bullets from whatever data is loaded,
and `data/summary.csv` + `data/correlation.csv` contain the exact numbers.

> **Note:** the committed `images/` were rendered from synthetic demo data in an
> offline environment, so the charts show the same *patterns* with different
> values from the table above. Re-run with internet access to regenerate them
> from Yahoo data. Synthetic runs are always labelled and never blended with real
> prices.
