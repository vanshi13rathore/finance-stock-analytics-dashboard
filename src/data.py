"""Data loading utilities: download, cache, clean, and (offline) simulate prices.

The module is resilient to the two big real-world annoyances of this project:

1. ``yfinance`` changed its default column layout across versions
   (``(Price, Ticker)`` vs ``(Ticker, Price)``), so extraction is layout-aware.
2. The Yahoo API may be unreachable (offline sandbox, rate limits), so every
   entry point can fall back to a deterministic synthetic dataset or a local
   CSV cache instead of crashing.

Price basis
-----------
Return and risk calculations use **dividend- and split-adjusted** closing
prices (``Adj Close``) whenever yfinance provides them, because raw ``Close``
omits dividends and would understate total return. ``load_prices_detailed()``
reports which basis was used in ``LoadedPrices.price_basis`` so callers can
label it honestly. If ``Adj Close`` is unavailable the loader falls back to raw
``Close`` and emits a warning.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RANDOM_SEED

CLOSE_COL = "Close"
ADJUSTED_COL = "Adj Close"

#: Slack allowed when checking whether a cached CSV covers a requested range:
#: the first trading day can be a few days after ``start`` (weekends/holidays)
#: and yfinance treats ``end`` as exclusive, so the last row sits just before it.
CACHE_TOLERANCE_DAYS = 7


class DataDownloadError(RuntimeError):
    """Raised when price data cannot be downloaded and no fallback is allowed."""


@dataclass(frozen=True)
class LoadedPrices:
    """A price frame plus everything needed to describe it honestly in a UI.

    Attributes
    ----------
    close:
        Cleaned (dates × tickers) price frame.
    source:
        ``"cache"``, ``"yahoo"`` or ``"synthetic"``.
    price_basis:
        ``"Adj Close"`` (dividends/splits included) or ``"Close"`` (raw).
    note:
        Human-readable explanation of anything unusual (fallback used, stale
        cache refreshed, tickers dropped). Empty on a clean load.
    """

    close: pd.DataFrame
    source: str
    price_basis: str
    note: str = ""


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def download_prices(
    tickers: list[str],
    start: str,
    end: str,
    auto_adjust: bool = False,
    cache_path: Path | str | None = None,
) -> pd.DataFrame:
    """Download OHLCV data with ``yfinance`` (optionally writing a CSV cache).

    Parameters
    ----------
    tickers:
        Stock tickers, e.g. ``["BAC", "C", "GS", "JPM", "MS", "WFC"]``.
    start, end:
        Date range (``YYYY-MM-DD``). ``end`` is **exclusive**, matching the
        yfinance/Yahoo API.
    auto_adjust:
        If False, keep raw ``Close`` plus an ``Adj Close`` column.
    cache_path:
        Where to store the raw download. ``None`` disables caching. Note that
        this function never *reads* a cache — use :func:`load_prices_detailed`,
        which validates that a cache covers the requested tickers and dates.

    Returns
    -------
    Raw ``yfinance`` DataFrame (possibly with MultiIndex columns).

    Raises
    ------
    DataDownloadError
        If the download yields an empty frame (network blocked, bad tickers…).
    """
    import yfinance as yf  # local import so metrics/plots stay lightweight

    df = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        group_by="ticker",
        threads=False,
        progress=False,
    )
    if df is None or df.empty:
        raise DataDownloadError(
            "yfinance returned no data. Check your connection/tickers, "
            "or use `synthetic_fallback=True` / a cached CSV."
        )
    if cache_path is not None:
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)
    return df


# ---------------------------------------------------------------------------
# Extraction / cleaning
# ---------------------------------------------------------------------------
def _available_columns(raw: pd.DataFrame) -> set[str]:
    """Every label present in a flat or MultiIndex column frame."""
    if isinstance(raw.columns, pd.MultiIndex):
        return {
            str(label)
            for level in range(raw.columns.nlevels)
            for label in raw.columns.get_level_values(level)
        }
    return {str(c) for c in raw.columns}


def extract_close(raw: pd.DataFrame, price_col: str = CLOSE_COL) -> pd.DataFrame:
    """Extract a (dates × tickers) price frame from a raw download.

    Handles every ``yfinance`` layout we have seen in the wild:

    * MultiIndex ``(ticker, price)``  (``group_by="ticker"``)
    * MultiIndex ``(price, ticker)``  (newer ``yfinance`` default)
    * Flat columns for a single-ticker download
    """
    if not isinstance(raw.columns, pd.MultiIndex):
        if price_col in raw.columns:
            return raw[[price_col]].copy()
        raise KeyError(f"Column {price_col!r} not found in {list(raw.columns)}")

    level0 = set(raw.columns.get_level_values(0))
    level1 = set(raw.columns.get_level_values(1))

    if price_col in level1:  # (ticker, price) layout
        close = raw.xs(price_col, axis=1, level=1)
    elif price_col in level0:  # (price, ticker) layout
        close = raw.xs(price_col, axis=1, level=0)
    else:  # pragma: no cover - defensive
        raise KeyError(f"Column {price_col!r} not found in {list(level0 | level1)}")

    close.columns = [str(c) for c in close.columns]
    return close


def extract_prices(
    raw: pd.DataFrame, prefer_adjusted: bool = True
) -> tuple[pd.DataFrame, str]:
    """Extract prices, preferring ``Adj Close`` (total return) over ``Close``.

    Returns
    -------
    (prices, price_basis) where ``price_basis`` is the column that was used.
    """
    available = _available_columns(raw)
    if prefer_adjusted and ADJUSTED_COL in available:
        return extract_close(raw, ADJUSTED_COL), ADJUSTED_COL
    if prefer_adjusted:
        warnings.warn(
            "'Adj Close' is missing from the data; falling back to raw 'Close', "
            "which excludes dividends (total return will be understated).",
            stacklevel=2,
        )
    return extract_close(raw, CLOSE_COL), CLOSE_COL


def clean_prices(close: pd.DataFrame, max_fill_days: int = 5) -> pd.DataFrame:
    """Sort, de-duplicate, and fill small gaps in a price frame.

    * sorts the index and drops duplicated dates,
    * forward-fills gaps up to ``max_fill_days`` (short suspensions/holidays),
    * drops any remaining all-NaN rows and reports what was fixed.
    """
    cleaned = close.sort_index()
    cleaned = cleaned[~cleaned.index.duplicated(keep="first")]
    n_missing_before = int(cleaned.isna().sum().sum())
    cleaned = cleaned.ffill(limit=max_fill_days).bfill(limit=max_fill_days)
    cleaned = cleaned.dropna(how="all")
    n_missing_after = int(cleaned.isna().sum().sum())
    if n_missing_before:
        warnings.warn(
            f"Filled/dropped {n_missing_before - n_missing_after} missing price "
            f"points ({n_missing_after} NaNs remain).",
            stacklevel=2,
        )
    return cleaned


# ---------------------------------------------------------------------------
# Offline fallback: deterministic synthetic prices
# ---------------------------------------------------------------------------
def generate_synthetic_prices(
    tickers: list[str],
    start: str = "2006-01-01",
    end: str = "2016-01-01",
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Generate reproducible business-day prices (geometric Brownian motion).

    A high-volatility regime is injected around 2008–2009 so the demo data
    reproduces the narrative of the real sample (crisis spike in volatility).
    These numbers are **simulated**: they are never presented as Yahoo Finance
    data (callers label the source ``"synthetic"``).

    Different drifts/volatilities per ticker keep Citigroup the riskiest and
    Goldman Sachs relatively calm — mirroring the real findings.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)

    # Per-ticker (annual drift, base annual volatility, starting price).
    params = {
        "BAC": (0.02, 0.35, 45.0),
        "C": (0.01, 0.45, 50.0),
        "GS": (0.06, 0.25, 130.0),
        "JPM": (0.05, 0.28, 40.0),
        "MS": (0.03, 0.38, 60.0),
        "WFC": (0.04, 0.27, 35.0),
    }
    crisis = (dates >= "2008-01-01") & (dates <= "2009-12-31")
    # Shared market factor with a mild upward drift so post-crisis years recover.
    market = rng.standard_normal(n) + np.where(crisis, -0.02, 0.035)

    prices = {}
    for i, ticker in enumerate(tickers):
        drift, vol, start_price = params.get(ticker, (0.04, 0.30, 50.0))
        daily_drift = drift / 252
        daily_vol = vol / np.sqrt(252)
        shocks = rng.standard_normal(n)
        # Crisis regime: 2.5x volatility + negative drift.
        daily_vols = np.where(crisis, daily_vol * 2.5, daily_vol)
        daily_drifts = np.where(crisis, -0.0015, daily_drift)
        # Correlate tickers through the shared market factor for realism.
        rets = daily_drifts + daily_vols * (0.45 * shocks + 0.55 * market)
        prices[ticker] = start_price * np.exp(np.cumsum(rets))
    return pd.DataFrame(prices, index=dates)


# ---------------------------------------------------------------------------
# One-stop loader
# ---------------------------------------------------------------------------
def _validate_request(tickers: list[str], start: str, end: str) -> None:
    """Reject requests that cannot produce data (empty tickers, inverted dates)."""
    if not tickers:
        raise ValueError("Select at least one ticker.")
    try:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid date(s): start={start!r}, end={end!r}") from exc
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise ValueError(f"Invalid date(s): start={start!r}, end={end!r}")
    if start_ts >= end_ts:
        raise ValueError(
            f"Start date ({start_ts.date()}) must be before end date ({end_ts.date()})."
        )


def _cache_covers(
    close: pd.DataFrame, tickers: list[str], start: str, end: str
) -> bool:
    """True when a cached frame holds every requested ticker for the whole range.

    Without this check the cache would silently override the user's ticker and
    date selections (the dashboard asked for proof the cache was reusable).
    """
    if close is None or close.empty:
        return False
    if any(t not in close.columns for t in tickers):
        return False
    tolerance = pd.Timedelta(days=CACHE_TOLERANCE_DAYS)
    return bool(
        close.index.min() <= pd.Timestamp(start) + tolerance
        and close.index.max() >= pd.Timestamp(end) - tolerance
    )


def load_prices_detailed(
    tickers: list[str],
    start: str,
    end: str,
    cache_path: Path | str | None = None,
    use_cache: bool = True,
    synthetic_fallback: bool = True,
    prefer_adjusted: bool = True,
) -> LoadedPrices:
    """Load clean prices, trying a *valid* cache → download → synthetic.

    A cache is only reused when it contains every requested ticker and spans
    the requested dates; otherwise the data are downloaded afresh.

    Raises
    ------
    ValueError
        For an empty ticker list or ``start >= end``.
    DataDownloadError
        When downloading fails, no usable cache exists, and
        ``synthetic_fallback`` is False.
    """
    tickers = [str(t) for t in tickers]
    _validate_request(tickers, start, end)

    cache_note = ""
    if use_cache and cache_path is not None and Path(cache_path).exists():
        name = Path(cache_path).name
        try:
            raw_cached = pd.read_csv(cache_path, header=[0, 1], index_col=0,
                                     parse_dates=True)
            cached_close, cached_basis = extract_prices(raw_cached, prefer_adjusted)
            if _cache_covers(cached_close, tickers, start, end):
                # A cache that spans more than the request is fine, but it must
                # be cut down to the requested window (end exclusive, as in
                # yfinance) instead of returning the whole cached history.
                window = cached_close.loc[
                    (cached_close.index >= pd.Timestamp(start))
                    & (cached_close.index < pd.Timestamp(end)),
                    tickers,
                ]
                if len(window) >= 2:
                    return LoadedPrices(
                        close=clean_prices(window),
                        source="cache",
                        price_basis=cached_basis,
                    )
            cache_note = (
                f"Local cache {name} does not cover {', '.join(tickers)} for "
                f"{start} → {end}; data were re-downloaded from Yahoo Finance."
            )
        except Exception as exc:  # corrupt/legacy cache must not break loading
            cache_note = (
                f"Local cache {name} could not be read ({exc!r}); "
                "data were re-downloaded from Yahoo Finance."
            )

    try:
        raw = download_prices(tickers, start, end, cache_path=cache_path)
        close, basis = extract_prices(raw, prefer_adjusted)
        missing = [t for t in tickers if t not in close.columns]
        if missing:
            warnings.warn(
                f"No data returned for {missing}; excluded from the analysis.",
                stacklevel=2,
            )
        # Keep the caller's ticker order so tables/charts are deterministic.
        close = close[[t for t in tickers if t in close.columns]]
        cleaned = clean_prices(close)
        if cleaned.empty:
            raise DataDownloadError("Yahoo Finance returned no data for this range.")
        return LoadedPrices(cleaned, "yahoo", basis, cache_note)
    except Exception as exc:  # network blocked, API changed, … — don't crash
        if not synthetic_fallback:
            raise DataDownloadError(str(exc)) from exc
        synthetic = generate_synthetic_prices(tickers, start, end)
        if synthetic.empty:
            raise DataDownloadError(
                f"No price data available for {start} → {end} ({exc})."
            ) from exc
        note = (
            f"Live download failed ({exc}); showing reproducible SYNTHETIC demo "
            "data — these are simulated numbers, not Yahoo Finance prices."
        )
        if cache_note:
            note = f"{note} {cache_note}"
        warnings.warn(note, stacklevel=2)
        return LoadedPrices(clean_prices(synthetic), "synthetic", "synthetic", note)


def load_prices(
    tickers: list[str],
    start: str,
    end: str,
    cache_path: Path | str | None = None,
    use_cache: bool = True,
    synthetic_fallback: bool = True,
    prefer_adjusted: bool = True,
) -> tuple[pd.DataFrame, str]:
    """Backwards-compatible wrapper around :func:`load_prices_detailed`.

    Returns
    -------
    (close_prices, source) where ``source`` is one of
    ``"cache"``, ``"yahoo"``, or ``"synthetic"``. Use
    :func:`load_prices_detailed` when you also need the price basis and notes.
    """
    loaded = load_prices_detailed(
        tickers,
        start,
        end,
        cache_path=cache_path,
        use_cache=use_cache,
        synthetic_fallback=synthetic_fallback,
        prefer_adjusted=prefer_adjusted,
    )
    return loaded.close, loaded.source


def describe_data(close: pd.DataFrame) -> pd.DataFrame:
    """Quick overview table: date range, rows, missing values per ticker."""
    return pd.DataFrame(
        {
            "start": [close.index.min()] * len(close.columns),
            "end": [close.index.max()] * len(close.columns),
            "rows": [len(close)] * len(close.columns),
            "missing": close.isna().sum().tolist(),
            "first_price": close.iloc[0].tolist(),
            "last_price": close.iloc[-1].tolist(),
        },
        index=list(close.columns),
    )
