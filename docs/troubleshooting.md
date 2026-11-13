# 🔧 Troubleshooting

Common problems and fixes.

## Data / download issues

### "yfinance returned no data" / SSL / connection errors

Yahoo Finance may be unreachable (offline machine, firewall, rate limit, or a
Yahoo outage). The project handles this automatically:

- The **notebook**, **CLI**, and **dashboard** fall back to synthetic demo data
  and print `Data source : synthetic`.
- To force the demo explicitly: `python scripts/run_analysis.py --synthetic`
  or tick *"Use synthetic demo data"* in the dashboard sidebar.
- `yfinance` prints noisy SSL/connection lines to **stderr** before the
  fallback kicks in — this is cosmetic; the analysis still succeeds.

If you *need* live data: check your connection, wait out rate limits
(`Exception: Too Many Requests` → retry in a few minutes), or upgrade:
`pip install -U yfinance`.

### One ticker fails but others succeed ("N Failed downloads")

Yahoo occasionally drops a ticker (delisted symbol, typo, temporary API gap).
Fixes:

- Check the symbol exists on Yahoo Finance.
- Re-run — transient failures are common.
- Pass `--no-cache` to discard a partially cached download.

### Stale results — I changed tickers/dates but numbers didn't change

The cache (`data/bank_prices.csv`) is validated against your request: it is only
reused when it contains every selected ticker for the selected dates, and it is
then cut down to that window (`end` exclusive, as Yahoo defines it). Before
this check existed, the old CSV silently overrode the dashboard's controls.

If the numbers still look wrong:

- read the caption under the dashboard title — it states the source
  (`cache` / `yahoo` / `synthetic`), the price basis and the **actual** date span;
- force a fresh download with `--no-cache` (CLI) or by deleting
  `data/bank_prices.csv`;
- remember the end date is exclusive: `2016-01-01` ends on `2015-12-31`.

### Which prices are being used — `Close` or `Adj Close`?

The default is **`Adj Close`** (dividend- and split-adjusted total return),
controlled by `config.USE_ADJUSTED_PRICES`. The dashboard caption and the CLI
both print the basis that was used. Raw `Close` excludes dividends, so
annualized returns come out roughly 2–3 pp lower for WFC/JPM over 2006–2015.

## Notebook issues

### `ModuleNotFoundError: No module named 'src'`

The notebook inserts the repo root into `sys.path` in its setup cell — this
only works if the notebook runs from the repository root. Either:

- Open the notebook as `jupyter notebook finance_project.ipynb` from the root, or
- Run the setup cell (cell 0) before any other cell.

### Cells run out of order / `NameError: close`

Use **Kernel → Restart & Run All**. Later sections depend on variables
(`close`, `returns`, `summary`, `corr`) created earlier.

### Pairplot cell is slow

It's already capped at a 500-day sample (`plot_pairwise_scatter(sample=500)`).
Lower it further if needed: `sample=200`.

## Dashboard issues

### `streamlit: command not found`

Install the runtime dependencies: `pip install -r requirements.txt` (it declares
`streamlit`).

### Blank page / old Streamlit deprecation warnings

Upgrade: `pip install -U streamlit` — the dashboard uses the `width="stretch"`
API and the newer theme options, so it needs **Streamlit ≥ 1.49**
(verified on 1.67).

### `ModuleNotFoundError: No module named 'plotly'`

The dashboard's charts are Plotly; install the runtime dependencies:
`pip install -r requirements.txt` (Plotly ≥ 5.18). The notebook and CLI use
matplotlib and do not need it.

### Charts appear but the page looks unstyled (default Streamlit blue)

`.streamlit/config.toml` and the injected CSS in `src/theme.py` provide the dark
theme. Run `streamlit run app.py` **from the repository root** so Streamlit finds
`.streamlit/config.toml`. A hard browser refresh (⌘/Ctrl+Shift+R) clears cached
CSS after an upgrade.

## Test / install issues

### `pytest` fails with import errors

Run from the repo root: `pytest tests/ -q`. The test module adds the root to
`sys.path` itself.

### `pip install` fails with "externally-managed-environment" (PEP 668)

You're on a system Python that blocks global installs. Either use a virtual
environment (recommended):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

or, only if you understand the risk: `pip install --break-system-packages`.

## Still stuck?

1. Check the [Getting Started](getting-started.md) steps in order.
2. Re-run with a clean slate: delete `data/bank_prices.csv`, then
   `python scripts/run_analysis.py --synthetic --no-cache`.
3. Open an issue with your Python version (`python3 --version`), the command
   you ran, and the full error text.
