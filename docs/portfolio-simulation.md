# 🎯 Portfolio Simulation

The dashboard's **Portfolio** tab and `src/portfolio.py` explore how these six
banks trade off risk against return. This page states exactly what the method
does, what it deliberately does not do, and which assumptions sit behind the
numbers.

> **Short version:** this is a **Monte Carlo sampling exercise with uniform random
> long-only weights**. It is not an optimiser, it does not compute an efficient
> frontier, and its output is not a prediction, recommendation or guarantee.

## Method

1. Draw `N` random **long-only** weight vectors (default `N = 5,000`;
   weights ≥ 0, normalised to sum to 100%). Sampling is **uniform** over that
   simplex — every valid mix is equally likely, nothing is optimised. The
   dashboard passes `config.RANDOM_SEED` (99); the CLI and direct calls to
   `random_portfolios()` use the function default (`seed = 42`).
2. Annualize each portfolio's expected return and volatility from the sample mean
   vector and covariance matrix of daily returns.
3. Report the **maximum-Sharpe** and **minimum-volatility** portfolios *found
   among the sampled mixes* (`argmax(sharpe)`, `argmin(volatility)`), and scatter
   all `N` points as a risk–return cloud coloured by Sharpe ratio.

The implementation needs only `pandas`/`numpy` — no `scipy`, no solver.

## Portfolio maths — `portfolio_performance()`

```text
R_p     = w · μ × 252            annualized expected return
σ_p     = √(wᵀ Σ w) × √252       annualized volatility
Sharpe_p = (R_p − r_f) / σ_p
```

`μ` and `Σ` are the sample mean vector and covariance matrix of daily returns
over the selected window.

## What this is *not*

| Claim | Reality |
|-------|---------|
| "Efficient frontier" | ❌ No frontier is computed. The scatter only **approximates** the achievable risk–return region, and with 5,000 draws the boundary is blurry. |
| "Optimal portfolios" | ❌ The two highlighted portfolios are **best-of-sample**, not mathematically optimal. A constrained solver would find better mixes. |
| "Prediction" / "forecast" | ❌ Inputs are historical full-sample statistics; nothing is projected forward. |
| "Backtest" | ❌ Weights and returns come from the same window, so the exercise contains look-ahead bias. |
| "Investment advice" | ❌ Educational illustration of historical data only. |

## Assumptions

- **Buy-and-hold** for the whole window.
- **No transaction costs, taxes or rebalancing** — real portfolios pay all three.
- **Stable means and covariances** across the window.
- **Full-sample inputs**, i.e. information no 2006 investor had (look-ahead).
- Long-only, fully invested (weights sum to 100%), no leverage or shorting.

## Reading the output

- **Cloud colour** encodes the Sharpe ratio (annualized, risk-free 2% by default;
  the sidebar slider changes it).
- **Max-Sharpe / min-volatility markers** answer "best and calmest of the mixes we
  happened to sample this run", not "the best possible".
- **Weights table** lists the six allocations for those two portfolios as
  percentages, with a CSV download.
- Because the seed is fixed (`RANDOM_SEED = 99` in the dashboard, `42` in the
  CLI), re-running with the same tickers, dates and portfolio count reproduces
  the same cloud; changing any of those changes it.

Portfolio results for the cached 2006–2015 snapshot are quoted in
[Findings](findings.md). For the risk measures used to rank these portfolios, see
[Metrics Reference](metrics-reference.md).
