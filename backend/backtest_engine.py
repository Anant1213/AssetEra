"""
Backtest Engine — Reusable portfolio simulation core.
Extracted from Fund Backtester for use by both Fund Backtester and Portfolio Builder.
"""

from __future__ import annotations
import math
from datetime import date
from typing import Dict

import numpy as np
import pandas as pd
import streamlit as st

from backend.market import fetch_prices

TRADING_DAYS = 252


@st.cache_data(show_spinner=False, ttl=300)
def fetch_portfolio_prices(tickers: tuple, start: date, end: date) -> pd.DataFrame:
    """Load prices from configured market store and pivot to wide format."""
    prices, _ = fetch_prices(list(tickers), period="max", interval="1d")
    if prices.empty:
        return pd.DataFrame()
    # Pivot to wide format: Date × Ticker
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    pivot = pivot[[t for t in tickers if t in pivot.columns]]
    pivot = pivot.sort_index()
    # Trim to requested date range
    pivot = pivot[(pivot.index >= pd.Timestamp(start)) & (pivot.index <= pd.Timestamp(end))]
    return pivot.dropna(how="all").ffill()


def renorm_weights(w: dict, keep: list) -> dict:
    """Re-normalize weights to sum to 1.0 after dropping missing tickers."""
    f = {t: v for t, v in w.items() if t in keep and v > 0}
    s = sum(f.values())
    return {t: v / s for t, v in f.items()} if s > 0 else {}


def portfolio_equity_curve(
    rets: pd.DataFrame,
    weights: dict,
    rebalance: str = "Annual",
    fee: float = 0.0,
) -> pd.Series:
    """
    Simulate portfolio equity curve with daily weight drift, rebalancing, and fee drag.

    Args:
        rets: DataFrame of daily returns (Date × Ticker)
        weights: dict of ticker → allocation (must sum to 1.0)
        rebalance: "Annual", "Quarterly", "Monthly", or "None"
        fee: annual fee as decimal (e.g., 0.002 for 2 bps)

    Returns:
        pd.Series of equity curve starting at 1.0
    """
    tickers = list(weights.keys())
    W = np.array([weights[t] for t in tickers], dtype=float)
    r = rets[tickers].dropna(how="any")
    if r.empty:
        return pd.Series(dtype=float)

    fd = fee / TRADING_DAYS
    idx = r.index
    R = r.values

    w = W.copy()
    eq = np.zeros(len(idx))
    eq[0] = 1.0 * (1 - fd) * (1 + (w * R[0]).sum())

    for i in range(1, len(idx)):
        w = w * (1 + R[i - 1])
        s = w.sum()
        w = w / s if s else W.copy()

        # Rebalance logic
        if rebalance.lower() == "annual" and idx[i - 1].year != idx[i].year:
            w = W.copy()
        elif rebalance.lower() == "quarterly" and idx[i - 1].quarter != idx[i].quarter:
            w = W.copy()
        elif rebalance.lower() == "monthly" and idx[i - 1].month != idx[i].month:
            w = W.copy()

        eq[i] = eq[i - 1] * (1 - fd) * (1 + (w * R[i]).sum())

    return pd.Series(eq, index=idx, name="Portfolio")


def benchmark_equity_curve(rets_all: pd.DataFrame, bench_def: dict) -> pd.Series:
    """
    Compute benchmark equity curve from returns DataFrame.

    Args:
        rets_all: DataFrame of daily returns (Date × Ticker)
        bench_def: {"type": "single"|"mix", "ticker": str} or {"weights": {ticker: float}}

    Returns:
        pd.Series of benchmark equity curve starting at 1.0
    """
    t = bench_def.get("type")
    if t == "single":
        tk = bench_def["ticker"]
        if tk not in rets_all.columns:
            return pd.Series(dtype=float)
        r = rets_all[[tk]].dropna(how="any")
        return (1 + r[tk]).cumprod().rename(tk) if not r.empty else pd.Series(dtype=float)
    elif t == "mix":
        w = bench_def["weights"]
        cols = [c for c in rets_all.columns if c in w]
        if not cols:
            return pd.Series(dtype=float)
        r = rets_all[cols].dropna(how="any")
        if r.empty:
            return pd.Series(dtype=float)
        wv = np.array([w[c] for c in cols])
        wv /= wv.sum()
        return ((1 + r).dot(wv)).cumprod().rename("mix")
    return pd.Series(dtype=float)


def portfolio_kpis(equity: pd.Series, start_value: float, d0: date, d1: date, rf: float = 0.0) -> dict:
    """
    Compute basic KPIs from equity curve.

    Returns dict with: fv, ret, cagr, vol, sharpe
    """
    if equity.empty or len(equity) < 2:
        return None

    daily = equity.pct_change(fill_method=None).dropna()
    yrs = max((d1 - d0).days, 0) / 365.25

    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    cagr = (float(equity.iloc[-1] / equity.iloc[0])) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    vol = float(daily.std() * math.sqrt(TRADING_DAYS)) if len(daily) > 1 else np.nan

    rf_d = rf / TRADING_DAYS
    sharpe = (
        float(((daily.mean() - rf_d) / daily.std()) * math.sqrt(TRADING_DAYS))
        if daily.std() > 0
        else np.nan
    )

    return {
        "fv": start_value * float(equity.iloc[-1]),
        "ret": total,
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
    }


def compute_enhanced_metrics(
    equity: pd.Series,
    bench_equity: pd.Series,
    start_value: float,
    d0: date,
    d1: date,
    rf: float = 0.0,
) -> dict:
    """
    Compute full set of metrics including Sortino, Calmar, VaR, CVaR, Beta, Alpha.

    Returns a dict with all KPIs plus advanced metrics.
    """
    from backend.indicators import (
        max_drawdown,
        sortino_ratio,
        calmar_ratio,
        compute_beta_alpha,
    )

    kpi = portfolio_kpis(equity, start_value, d0, d1, rf)
    if kpi is None:
        return {}

    yrs = max((d1 - d0).days, 0) / 365.25

    # Advanced metrics
    mdd = max_drawdown(equity)
    sortino = sortino_ratio(equity, rf_annual=rf)
    calmar = calmar_ratio(equity, yrs)

    # Monthly returns for VaR/CVaR
    monthly = equity.resample("ME").last().pct_change(fill_method=None).dropna()

    var95 = float(np.percentile(monthly, 5)) if not monthly.empty else np.nan
    cvar95 = (
        float(monthly[monthly <= var95].mean())
        if (monthly <= var95).any()
        else var95
    )

    pct_pos = (monthly > 0).mean() if not monthly.empty else np.nan

    # Beta & Alpha vs benchmark
    beta_val = alpha_val = np.nan
    if not bench_equity.empty:
        bench_eq = bench_equity.reindex(equity.index).ffill().dropna()
        if not bench_eq.empty:
            bench_eq = bench_eq / bench_eq.iloc[0]
            beta_val, alpha_val = compute_beta_alpha(
                equity.pct_change(fill_method=None).dropna(),
                bench_eq.pct_change(fill_method=None).dropna(),
                rf_annual=rf,
            )

    return {
        **kpi,
        "mdd": mdd,
        "sortino": sortino,
        "calmar": calmar,
        "var95": var95,
        "cvar95": cvar95,
        "pct_pos": pct_pos,
        "beta": beta_val,
        "alpha": alpha_val,
    }
