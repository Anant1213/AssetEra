"""
Portfolio Builder — Create and backtest custom portfolios.
"""

from __future__ import annotations
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.ui import (
    apply_styles, page_header, section_header, kpi_row, ticker_tape, disclaimer, CHART_LAYOUT
)
from backend.market import fetch_prices, compute_metrics, ALLOWLIST
from backend.backtest_engine import (
    fetch_portfolio_prices, renorm_weights, portfolio_equity_curve,
    benchmark_equity_curve, compute_enhanced_metrics
)
from backend.portfolio_store import (
    create_portfolio, list_portfolios, get_portfolio, delete_portfolio
)
from backend.indicators import drawdown_series

st.set_page_config(page_title="Portfolio Builder — AssetEra", page_icon="🎯", layout="wide")
apply_styles()

# ── Benchmarks ────────────────────────────────────────────────────────
BENCHMARKS = {
    "SPY": {"name": "S&P 500 (SPY)", "def": {"type": "single", "ticker": "SPY"}},
    "GLD": {"name": "Gold (GLD)", "def": {"type": "single", "ticker": "GLD"}},
    "IEF": {"name": "UST 7-10y (IEF)", "def": {"type": "single", "ticker": "IEF"}},
    "AGG": {"name": "Aggregate Bond (AGG)", "def": {"type": "single", "ticker": "AGG"}},
    "60/40": {"name": "60/40 (SPY/IEF)", "def": {"type": "mix", "weights": {"SPY": 0.6, "IEF": 0.4}}},
    "80/20": {"name": "80/20 (SPY/IEF)", "def": {"type": "mix", "weights": {"SPY": 0.8, "IEF": 0.2}}},
}

# ── Session state ─────────────────────────────────────────────────────
if "pb_holdings" not in st.session_state:
    st.session_state.pb_holdings = []
if "pb_name" not in st.session_state:
    st.session_state.pb_name = "My Portfolio"
if "pb_description" not in st.session_state:
    st.session_state.pb_description = ""

# ── Ticker tape ───────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _tape():
    p, _ = fetch_prices(sorted(list(ALLOWLIST)[:10]), period="5d", interval="1d")
    return compute_metrics(p)

ticker_tape(_tape())

page_header("Portfolio Builder", "Design and backtest custom asset allocations", badge="INTERACTIVE")

# ── Tabs ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Build", "📈 Backtest", "💾 My Portfolios"])

# ══════════════════════════════════════════════════════════════════════
# TAB 1: BUILD PORTFOLIO
# ══════════════════════════════════════════════════════════════════════

with tab1:
    section_header("Portfolio Details")

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.pb_name = st.text_input(
            "Portfolio Name",
            value=st.session_state.pb_name,
            placeholder="e.g., Tech Growth 2024"
        )
    with c2:
        st.session_state.pb_description = st.text_input(
            "Description (optional)",
            value=st.session_state.pb_description,
            placeholder="e.g., Growth-focused portfolio with 70% equities"
        )

    section_header("Add Holdings")

    # Ticker search and add
    search_col, add_col = st.columns([3, 1])
    with search_col:
        new_ticker = st.selectbox(
            "Search tickers",
            options=sorted(list(ALLOWLIST)),
            placeholder="Type a ticker (e.g., AAPL, SPY)…",
            label_visibility="collapsed",
        )
    with add_col:
        if st.button("Add", key="add_holding", use_container_width=True):
            if new_ticker and new_ticker.upper() not in [h["ticker"] for h in st.session_state.pb_holdings]:
                st.session_state.pb_holdings.append({
                    "ticker": new_ticker.upper(),
                    "weight": 0.0,
                })
                st.rerun()

    # Holdings list with weight controls
    if st.session_state.pb_holdings:
        section_header("Current Holdings")

        total_weight = 0.0
        new_holdings = []

        for i, holding in enumerate(st.session_state.pb_holdings):
            col1, col2, col3, col4 = st.columns([1, 2, 1.5, 0.8])

            ticker = holding["ticker"]
            weight = holding["weight"]

            with col1:
                st.write(f"**{ticker}**")
            with col2:
                weight = st.slider(
                    f"Weight {ticker}",
                    min_value=0.0,
                    max_value=100.0,
                    value=weight,
                    step=0.5,
                    label_visibility="collapsed",
                )
            with col3:
                st.write(f"{weight:.1f}%")
            with col4:
                if st.button("✕", key=f"del_{i}", use_container_width=True):
                    continue

            total_weight += weight
            new_holdings.append({"ticker": ticker, "weight": weight})

        st.session_state.pb_holdings = new_holdings

        # Weight feedback
        st.markdown(
            f"""
            <div style="
              background:var(--bg-card);border:1px solid var(--border);
              border-radius:10px;padding:10px 12px;font-size:.85rem;
              color:var(--text-2);margin:12px 0;">
              <strong style="color:var(--text);">Total allocation:</strong>
              <span style="color:{'var(--green)' if abs(total_weight - 100) < 0.1 else 'var(--yellow)'};
                font-family:var(--mono);font-weight:700;">{total_weight:.1f}%</span>
              <span style="color:var(--text-3);">
              {'✓ Ready' if abs(total_weight - 100) < 0.1 else f'({100 - total_weight:+.1f}% to adjust)'}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Allocation pie chart
        if st.session_state.pb_holdings:
            holdings_for_chart = [h for h in st.session_state.pb_holdings if h["weight"] > 0]
            if holdings_for_chart:
                fig_pie = go.Figure(data=[
                    go.Pie(
                        labels=[h["ticker"] for h in holdings_for_chart],
                        values=[h["weight"] for h in holdings_for_chart],
                        marker=dict(colors=["#2962FF", "#00C896", "#FFB020", "#FF3560", "#A78BFA"] * 10),
                    )
                ])
                fig_pie.update_layout(
                    height=300,
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="var(--text)", family="Inter, sans-serif"),
                    margin=dict(l=20, r=20, t=20, b=20),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        # Action buttons
        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            if st.button("Auto-Balance", use_container_width=True, help="Equal weight all holdings"):
                if st.session_state.pb_holdings:
                    equal_weight = 100.0 / len(st.session_state.pb_holdings)
                    for h in st.session_state.pb_holdings:
                        h["weight"] = equal_weight
                    st.rerun()

        with col_b:
            if st.button("Save Portfolio", use_container_width=True, type="primary"):
                if st.session_state.pb_holdings and abs(total_weight - 100) < 0.1:
                    portfolio_id = create_portfolio(
                        st.session_state.pb_name,
                        st.session_state.pb_description,
                        st.session_state.pb_holdings,
                    )
                    if portfolio_id:
                        st.success(f"✓ Portfolio saved (ID: {portfolio_id})")
                    else:
                        st.warning("Could not save (Postgres not available)")
                else:
                    st.error("Adjust weights to total 100%")

    else:
        st.info("Add tickers above to get started.")

# ══════════════════════════════════════════════════════════════════════
# TAB 2: BACKTEST
# ══════════════════════════════════════════════════════════════════════

with tab2:
    if not st.session_state.pb_holdings:
        st.warning("Create a portfolio in the **Build** tab first.")
    else:
        section_header("Backtest Settings")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**Period**")
            today = date.today()
            default_start = today - timedelta(days=365 * 2)
            start_date = st.date_input("Start Date", value=default_start, max_value=today)
            end_date = st.date_input("End Date", value=today, max_value=today)

        with c2:
            st.markdown("**Investment & Fees**")
            start_amount = st.number_input("Initial Investment ($)", value=100000.0, step=10000.0)
            fee_bps = st.number_input("Annual Fee (bps)", value=20, step=5, min_value=0, max_value=100)
            fee = fee_bps / 10000.0

        with c3:
            st.markdown("**Options**")
            rebalance = st.selectbox("Rebalance", ["Annual", "Quarterly", "Monthly", "None"])
            rf_rate = st.number_input("Risk-free Rate (%)", value=4.0, step=0.1) / 100.0
            bench_sel = st.multiselect("Benchmarks", list(BENCHMARKS.keys()), default=["SPY"])

        # Run button
        if st.button("▶ Run Backtest", type="primary", use_container_width=True):
            with st.spinner("Fetching prices and computing metrics…"):
                # Build target weights from holdings
                target_w = {h["ticker"]: h["weight"] / 100.0 for h in st.session_state.pb_holdings}
                fund_tickers = set(target_w.keys())

                # Collect benchmark tickers
                bench_tickers = set()
                for b in bench_sel:
                    defn = BENCHMARKS[b]["def"]
                    if defn["type"] == "single":
                        bench_tickers.add(defn["ticker"])
                    else:
                        bench_tickers.update(defn["weights"].keys())

                needed = sorted(fund_tickers | bench_tickers)

                # Fetch prices
                prices = fetch_portfolio_prices(tuple(needed), start_date, end_date)
                if prices.empty:
                    st.error("No data available for this period.")
                    st.stop()

                # Check available tickers
                present = [t for t in fund_tickers if t in prices.columns]
                missing = sorted(fund_tickers - set(present))
                if missing:
                    st.warning(f"No data for: {', '.join(missing)} (weights renormalized)")

                weights = renorm_weights(target_w, present)
                if not weights:
                    st.error("No portfolio tickers have data.")
                    st.stop()

                # Compute returns
                rets_all = prices.pct_change(fill_method=None)
                r_port = rets_all[present].dropna(how="any")

                if r_port.empty or len(r_port) < 2:
                    st.error("Insufficient overlapping data.")
                    st.stop()

                # Run simulation
                eq = portfolio_equity_curve(r_port, weights, rebalance=rebalance, fee=fee)
                if eq.empty:
                    st.error("Empty equity series.")
                    st.stop()

                eq = eq / eq.iloc[0]
                d0, d1 = eq.index[0].date(), eq.index[-1].date()

                # Compute metrics vs primary benchmark
                primary_bench = benchmark_equity_curve(rets_all, BENCHMARKS[bench_sel[0]]["def"])

                metrics = compute_enhanced_metrics(eq, primary_bench, start_amount, d0, d1, rf=rf_rate)

                # Store in session for charts
                st.session_state.pb_backtest_result = {
                    "eq": eq,
                    "rets_all": rets_all,
                    "metrics": metrics,
                    "d0": d0,
                    "d1": d1,
                    "weights": weights,
                    "start_amount": start_amount,
                    "rf_rate": rf_rate,
                    "bench_sel": bench_sel,
                }

        # Display results if available
        if "pb_backtest_result" in st.session_state:
            result = st.session_state.pb_backtest_result
            eq = result["eq"]
            rets_all = result["rets_all"]
            metrics = result["metrics"]
            d0 = result["d0"]
            d1 = result["d1"]
            bench_sel = result["bench_sel"]

            # KPI strip
            section_header("Performance Summary")
            kpi_row([
                {"label": "Final Value", "value": f"${metrics.get('fv', 0):,.0f}", "delta": None},
                {
                    "label": "Total Return",
                    "value": f"{metrics.get('ret', 0)*100:.2f}%",
                    "delta": None,
                    "delta_dir": "up" if (metrics.get("ret", 0) or 0) >= 0 else "dn",
                },
                {"label": "CAGR", "value": f"{metrics.get('cagr', 0)*100:.2f}%", "delta": None},
                {"label": "Volatility", "value": f"{metrics.get('vol', 0)*100:.2f}%", "delta": None},
                {
                    "label": "Sharpe",
                    "value": f"{metrics.get('sharpe', 0):.2f}",
                    "delta": None,
                },
                {
                    "label": "Max Drawdown",
                    "value": f"{metrics.get('mdd', 0)*100:.1f}%",
                    "delta": None,
                    "delta_dir": "dn",
                },
            ])

            # Equity curve
            section_header("Equity Curve")
            df_plot = pd.DataFrame({"Portfolio": eq})

            for b in bench_sel:
                defn = BENCHMARKS[b]["def"]
                bs = benchmark_equity_curve(rets_all, defn)
                if not bs.empty:
                    bs = bs.reindex(eq.index).ffill().dropna()
                    if not bs.empty:
                        bs = bs / bs.iloc[0]
                        df_plot[BENCHMARKS[b]["name"]] = bs

            fig_eq = go.Figure()
            palette = ["#2962FF", "#00C896", "#FFB020", "#FF3560", "#A78BFA"]
            for i, col in enumerate(df_plot.columns):
                fig_eq.add_trace(
                    go.Scatter(
                        x=df_plot.index,
                        y=df_plot[col],
                        mode="lines",
                        name=col,
                        line=dict(
                            color=palette[i % len(palette)],
                            width=3 if col == "Portfolio" else 1.5,
                            dash="solid" if col == "Portfolio" else "dot",
                        ),
                    )
                )
            layout = dict(**CHART_LAYOUT)
            layout.update(height=420, margin=dict(l=55, r=20, t=30, b=40))
            fig_eq.update_layout(**layout)
            fig_eq.update_yaxes(title_text="Growth (×1 at start)")
            st.plotly_chart(fig_eq, use_container_width=True)

            # Drawdown
            section_header("Drawdown")
            dd = drawdown_series(eq) * 100
            fig_dd = go.Figure(
                go.Scatter(
                    x=dd.index,
                    y=dd,
                    fill="tozeroy",
                    fillcolor="rgba(255,53,96,.12)",
                    line=dict(color="#FF3560", width=1.5),
                    name="Drawdown",
                )
            )
            layout = dict(**CHART_LAYOUT)
            layout.update(height=220, margin=dict(l=55, r=20, t=20, b=40))
            fig_dd.update_layout(**layout)
            fig_dd.update_yaxes(title_text="Drawdown (%)")
            st.plotly_chart(fig_dd, use_container_width=True)

            # Metrics table
            section_header("Detailed Metrics")
            metrics_df = pd.DataFrame({
                "Metric": [
                    "Final Value",
                    "Total Return %",
                    "CAGR %",
                    "Volatility (ann.) %",
                    "Sharpe Ratio",
                    "Sortino Ratio",
                    "Calmar Ratio",
                    "Max Drawdown %",
                    "Beta",
                    "Alpha %",
                    "VaR 95% (monthly) %",
                    "CVaR 95% %",
                    "% Positive Months",
                ],
                "Value": [
                    f"${metrics.get('fv', 0):,.0f}",
                    f"{metrics.get('ret', 0)*100:.2f}",
                    f"{metrics.get('cagr', 0)*100:.2f}",
                    f"{metrics.get('vol', 0)*100:.2f}",
                    f"{metrics.get('sharpe', 0):.2f}",
                    f"{metrics.get('sortino', 0):.2f}",
                    f"{metrics.get('calmar', 0):.2f}",
                    f"{metrics.get('mdd', 0)*100:.1f}",
                    f"{metrics.get('beta', 0):.2f}",
                    f"{metrics.get('alpha', 0)*100:.2f}",
                    f"{metrics.get('var95', 0)*100:.2f}",
                    f"{metrics.get('cvar95', 0)*100:.2f}",
                    f"{metrics.get('pct_pos', 0)*100:.1f}",
                ],
            })
            st.dataframe(metrics_df, use_container_width=True, hide_index=True)

            # Download
            section_header("Export")
            out = pd.DataFrame({"equity": eq})
            out.index.name = "date"
            st.download_button(
                "Download Equity Curve (CSV)",
                out.to_csv().encode(),
                f"portfolio_{d0}_{d1}.csv",
                "text/csv",
            )

# ══════════════════════════════════════════════════════════════════════
# TAB 3: MY PORTFOLIOS
# ══════════════════════════════════════════════════════════════════════

with tab3:
    section_header("Saved Portfolios")

    portfolios = list_portfolios()

    if not portfolios:
        st.info("You haven't saved any portfolios yet. Build one in the **Build** tab!")
    else:
        for p in portfolios:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.write(f"**{p['name']}**")
                if p["description"]:
                    st.caption(p["description"])
                holdings = p.get("holdings", [])
                if isinstance(holdings, str):
                    holdings = __import__("json").loads(holdings)
                st.caption(
                    f"{len(holdings)} holdings · "
                    f"Created {pd.Timestamp(p['created_at']).strftime('%Y-%m-%d')}"
                )

            with col2:
                if st.button("Load", key=f"load_{p['id']}", use_container_width=True):
                    st.session_state.pb_name = p["name"]
                    st.session_state.pb_description = p.get("description", "")
                    st.session_state.pb_holdings = p.get("holdings", [])
                    if isinstance(st.session_state.pb_holdings, str):
                        st.session_state.pb_holdings = __import__("json").loads(
                            st.session_state.pb_holdings
                        )
                    st.success("Loaded into Build tab!")
                    st.switch_page("pages/3_Portfolio_Builder.py")

            with col3:
                if st.button("Backtest", key=f"test_{p['id']}", use_container_width=True):
                    st.session_state.pb_name = p["name"]
                    st.session_state.pb_holdings = p.get("holdings", [])
                    if isinstance(st.session_state.pb_holdings, str):
                        st.session_state.pb_holdings = __import__("json").loads(
                            st.session_state.pb_holdings
                        )
                    st.switch_page("pages/3_Portfolio_Builder.py")

            with col4:
                if st.button("Delete", key=f"del_{p['id']}", use_container_width=True):
                    if delete_portfolio(p["id"]):
                        st.success("Deleted")
                        st.rerun()

disclaimer("Backtesting results assume zero slippage and no transaction costs.")
