"""Finance Stock Analytics — Streamlit dashboard.

Phase 2 UI: dark institutional theme, KPI tiles, interactive Plotly charts and
downloadable tables. Financial maths is unchanged from Phase 1 — everything
displayed comes from ``src.metrics`` / ``src.portfolio`` via cached wrappers.

Run with::

    pip install -r requirements-dev.txt
    streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import charts, config, data, metrics, portfolio, theme  # noqa: E402

SUBTITLE = (
    "Historical performance, risk and portfolio analysis of six major US "
    "banking stocks."
)
DATA_TTL_SECONDS = 900  # reuse a live download for 15 minutes per session

st.set_page_config(
    page_title="Finance Stock Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(theme.CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached data + analysis (keeps re-runs cheap and avoids repeat downloads)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=DATA_TTL_SECONDS)
def load_market_data(
    tickers: tuple[str, ...], start: str, end: str, synthetic: bool
) -> data.LoadedPrices:
    """Load prices once per unique (tickers, dates, source) combination."""
    if synthetic:
        return data.LoadedPrices(
            close=data.generate_synthetic_prices(
                list(tickers), start, end, seed=config.RANDOM_SEED
            ),
            source="synthetic",
            price_basis="synthetic",
            note=(
                "You selected offline demo mode: these prices are simulated, "
                "not real market data."
            ),
        )
    return data.load_prices_detailed(
        list(tickers),
        start,
        end,
        cache_path=config.CACHE_FILE,
        synthetic_fallback=True,
        prefer_adjusted=config.USE_ADJUSTED_PRICES,
    )


@st.cache_data(show_spinner=False)
def analyse(
    close: pd.DataFrame, risk_free_rate: float, var_level: float
) -> dict[str, pd.DataFrame]:
    """All derived tables for one price frame (one cache hit per rerun)."""
    rets = metrics.daily_returns(close)
    return {
        "returns": rets,
        "summary": metrics.summary_table(close, rets, risk_free_rate, var_level),
        "correlation": metrics.correlation_matrix(rets),
        "cumulative": metrics.cumulative_returns(rets),
        "normalized": metrics.normalized_prices(close),
        "drawdown": metrics.drawdown_series(close),
        "extremes": metrics.best_worst_days(rets),
    }


@st.cache_data(show_spinner="Simulating random portfolios…")
def simulate(
    returns: pd.DataFrame, n_portfolios: int, risk_free_rate: float, seed: int
) -> tuple[pd.DataFrame, portfolio.PortfolioResult]:
    """Monte Carlo long-only simulation (cached by returns + parameters)."""
    return portfolio.random_portfolios(
        returns, n_portfolios=n_portfolios, risk_free_rate=risk_free_rate, seed=seed
    )


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------
def section(title: str, description: str = "") -> None:
    st.markdown(
        theme.section_html(theme.Section(title, description)),
        unsafe_allow_html=True,
    )


def chart(fig, alt: str) -> None:
    st.plotly_chart(
        fig,
        width="stretch",
        theme=None,  # keep the dashboard's own Plotly template
        config=theme.PLOTLY_CONFIG,
        alt=alt,
    )


def empty_state(message: str) -> None:
    st.markdown(theme.empty_state(message), unsafe_allow_html=True)


def summary_display(frame: pd.DataFrame) -> pd.DataFrame:
    """Percent-scaled copy of the summary table for display only.

    The underlying metrics stay in decimal form; scaling here lets the table's
    printf formats render ``12.3%`` while keeping column sorting correct.
    """
    var_col = next((c for c in frame.columns if str(c).startswith("VaR")), None)
    return pd.DataFrame(
        {
            "Ticker": [str(t) for t in frame.index],
            "Bank": [config.BANK_NAMES.get(str(t), str(t)) for t in frame.index],
            "Annual return": frame["Ann. Return"] * 100,
            "Annual volatility": frame["Ann. Volatility"] * 100,
            "Sharpe": frame["Sharpe"],
            "Sortino": frame["Sortino"],
            "Max drawdown": frame["Max Drawdown"] * 100,
            "Daily VaR 95%": (frame[var_col] * 100) if var_col else float("nan"),
            "Best day": frame["Best Day"] * 100,
            "Worst day": frame["Worst Day"] * 100,
            "Growth of $1": frame["Growth of $1"],
        }
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(theme.brand_block(), unsafe_allow_html=True)

    st.markdown(theme.sidebar_label("Universe"), unsafe_allow_html=True)
    tickers = st.multiselect(
        "Banks",
        config.BANKS,
        default=config.BANKS,
        help="Pick one or more banks. Portfolio analysis needs at least two.",
    )

    st.markdown(theme.sidebar_label("Period"), unsafe_allow_html=True)
    start = st.date_input(
        "Start date",
        value=dt.date.fromisoformat(config.START_DATE),
        min_value=dt.date(1990, 1, 1),
        max_value=dt.date.today(),
        help="First trading day included in the analysis.",
    )
    end = st.date_input(
        "End date",
        value=dt.date.fromisoformat(config.END_DATE),
        min_value=dt.date(1990, 1, 1),
        max_value=dt.date.today(),
        help="Yahoo Finance treats this date as exclusive.",
    )

    st.markdown(theme.sidebar_label("Assumptions"), unsafe_allow_html=True)
    risk_free_pct = st.slider(
        "Risk-free rate (%)",
        0.0,
        10.0,
        value=config.RISK_FREE_RATE * 100,
        step=0.25,
        format="%.2f%%",
        help="Annual rate subtracted from returns in the Sharpe and Sortino ratios.",
    )
    short_ma = st.slider(
        "Short moving average",
        5,
        100,
        config.MA_SHORT_WINDOW,
        help="Window (trading days) for the fast moving average.",
    )
    long_ma = st.slider(
        "Long moving average",
        20,
        200,
        config.MA_LONG_WINDOW,
        help="Window (trading days) for the slow moving average.",
    )
    vol_window = st.slider(
        "Rolling volatility window",
        10,
        120,
        config.ROLLING_VOL_WINDOW,
        help="Look-back window for the rolling volatility chart.",
    )

    st.markdown(theme.sidebar_label("Data source"), unsafe_allow_html=True)
    use_synthetic = st.checkbox(
        "Use synthetic demo data",
        value=False,
        help=(
            "Simulated prices for offline demos and tests. Always labelled as "
            "synthetic — never presented as market data."
        ),
    )

    st.markdown(theme.sidebar_label("Ticker colours"), unsafe_allow_html=True)
    st.markdown(
        theme.legend_rows(config.BANKS, config.BANK_NAMES), unsafe_allow_html=True
    )

    with st.expander("About this dashboard"):
        st.markdown(
            "Historical analysis of six US banks over 2006–2016, using "
            "dividend-adjusted prices from Yahoo Finance.\n\n"
            "Returns are annualized with 252 trading days; volatility is the "
            "daily standard deviation × √252. VaR is the 5% historical "
            "quantile of daily returns (negative = loss).\n\n"
            "Nothing here is investment advice."
        )

risk_free = risk_free_pct / 100.0

# ---------------------------------------------------------------------------
# Input validation (before any data or chart work)
# ---------------------------------------------------------------------------
if not tickers:
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error("Select at least one bank in the sidebar to continue.")
    st.stop()

if start >= end:
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error(
        f"Start date ({start:%d %b %Y}) must be before end date "
        f"({end:%d %b %Y})."
    )
    st.stop()

if short_ma == long_ma:
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error(
        "Short and long moving-average windows must be different — "
        f"both are set to {short_ma} days."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
try:
    with st.spinner("Loading price data…"):
        loaded = load_market_data(tuple(tickers), str(start), str(end), use_synthetic)
except ValueError as exc:  # invalid dates / empty selection
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error(f"This analysis cannot run: {exc}")
    st.stop()
except Exception as exc:  # noqa: BLE001 - readable message, details in diagnostics
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error(
        "Price data could not be loaded. Check your internet connection and try "
        "again, or enable synthetic demo data in the sidebar."
    )
    with st.expander("Diagnostics"):
        st.code(f"{type(exc).__name__}: {exc}")
    st.stop()

close = loaded.close
if close.empty or len(close) < 2:
    st.markdown(theme.hero("Finance Stock Analytics", SUBTITLE), unsafe_allow_html=True)
    st.error(
        f"No usable price data between {start:%d %b %Y} and {end:%d %b %Y}. "
        "Try a wider date range."
    )
    st.stop()

bundle = analyse(close, risk_free, config.VAR_LEVEL)
returns = bundle["returns"]
summary = bundle["summary"]
correlation = bundle["correlation"]

is_synthetic = loaded.source == "synthetic"
basis_label = "Simulated" if is_synthetic else loaded.price_basis
source_label = {
    "yahoo": "Yahoo Finance (live)",
    "cache": "Yahoo Finance (cached CSV)",
    "synthetic": "Simulated prices",
}.get(loaded.source, loaded.source)
# Provenance labels are deliberately factual. The project *loads* Yahoo Finance
# prices but runs no independent verification of them, so the dashboard must not
# claim "verified" prices. Keeping one label per source means a cached CSV or a
# simulated dataset can never be presented as a live download.
STATUS_LABELS: dict[str, tuple[str, str]] = {
    "yahoo": ("Historical data loaded", "pos"),
    "cache": ("Cached historical data", "pos"),
    "synthetic": ("Simulated — not market data", "warn"),
}
status_chip = STATUS_LABELS.get(loaded.source, ("Historical data loaded", ""))

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    theme.hero("Finance Stock Analytics", SUBTITLE, theme.status_pill(loaded.source)),
    unsafe_allow_html=True,
)
st.markdown(
    theme.chips(
        [
            ("Banks", " ".join(str(t) for t in close.columns)),
            (
                "Window",
                f"{close.index.min():%d %b %Y} → {close.index.max():%d %b %Y}",
            ),
            ("Sessions", theme.fmt_int(len(close))),
            ("Source", source_label),
            ("Basis", basis_label),
            ("Status", status_chip[0], status_chip[1]),
        ]
    ),
    unsafe_allow_html=True,
)

if is_synthetic:
    st.warning(
        "**Synthetic demo data.** These prices are simulated with a fixed random "
        "seed — they are **not** Yahoo Finance market data and must not be read "
        "as real bank performance."
    )
elif loaded.note:
    st.info(loaded.note)

st.caption(
    "Yahoo Finance treats the end date as *exclusive*, so the last close is the "
    "final trading day **before** the selected end date."
    if not is_synthetic
    else "Simulated business-day calendar: the end date is inclusive."
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_prices, tab_risk, tab_corr, tab_port = st.tabs(
    ["Prices", "Risk", "Correlations", "Portfolio"]
)


# ===========================================================================
# Prices
# ===========================================================================
with tab_prices:
    section(
        "Performance overview",
        f"Total return over the selected window, with annualized volatility and "
        f"Sharpe ratio for each bank ({basis_label.lower()} prices).",
    )
    st.markdown(
        theme.kpi_grid(
            [
                theme.KpiCard(
                    label=str(ticker),
                    value=theme.fmt_pct(row["Growth of $1"] - 1, 1, signed=True),
                    sub=(
                        f"vol {theme.fmt_pct(row['Ann. Volatility'])} · "
                        f"Sharpe {theme.fmt_ratio(row['Sharpe'])}"
                    ),
                    tone=theme.tone_of(row["Growth of $1"] - 1),
                    swatch=theme.ticker_color(str(ticker)),
                    tooltip=(
                        f"{config.BANK_NAMES.get(str(ticker), ticker)} — "
                        "total return over the selected window"
                    ),
                )
                for ticker, row in summary.iterrows()
            ]
        ),
        unsafe_allow_html=True,
    )

    section(
        (
            "Adjusted closing prices"
            if basis_label == "Adj Close"
            else f"{basis_label} closing prices"
        ),
        "Daily closing levels. Shaded band marks the 2008–09 financial crisis. "
        "Drag to zoom; scroll to pan.",
    )
    log_scale = st.toggle(
        "Logarithmic price axis",
        value=False,
        help=(
            "Useful here: Citigroup traded near $500 in 2007 while JPMorgan "
            "was near $40, so a linear axis flattens the cheaper banks."
        ),
    )
    chart(
        charts.price_history(close, basis_label, log_scale=log_scale),
        alt=(
            "Line chart of adjusted closing prices for "
            f"{', '.join(map(str, close.columns))}."
        ),
    )

    left, right = st.columns(2)
    with left:
        section(
            "Normalized performance",
            "Every bank rebased to 100 at its first available price, so relative "
            "performance is comparable.",
        )
        chart(
            charts.normalized(bundle["normalized"]),
            alt="Rebased index chart starting at 100 for each selected bank.",
        )
    with right:
        section(
            "Growth of $1",
            "Value of $1 invested at the start of the window, dividends "
            "reinvested.",
        )
        chart(
            charts.cumulative(bundle["cumulative"]),
            alt="Growth of one dollar invested in each selected bank.",
        )

    focus = st.selectbox(
        "Focus bank for the charts below",
        list(close.columns),
        format_func=lambda t: f"{t} — {config.BANK_NAMES.get(t, t)}",
        help="Switches the moving-average and daily-return charts.",
    )

    section(
        f"{focus} moving averages",
        f"{short_ma}-day and {long_ma}-day simple moving averages on the price series.",
    )
    chart(
        charts.moving_averages(
            metrics.moving_averages(close[focus], short_ma, long_ma), ticker=focus
        ),
        alt=f"Price of {focus} with {short_ma}-day and {long_ma}-day moving averages.",
    )

    section(
        f"{focus} daily returns",
        "Green bars are up days and rose bars are down days; the line marks zero. "
        "Clusters of large bars show volatility regimes.",
    )
    chart(
        charts.daily_returns(returns, focus),
        alt=f"Bar chart of daily returns for {focus}, coloured by sign.",
    )

    with st.expander("Price data table and download"):
        overview = data.describe_data(close)
        overview.index.name = "Ticker"
        st.dataframe(
            overview.reset_index(),
            hide_index=True,
            width="stretch",
            column_config={
                "start": st.column_config.DateColumn("First date", format="DD MMM YYYY"),
                "end": st.column_config.DateColumn("Last date", format="DD MMM YYYY"),
                "rows": st.column_config.NumberColumn("Sessions", format="%d"),
                "missing": st.column_config.NumberColumn("Missing prices", format="%d"),
                "first_price": st.column_config.NumberColumn("First", format="$%.2f"),
                "last_price": st.column_config.NumberColumn("Last", format="$%.2f"),
            },
        )
        st.download_button(
            "Download price data (CSV)",
            close.to_csv().encode("utf-8"),
            file_name="bank_prices_selected.csv",
            mime="text/csv",
        )


# ===========================================================================
# Risk
# ===========================================================================
SUMMARY_COLUMNS = {
    "Annual return": st.column_config.NumberColumn(
        "Annual return", format="%.1f%%", help="Mean daily return × 252."
    ),
    "Annual volatility": st.column_config.NumberColumn(
        "Annual volatility",
        format="%.1f%%",
        help="Standard deviation of daily returns × √252.",
    ),
    "Sharpe": st.column_config.NumberColumn(
        "Sharpe",
        format="%.2f",
        help="(Annual return − risk-free rate) ÷ annual volatility.",
    ),
    "Sortino": st.column_config.NumberColumn(
        "Sortino",
        format="%.2f",
        help="Excess return per unit of downside deviation (target 0).",
    ),
    "Max drawdown": st.column_config.NumberColumn(
        "Max drawdown",
        format="%.1f%%",
        help="Worst peak-to-trough decline in the window.",
    ),
    "Daily VaR 95%": st.column_config.NumberColumn(
        "Daily VaR 95%",
        format="%.1f%%",
        help=(
            "5% historical quantile of daily returns. Negative values are "
            "losses: on the worst 5% of days the bank lost at least this much."
        ),
    ),
    "Best day": st.column_config.NumberColumn(
        "Best day", format="%.1f%%", help="Largest single-day gain."
    ),
    "Worst day": st.column_config.NumberColumn(
        "Worst day", format="%.1f%%", help="Largest single-day loss."
    ),
    "Growth of $1": st.column_config.NumberColumn(
        "Growth of $1",
        format="$%.2f",
        help="Value at the end of the window of $1 invested at the start.",
    ),
}

with tab_risk:
    var_column = next((c for c in summary.columns if str(c).startswith("VaR")), None)
    top_ticker = str(summary.index[0])
    most_volatile = str(summary["Ann. Volatility"].idxmax())
    deepest = str(summary["Max Drawdown"].idxmin())
    worst_var = str(summary[var_column].idxmin()) if var_column else top_ticker

    section(
        "Risk and return",
        "Headline risk statistics across the selected banks. Hover any column "
        "header in the table for its definition.",
    )
    st.markdown(
        theme.kpi_grid(
            [
                theme.KpiCard(
                    label="Best risk-adjusted",
                    value=top_ticker,
                    sub=(
                        f"{config.BANK_NAMES.get(top_ticker, top_ticker)} · "
                        f"Sharpe {theme.fmt_ratio(summary.loc[top_ticker, 'Sharpe'])}"
                    ),
                    tone="pos",
                    swatch=theme.ticker_color(top_ticker),
                    tooltip="Highest Sharpe ratio in the selected window.",
                ),
                theme.KpiCard(
                    label="Highest volatility",
                    value=theme.fmt_pct(summary.loc[most_volatile, "Ann. Volatility"]),
                    sub=config.BANK_NAMES.get(most_volatile, most_volatile),
                    tone="neg",
                    swatch=theme.ticker_color(most_volatile),
                    tooltip="Largest annualized standard deviation of daily returns.",
                ),
                theme.KpiCard(
                    label="Deepest drawdown",
                    value=theme.fmt_pct(summary.loc[deepest, "Max Drawdown"]),
                    sub=config.BANK_NAMES.get(deepest, deepest),
                    tone="neg",
                    swatch=theme.ticker_color(deepest),
                    tooltip="Largest peak-to-trough decline.",
                ),
                theme.KpiCard(
                    label="Worst daily VaR",
                    value=(
                        theme.fmt_pct(summary.loc[worst_var, var_column])
                        if var_column
                        else "—"
                    ),
                    sub=config.BANK_NAMES.get(worst_var, worst_var),
                    tone="neg",
                    swatch=theme.ticker_color(worst_var),
                    tooltip="5% historical quantile of daily returns.",
                ),
            ]
        ),
        unsafe_allow_html=True,
    )

    table = summary_display(summary)
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config=SUMMARY_COLUMNS,
    )
    st.download_button(
        "Download risk metrics (CSV)",
        summary.to_csv().encode("utf-8"),
        file_name="risk_summary.csv",
        mime="text/csv",
        help="Full-precision metrics (decimals, not percentages).",
    )

    left, right = st.columns(2)
    with left:
        section(
            "Risk versus return",
            "Bubble size grows with the Sharpe ratio. Points above the dotted "
            "line beat the risk-free rate.",
        )
        chart(
            charts.risk_return(summary, risk_free),
            alt="Scatter chart of annual volatility against annual return for each bank.",
        )
    with right:
        section(
            "Drawdown from peak",
            "Distance below each bank's previous high. Deeper and longer "
            "underwater periods mean slower recovery.",
        )
        chart(
            charts.drawdown(bundle["drawdown"]),
            alt="Underwater chart showing each bank's drawdown from its running peak.",
        )

    if len(returns) < vol_window:
        section(f"{vol_window}-day rolling volatility")
        empty_state(
            f"Only {len(returns)} return observations are available, which is not "
            f"enough for a {vol_window}-day rolling window. Widen the date range "
            "or lower the window in the sidebar."
        )
    else:
        section(
            f"{vol_window}-day rolling volatility (annualized)",
            "Volatility regimes over time — the 2008–09 spike dominates the sample.",
        )
        chart(
            charts.rolling_volatility(
                metrics.rolling_volatility(returns, vol_window), vol_window
            ),
            alt=f"Annualized {vol_window}-day rolling volatility for each bank.",
        )

    left, right = st.columns([1.1, 1])
    with left:
        section(
            "Daily return distributions",
            "Boxes show median and interquartile range; whiskers extend to the "
            "typical extremes. Long whiskers indicate fat tails.",
        )
        chart(
            charts.return_boxes(returns),
            alt="Box plot of daily return distributions for each bank.",
        )
    with right:
        section("Best and worst days")
        extremes = bundle["extremes"]
        extremes_display = pd.DataFrame(
            {
                "Ticker": [str(t) for t in extremes.index],
                "Best day": extremes["best_day_return"] * 100,
                "Best date": extremes["best_day_date"].dt.strftime("%d %b %Y"),
                "Worst day": extremes["worst_day_return"] * 100,
                "Worst date": extremes["worst_day_date"].dt.strftime("%d %b %Y"),
            }
        )
        st.dataframe(
            extremes_display,
            hide_index=True,
            width="stretch",
            column_config={
                "Best day": st.column_config.NumberColumn("Best day", format="%.1f%%"),
                "Worst day": st.column_config.NumberColumn(
                    "Worst day", format="%.1f%%"
                ),
            },
        )

    with st.expander("How these metrics are calculated"):
        st.markdown(
            "- **Daily return** — `P(t) / P(t−1) − 1` on dividend-adjusted closes "
            "(first row dropped).\n"
            "- **Annual return** — mean daily return × 252 (arithmetic, not CAGR).\n"
            "- **Annual volatility** — standard deviation of daily returns × √252.\n"
            "- **Sharpe** — `(annual return − risk-free rate) / annual volatility`.\n"
            "- **Sortino** — same numerator, divided by the target downside "
            "deviation: `sqrt(mean(min(r − rf, 0)²)) × √252` over all days.\n"
            "- **Max drawdown** — `min(wealth / running peak − 1)`.\n"
            "- **Daily VaR 95%** — the 5th percentile of daily returns, shown as a "
            "signed return (negative = loss). It is not a positive loss amount.\n"
            "- **Rolling volatility** — the same √252 annualization over a moving "
            "window, so early peaks compare regimes rather than totals."
        )


# ===========================================================================
# Correlations
# ===========================================================================
with tab_corr:
    section(
        "Correlation of daily returns",
        "Pearson correlation over the selected window, on a fixed −1…+1 scale. "
        "Diversification benefits fade as values approach +1.",
    )

    if len(returns) < 2 or len(returns.columns) < 2:
        empty_state(
            "Correlation analysis needs at least two banks and a couple of daily "
            "returns. Select another bank in the sidebar."
        )
    else:
        pairs = [
            (str(a), str(b), float(correlation.loc[a, b]))
            for i, a in enumerate(correlation.columns)
            for b in correlation.columns[i + 1 :]
        ]
        strongest = max(pairs, key=lambda item: item[2])
        weakest = min(pairs, key=lambda item: item[2])
        average = sum(item[2] for item in pairs) / len(pairs)

        st.markdown(
            theme.kpi_grid(
                [
                    theme.KpiCard(
                        label="Average pairwise corr.",
                        value=theme.fmt_ratio(average),
                        sub=f"{len(pairs)} bank pairs",
                        tone="acc",
                        tooltip="Mean Pearson correlation across all bank pairs.",
                    ),
                    theme.KpiCard(
                        label="Strongest pair",
                        value=f"{strongest[0]}–{strongest[1]}",
                        sub=f"ρ = {theme.fmt_ratio(strongest[2])}",
                        swatch=theme.ticker_color(strongest[0]),
                        tooltip="Highest positive non-diagonal correlation.",
                    ),
                    theme.KpiCard(
                        label="Weakest pair",
                        value=f"{weakest[0]}–{weakest[1]}",
                        sub=f"ρ = {theme.fmt_ratio(weakest[2])}",
                        swatch=theme.ticker_color(weakest[0]),
                        tooltip="Lowest correlation in the matrix.",
                    ),
                ]
            ),
            unsafe_allow_html=True,
        )

        st.markdown(theme.correlation_scale(), unsafe_allow_html=True)
        chart(
            charts.correlation_heatmap(correlation),
            alt="Heatmap of pairwise correlation between the selected banks.",
        )

        left, right = st.columns([1.15, 1])
        with left:
            section("Correlation matrix")
            matrix = correlation.copy()
            matrix.index = [str(t) for t in matrix.index]
            matrix.columns = [str(c) for c in matrix.columns]
            st.dataframe(
                matrix.round(2),
                width="stretch",
                column_config={
                    str(c): st.column_config.NumberColumn(str(c), format="%.2f")
                    for c in matrix.columns
                },
            )
            st.download_button(
                "Download correlations (CSV)",
                correlation.to_csv().encode("utf-8"),
                file_name="correlations.csv",
                mime="text/csv",
            )
        with right:
            section("What this means")
            st.markdown(
                f"- **{strongest[0]} and {strongest[1]}** moved most closely "
                f"together (ρ = {strongest[2]:.2f}).\n"
                f"- **{weakest[0]} and {weakest[1]}** were the least correlated "
                f"pair (ρ = {weakest[2]:.2f}).\n"
                f"- The average pairwise correlation is {average:.2f}, so these "
                "banks largely shared the same market and regulatory shocks.\n\n"
                "Correlation measures co-movement of daily returns within this "
                "sample only. It does **not** imply causation, and it is unstable "
                "over time — relationships strengthen in crises, exactly when "
                "diversification matters most."
            )


# ===========================================================================
# Portfolio
# ===========================================================================
with tab_port:
    section(
        "Monte Carlo portfolio simulation — risk vs. return",
        "Random long-only weights simulated over the selected history. Each dot "
        "is one hypothetical mix; colour shows its Sharpe ratio.",
    )

    port_returns = returns.dropna()
    if port_returns.shape[1] < 2 or len(port_returns) < 2:
        empty_state(
            "Portfolio simulation needs at least two banks with overlapping "
            "returns. Add another bank to the selection."
        )
    else:
        n_port = st.slider(
            "Portfolios to simulate",
            500,
            20_000,
            config.N_MONTE_CARLO_PORTFOLIOS,
            step=500,
            help="More simulations trace the cloud more densely but take longer.",
        )

        try:
            simulations, best = simulate(
                port_returns, n_port, risk_free, config.RANDOM_SEED
            )
        except Exception as exc:  # noqa: BLE001 - never crash the page
            st.error("The portfolio simulation could not be computed.")
            with st.expander("Diagnostics"):
                st.code(f"{type(exc).__name__}: {exc}")
        else:
            assets = pd.DataFrame(
                {
                    "return": summary["Ann. Return"].reindex(port_returns.columns),
                    "volatility": summary["Ann. Volatility"].reindex(
                        port_returns.columns
                    ),
                }
            ).dropna()
            chart(
                charts.portfolio_cloud(
                    simulations,
                    max_sharpe=(best.max_sharpe_vol, best.max_sharpe_return),
                    min_vol=(best.min_vol_vol, best.min_vol_return),
                    assets=assets,
                ),
                alt=(
                    "Scatter of simulated portfolio volatility against expected "
                    "return, with maximum-Sharpe and minimum-volatility points "
                    "highlighted."
                ),
            )
            st.caption(
                f"{n_port:,} random long-only portfolios · seed {config.RANDOM_SEED} "
                "· weights always sum to 100%. Illustrative only — not an "
                "investment recommendation."
            )

            left, right = st.columns(2)
            for column, title, description, weights, ret, vol, ratio in (
                (
                    left,
                    "Maximum-Sharpe allocation",
                    "Best return per unit of volatility among the sampled mixes.",
                    best.max_sharpe_weights,
                    best.max_sharpe_return,
                    best.max_sharpe_vol,
                    best.max_sharpe_ratio,
                ),
                (
                    right,
                    "Minimum-volatility allocation",
                    "Lowest portfolio volatility among the sampled mixes.",
                    best.min_vol_weights,
                    best.min_vol_return,
                    best.min_vol_vol,
                    best.min_vol_ratio,
                ),
            ):
                with column:
                    section(title, description)
                    st.markdown(
                        theme.kpi_grid(
                            [
                                theme.KpiCard(
                                    label="Expected return",
                                    value=theme.fmt_pct(ret, 1, signed=True),
                                    tone=theme.tone_of(ret),
                                    tooltip="Annualized mean return of this mix.",
                                ),
                                theme.KpiCard(
                                    label="Volatility",
                                    value=theme.fmt_pct(vol),
                                    tone="neutral",
                                    tooltip="Annualized standard deviation of this mix.",
                                ),
                                theme.KpiCard(
                                    label="Sharpe",
                                    value=theme.fmt_ratio(ratio),
                                    tone="acc",
                                    tooltip="(Return − risk-free) ÷ volatility.",
                                ),
                            ]
                        ),
                        unsafe_allow_html=True,
                    )
                    chart(
                        charts.weights_bar(weights),
                        alt=f"{title} weights by bank.",
                    )

            section(
                "Allocation comparison",
                "Both allocations normalised to 100%. Weights are whole-portfolio "
                "shares, so they can be read directly as percentages.",
            )
            allocations = pd.DataFrame(
                {
                    "Ticker": [str(t) for t in best.max_sharpe_weights.index],
                    "Bank": [
                        config.BANK_NAMES.get(str(t), str(t))
                        for t in best.max_sharpe_weights.index
                    ],
                    "Max-Sharpe weight": best.max_sharpe_weights.values * 100,
                    "Min-volatility weight": best.min_vol_weights.values * 100,
                }
            )
            st.dataframe(
                allocations,
                hide_index=True,
                width="stretch",
                column_config={
                    "Max-Sharpe weight": st.column_config.NumberColumn(
                        "Max-Sharpe weight", format="%.1f%%"
                    ),
                    "Min-volatility weight": st.column_config.NumberColumn(
                        "Min-volatility weight", format="%.1f%%"
                    ),
                },
            )
            st.caption(
                f"Max-Sharpe total {best.max_sharpe_weights.sum():.2%} · "
                f"min-volatility total {best.min_vol_weights.sum():.2%}"
            )
            st.download_button(
                "Download allocations (CSV)",
                allocations.to_csv(index=False).encode("utf-8"),
                file_name="portfolio_allocations.csv",
                mime="text/csv",
            )

            with st.expander("How to read this simulation"):
                st.markdown(
                    "- Weights are drawn uniformly at random and normalised so each "
                    "portfolio sums to 100%; **no short selling** is allowed.\n"
                    "- Expected return is `weights · mean daily return × 252`; "
                    "volatility is `√(wᵀΣw) × √252` using the covariance of the "
                    "same daily returns.\n"
                    "- Because thousands of random mixes are sampled, the cloud "
                    "*approximates* the achievable region. It is **not** a solved "
                    "efficient frontier and the stars are not optimal portfolios in "
                    "a mathematical sense.\n"
                    "- Weights use full-sample means and covariances, so the result "
                    "is descriptive and contains look-ahead information. It is not "
                    "a backtest and not a recommendation."
                )
