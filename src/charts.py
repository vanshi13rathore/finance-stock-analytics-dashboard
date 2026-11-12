"""Interactive Plotly charts for the dashboard.

Every chart is a pure function of pandas objects: no Streamlit imports, no
I/O, no financial maths (metrics arrive pre-computed from ``src.metrics`` and
``src.portfolio``). Colours, fonts and axis styling all come from
:mod:`src.theme`, so the four tabs look like one product.

The matplotlib versions in ``src.plots`` remain the source of truth for the
notebook/CLI PNG output and are untouched by this module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
CRISIS_START = pd.Timestamp("2008-01-01")
CRISIS_END = pd.Timestamp("2009-12-31")


def _finish(
    fig: go.Figure,
    height: int,
    *,
    hovermode: str = "x unified",
    showlegend: bool = True,
    margin_right: int = 16,
) -> go.Figure:
    """Apply the shared template, size and legend rules."""
    fig.update_layout(
        template=theme.register_plotly_template(),
        height=height,
        hovermode=hovermode,
        showlegend=showlegend,
        margin=dict(l=10, r=margin_right, t=38 if showlegend else 22, b=10),
    )
    return fig


def _crisis_band(fig: go.Figure, index) -> None:
    """Shade the 2008–09 crisis window when it falls inside the data."""
    if index is None or len(index) == 0:
        return
    lo, hi = pd.Timestamp(index.min()), pd.Timestamp(index.max())
    if hi < CRISIS_START or lo > CRISIS_END:
        return
    x0, x1 = max(CRISIS_START, lo), min(CRISIS_END, hi)
    fig.add_vrect(
        x0=x0,
        x1=x1,
        fillcolor=theme.ACCENT,
        opacity=0.07,
        layer="below",
        line_width=0,
    )
    fig.add_annotation(
        x=x0,
        y=1,
        xref="x",
        yref="paper",
        yanchor="top",
        xanchor="left",
        text=" 2008–09 crisis ",
        showarrow=False,
        font=dict(size=9, color=theme.FAINT),
    )


def _series(fig: go.Figure, frame: pd.DataFrame, **extra_line) -> None:
    """Add one line per column, coloured by ticker identity."""
    for ticker in frame.columns:
        series = frame[ticker].dropna()
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=str(ticker),
                line=dict(color=theme.ticker_color(str(ticker)), width=1.7, **extra_line),
                hovertemplate="%{y}<extra>" + str(ticker) + "</extra>",
            )
        )


def _time_axes(fig: go.Figure) -> None:
    fig.update_xaxes(tickformat="%b %Y", nticks=8, showgrid=False)


# ---------------------------------------------------------------------------
# Prices tab
# ---------------------------------------------------------------------------
def price_history(
    close: pd.DataFrame, basis: str = "Adj Close", log_scale: bool = False
) -> go.Figure:
    """Adjusted closing levels for every selected bank.

    ``log_scale`` keeps banks at very different price levels (Citigroup near
    $500 vs JPMorgan near $40 in 2007) readable on the same axis.
    """
    fig = go.Figure()
    for ticker in close.columns:
        series = close[ticker].dropna()
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=str(ticker),
                line=dict(color=theme.ticker_color(str(ticker)), width=1.7),
                hovertemplate="%{y:$,.2f}<extra>" + str(ticker) + "</extra>",
            )
        )
    _crisis_band(fig, close.index)
    fig.update_yaxes(
        tickprefix="$",
        tickformat=",.0f",
        title_text="Price (USD, log scale)" if log_scale else "Price (USD)",
        type="log" if log_scale else "linear",
    )
    _time_axes(fig)
    return _finish(fig, 430)


def normalized(normalized_prices: pd.DataFrame, base: float = 100.0) -> go.Figure:
    """Rebased performance: every bank starts at the same value."""
    fig = go.Figure()
    _series(fig, normalized_prices)
    for trace in fig.data:
        trace.hovertemplate = "%{y:.1f}<extra>" + trace.name + "</extra>"
    fig.add_hline(
        y=base,
        line=dict(color=theme.GRID, width=1, dash="dot"),
        annotation_text=f"base {base:.0f}",
        annotation_position="bottom right",
        annotation_font=dict(size=9, color=theme.FAINT),
    )
    fig.update_yaxes(tickformat=",.0f", title_text=f"Index ({base:.0f} = start)")
    _time_axes(fig)
    return _finish(fig, 340)


def cumulative(cumulative_returns: pd.DataFrame) -> go.Figure:
    """Growth of $1 invested at the start of the window."""
    fig = go.Figure()
    _series(fig, cumulative_returns)
    for trace in fig.data:
        trace.hovertemplate = "%{y:$,.2f}<extra>" + trace.name + "</extra>"
    fig.add_hline(
        y=1,
        line=dict(color=theme.GRID, width=1, dash="dot"),
        annotation_text="$1.00 invested",
        annotation_position="bottom right",
        annotation_font=dict(size=9, color=theme.FAINT),
    )
    fig.update_yaxes(tickprefix="$", tickformat=".2f", title_text="Value of $1")
    _time_axes(fig)
    return _finish(fig, 340)


def daily_returns(returns: pd.DataFrame, ticker: str) -> go.Figure:
    """Daily return bars for one bank — green up days, rose down days."""
    series = returns[ticker].dropna() if ticker in returns.columns else pd.Series(dtype=float)
    colors = [
        theme.POSITIVE if value >= 0 else theme.NEGATIVE for value in series.values
    ]
    fig = go.Figure(
        go.Bar(
            x=series.index,
            y=series.values,
            marker=dict(color=colors, line_width=0),
            name=ticker,
            hovertemplate="%{y:.2%}<extra>" + str(ticker) + "</extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color=theme.GRID, width=1))
    fig.update_layout(bargap=0.15)
    fig.update_yaxes(tickformat=".1%", title_text="Daily return")
    _time_axes(fig)
    return _finish(fig, 300, showlegend=False)


def moving_averages(ma: pd.DataFrame, ticker: str | None = None) -> go.Figure:
    """Price with short/long simple moving averages for one bank.

    ``ticker`` supplies the colour and legend label; the price column of
    ``metrics.moving_averages`` is called ``"Close"``, which is not a ticker.
    """
    fig = go.Figure()
    columns = list(ma.columns)
    if not columns:
        return _finish(fig, 340, showlegend=False)

    ticker = str(ticker) if ticker else str(columns[0])
    price = ma[columns[0]].dropna()
    fig.add_trace(
        go.Scatter(
            x=price.index,
            y=price.values,
            mode="lines",
            name=ticker,
            line=dict(color=theme.ticker_color(ticker), width=1.8),
            hovertemplate="%{y:$,.2f}<extra>" + ticker + "</extra>",
        )
    )
    shades = (0.32, 0.55)
    dashes = ("dash", "dot")
    for i, column in enumerate(columns[1:]):
        series = ma[column].dropna()
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=str(column),
                line=dict(
                    color=theme.tint(theme.ticker_color(ticker), shades[i % 2]),
                    width=1.4,
                    dash=dashes[i % 2],
                ),
                hovertemplate="%{y:$,.2f}<extra>" + str(column) + "</extra>",
            )
        )
    fig.update_yaxes(tickprefix="$", tickformat=",.0f", title_text="Price (USD)")
    _time_axes(fig)
    return _finish(fig, 340)


# ---------------------------------------------------------------------------
# Risk tab
# ---------------------------------------------------------------------------
def risk_return(summary: pd.DataFrame, risk_free_rate: float = 0.02) -> go.Figure:
    """Risk vs. reward scatter; bubble area grows with the Sharpe ratio."""
    frame = summary.dropna(subset=["Ann. Volatility", "Ann. Return"])
    fig = go.Figure()
    if frame.empty:
        return _finish(fig, 430, hovermode="closest", showlegend=False)

    sharpes = frame["Sharpe"].astype(float)
    finite = sharpes.replace([np.inf, -np.inf], np.nan)
    lo = float(finite.min()) if finite.notna().any() else 0.0
    hi = float(finite.max()) if finite.notna().any() else 1.0
    span = hi - lo if hi > lo else 1.0
    sizes = 13 + 21 * ((sharpes.fillna(lo) - lo) / span)

    fig.add_trace(
        go.Scatter(
            x=frame["Ann. Volatility"],
            y=frame["Ann. Return"],
            mode="markers+text",
            text=[str(t) for t in frame.index],
            textposition="top center",
            textfont=dict(size=11, color=theme.TEXT),
            cliponaxis=False,
            marker=dict(
                size=sizes,
                color=[theme.ticker_color(str(t)) for t in frame.index],
                symbol=[theme.ticker_symbol(str(t)) for t in frame.index],
                line=dict(width=1, color=theme.BG),
                opacity=0.92,
            ),
            customdata=np.stack(
                [
                    frame["Sharpe"].to_numpy(dtype=float),
                    frame["Sortino"].to_numpy(dtype=float),
                    frame["Max Drawdown"].to_numpy(dtype=float),
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Annual return %{y:.1%}<br>"
                "Annual volatility %{x:.1%}<br>"
                "Sharpe %{customdata[0]:.2f}<br>"
                "Sortino %{customdata[1]:.2f}<br>"
                "Max drawdown %{customdata[2]:.1%}"
                "<extra></extra>"
            ),
            name="",
        )
    )
    fig.add_hline(
        y=risk_free_rate,
        line=dict(color=theme.FAINT, width=1, dash="dot"),
        annotation_text=f"risk-free {risk_free_rate:.1%}",
        annotation_position="bottom left",
        annotation_font=dict(size=9, color=theme.FAINT),
    )
    fig.update_xaxes(tickformat=".0%", title_text="Annual volatility")
    fig.update_yaxes(tickformat=".0%", title_text="Annual return")
    return _finish(fig, 430, hovermode="closest", showlegend=False)


def drawdown(drawdown_series: pd.DataFrame) -> go.Figure:
    """Underwater chart: distance below each bank's running peak."""
    fig = go.Figure()
    for ticker in drawdown_series.columns:
        series = drawdown_series[ticker].dropna()
        if series.empty:
            continue
        color = theme.ticker_color(str(ticker))
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=str(ticker),
                line=dict(color=color, width=1.5),
                fill="tozeroy",
                fillcolor=theme.rgba(color, 0.10),
                hovertemplate="%{y:.1%}<extra>" + str(ticker) + "</extra>",
            )
        )
    fig.update_yaxes(tickformat=".0%", title_text="Drawdown from peak")
    _time_axes(fig)
    return _finish(fig, 360)


def rolling_volatility(rolling_vol: pd.DataFrame, window: int = 30) -> go.Figure:
    """Annualized rolling volatility of daily returns."""
    fig = go.Figure()
    _series(fig, rolling_vol)
    for trace in fig.data:
        trace.hovertemplate = "%{y:.1%}<extra>" + trace.name + "</extra>"
    fig.update_yaxes(tickformat=".0%", title_text="Annualized volatility")
    _time_axes(fig)
    return _finish(fig, 340)


def return_boxes(returns: pd.DataFrame) -> go.Figure:
    """Distribution of daily returns per bank (five-number summary)."""
    fig = go.Figure()
    for ticker in returns.columns:
        series = returns[ticker].dropna()
        if series.empty:
            continue
        color = theme.ticker_color(str(ticker))
        fig.add_trace(
            go.Box(
                y=series.values,
                name=str(ticker),
                marker=dict(color=color, size=3),
                line=dict(color=color, width=1.3),
                fillcolor=theme.rgba(color, 0.18),
                boxpoints=False,
                whiskerwidth=0.7,
                hovertemplate="%{y:.2%}<extra>" + str(ticker) + "</extra>",
            )
        )
    fig.update_yaxes(tickformat=".1%", title_text="Daily return")
    fig.update_xaxes(showgrid=False, title_text="")
    return _finish(fig, 340, hovermode="closest", showlegend=False)


# ---------------------------------------------------------------------------
# Correlations tab
# ---------------------------------------------------------------------------
def correlation_heatmap(corr: pd.DataFrame) -> go.Figure:
    """Pearson correlation heatmap on a fixed −1…+1 scale."""
    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=[str(c) for c in corr.columns],
            y=[str(i) for i in corr.index],
            zmin=-1,
            zmax=1,
            zmid=0,
            colorscale=theme.DIVERGING,
            xgap=3,
            ygap=3,
            text=np.round(corr.values, 2),
            texttemplate="%{text:.2f}",
            textfont=dict(size=12, color=theme.TEXT),
            hovertemplate="%{y} · %{x}<br>ρ = %{z:.3f}<extra></extra>",
            # The scale is fixed and every cell prints its value, so the
            # −1…+1 legend lives in the tab's HTML (theme.correlation_scale)
            # instead of a colour bar that can be clipped inside the card.
            showscale=False,
        )
    )
    size = max(320, 70 * len(corr) + 64)
    fig.update_xaxes(showgrid=False, side="bottom", tickfont=dict(size=11, color=theme.TEXT))
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11, color=theme.TEXT))
    return _finish(fig, size, hovermode="closest", showlegend=False)


# ---------------------------------------------------------------------------
# Portfolio tab
# ---------------------------------------------------------------------------
def portfolio_cloud(
    simulations: pd.DataFrame,
    max_sharpe: tuple[float, float] | None = None,
    min_vol: tuple[float, float] | None = None,
    assets: pd.DataFrame | None = None,
) -> go.Figure:
    """Monte Carlo cloud of random long-only portfolios (risk vs. return)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=simulations["volatility"],
            y=simulations["return"],
            mode="markers",
            name="Simulated portfolios",
            marker=dict(
                size=3.4,
                opacity=0.5,
                color=simulations["sharpe"],
                colorscale=[
                    [0.0, "#24304A"],
                    [0.55, "#4E79D8"],
                    [1.0, "#9BB8FF"],
                ],
                showscale=True,
                colorbar=dict(
                    thickness=8,
                    outlinewidth=0,
                    len=0.85,
                    xpad=8,
                    tickfont=dict(size=10, color=theme.MUTED),
                ),
            ),
            customdata=simulations["sharpe"].to_numpy(dtype=float),
            hovertemplate=(
                "Volatility %{x:.1%}<br>Return %{y:.1%}<br>"
                "Sharpe %{customdata:.2f}<extra></extra>"
            ),
        )
    )

    if assets is not None and not assets.empty:
        fig.add_trace(
            go.Scatter(
                x=assets["volatility"],
                y=assets["return"],
                mode="markers+text",
                name="Single banks",
                text=[str(t) for t in assets.index],
                textposition="top center",
                textfont=dict(size=10, color=theme.MUTED),
                cliponaxis=False,
                marker=dict(
                    size=11,
                    symbol=[theme.ticker_symbol(str(t)) for t in assets.index],
                    color=[theme.ticker_color(str(t)) for t in assets.index],
                    line=dict(width=1.2, color=theme.BG),
                ),
                hovertemplate="<b>%{text}</b><br>Vol %{x:.1%}<br>Return %{y:.1%}<extra></extra>",
            )
        )

    for point, label, symbol, color, offset in (
        (max_sharpe, "Max Sharpe", "star", theme.ACCENT, (46, -34)),
        (min_vol, "Min volatility", "diamond", theme.POSITIVE, (-52, -36)),
    ):
        if point is None:
            continue
        vol, ret = point
        fig.add_trace(
            go.Scatter(
                x=[vol],
                y=[ret],
                mode="markers",
                name=label,
                marker=dict(
                    size=17,
                    symbol=symbol,
                    color=color,
                    line=dict(width=1.2, color=theme.BG),
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>Vol %{{x:.1%}}<br>Return %{{y:.1%}}<extra></extra>"
                ),
            )
        )
        # Offset callouts instead of point labels, which collide with the
        # single-bank labels in the dense part of the cloud.
        fig.add_annotation(
            x=vol,
            y=ret,
            ax=offset[0],
            ay=offset[1],
            text=label,
            showarrow=True,
            arrowhead=0,
            arrowwidth=1,
            arrowcolor=theme.rgba(color, 0.7),
            font=dict(size=10, color=color),
            bgcolor=theme.rgba(theme.SURFACE, 0.85),
            borderpad=3,
        )

    fig.update_xaxes(tickformat=".0%", title_text="Annualized volatility")
    fig.update_yaxes(tickformat=".0%", title_text="Expected annual return")
    # generous right margin so the colour-bar tick labels are never clipped
    return _finish(fig, 470, hovermode="closest", margin_right=100)


def weights_bar(weights: pd.Series) -> go.Figure:
    """Horizontal allocation bars, labelled in percent."""
    clean = weights.dropna().sort_values()
    fig = go.Figure(
        go.Bar(
            x=clean.values,
            y=[str(t) for t in clean.index],
            orientation="h",
            marker=dict(
                color=[theme.ticker_color(str(t)) for t in clean.index],
                line_width=0,
            ),
            text=[f"{value:.1%}" for value in clean.values],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(size=11, color=theme.TEXT),
            hovertemplate="%{y}: %{x:.2%}<extra></extra>",
        )
    )
    upper = max(0.05, float(clean.max()) * 1.28) if len(clean) else 1.0
    fig.update_xaxes(tickformat=".0%", range=[0, upper], title_text="Allocation")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11, color=theme.TEXT))
    return _finish(fig, max(210, 42 * len(clean) + 60), hovermode="closest", showlegend=False)
