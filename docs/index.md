# 📚 Documentation

Everything about the **Finance Stock Analytics Dashboard** — a historical
risk-and-return analysis of six U.S. banks (2006–2015) built with Python,
Pandas, NumPy, yFinance, Plotly and Streamlit.

New here? Start with [Getting Started](getting-started.md), then read the
[User Guide](user-guide.md). Everything else is reference material.

## Start here

| Document | What it covers |
|----------|----------------|
| [Getting Started](getting-started.md) | Prerequisites, clone, install, first run, verifying the setup |
| [User Guide](user-guide.md) | The notebook, the dashboard (controls and tabs), and using `src/` as a library |

## Analysis

| Document | What it covers |
|----------|----------------|
| [Metrics Reference](metrics-reference.md) | Every return, risk and correlation metric: formulas, meaning, limitations |
| [Portfolio Simulation](portfolio-simulation.md) | The Monte Carlo risk–return cloud: method, maths, assumptions, what it is *not* |
| [Data & Sources](data-and-sources.md) | Yahoo Finance, the CSV cache, the synthetic fallback, output schemas |
| [Findings](findings.md) | Headline 2006–2015 results and how to reproduce them |

## Build and operate

| Document | What it covers |
|----------|----------------|
| [Architecture](architecture.md) | Repository layout, data flow and module dependencies |
| [API Reference](api-reference.md) | Public functions and constants in `src/` |
| [CLI Reference](cli-reference.md) | `scripts/run_analysis.py` options, outputs and exit codes |
| [Troubleshooting](troubleshooting.md) | Fixes for data, notebook, dashboard, test and install problems |

## Project-level files

| File | Purpose |
|------|---------|
| [README](../README.md) | Project overview, screenshots, quickstart, limitations |
| [CONTRIBUTING](../CONTRIBUTING.md) | Development setup, workflow, code and test guidelines |
| [CHANGELOG](../CHANGELOG.md) | Version history |
| [LICENSE](../LICENSE) | MIT License |

## Conventions used in these docs

- `code` in backticks means a file, function, parameter or something you type.
- Commands assume your working directory is the repository root and that you
  installed dependencies with `pip install -r requirements.txt` (which includes
  the dashboard's `streamlit` and `plotly`; `-r requirements-dev.txt` adds
  `pytest`).
- **Live data** means prices downloaded from Yahoo Finance; **cached data** means
  the stored Yahoo snapshot in `data/bank_prices.csv`; **synthetic data** means
  the built-in reproducible demo series (fixed seed `99`). The three are always
  labelled — see [Data & Sources](data-and-sources.md).
- All figures describe **2006–2015 U.S. banking stocks** and are historical
  statistics, not forecasts.
