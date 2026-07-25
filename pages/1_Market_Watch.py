"""
Market Watch — Candlestick charts, technical indicators, custom ETF cards.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backend.ui import apply_styles, page_header, section_header, etf_cards, live_ticker_tape, disclaimer, CHART_LAYOUT
from backend.market import (
    ALLOWLIST, PERIODS, INTERVALS, DEFAULT_PERIOD, DEFAULT_INTERVAL,
    fetch_prices, compute_metrics, build_timeseries, corr_matrix,
)
from backend.market_watch.data_catalog import CATALOG, DEFAULT_SELECTION
from backend.indicators import rsi, bollinger_bands, macd

st.set_page_config(page_title="Market Watch — AssetEra", page_icon="📈", layout="wide")
apply_styles()

# ── Ticker tape (shared small cached list — never the full ALLOWLIST) ──
live_ticker_tape()
page_header("Market Watch", "Candlestick charts · Technical indicators · Correlation heatmap", badge="DISK CACHE")

# ── Inline Controls ───────────────────────────────────────────────────

# Build flat ticker list preserving group labels
_all_options: dict[str, str] = {}  # label → ticker
for _grp, _items in CATALOG.items():
    for _lbl, _tkr in _items.items():
        if _tkr in ALLOWLIST:
            _all_options[_lbl] = _tkr

_default_labels = [lbl for lbl, tkr in _all_options.items() if tkr in DEFAULT_SELECTION]

st.markdown(
    "<div style='background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--r-lg);padding:1rem 1.2rem;margin-bottom:1rem;'>",
    unsafe_allow_html=True,
)

row1_c1, row1_c2, row1_c3 = st.columns([3, 1, 1])
with row1_c1:
    sel_labels = st.multiselect(
        "Tickers",
        options=list(_all_options.keys()),
        default=_default_labels,
        help="Select one or more tickers to analyse",
    )
    selected = [_all_options[lbl] for lbl in sel_labels if lbl in _all_options]

with row1_c2:
    period   = st.selectbox("Period",   PERIODS,   index=PERIODS.index(DEFAULT_PERIOD))

with row1_c3:
    interval = st.selectbox("Interval", INTERVALS, index=INTERVALS.index(DEFAULT_INTERVAL))

row2_c1, row2_c2, row2_c3, row2_c4, row2_c5, row2_c6 = st.columns([2, 1, 1, 1, 1, 1])
with row2_c1:
    chart_ticker = st.selectbox(
        "Candlestick chart for",
        options=selected if selected else list(_all_options.values())[:1],
    )
with row2_c2:
    show_bb     = st.checkbox("Bollinger Bands", value=True)
with row2_c3:
    show_rsi    = st.checkbox("RSI (14)",        value=True)
with row2_c4:
    show_macd   = st.checkbox("MACD",            value=False)
with row2_c5:
    show_volume = st.checkbox("Volume",          value=True)

st.markdown("</div>", unsafe_allow_html=True)

if not selected:
    st.info("Select at least one ticker above to get started.")
    st.stop()

# ── Fetch data ────────────────────────────────────────────────────────
with st.spinner("Loading market data…"):
    prices, errors = fetch_prices(selected, period=period, interval=interval)

if prices.empty:
    st.error("No data available.")
    st.stop()

metrics_df = compute_metrics(prices)

# ── ETF summary cards ─────────────────────────────────────────────────
section_header("Summary")
etf_cards(metrics_df)

# ── Chart tabs ────────────────────────────────────────────────────────
tab_candle, tab_perf, tab_corr = st.tabs([
    f"📊 Candlestick — {chart_ticker}",
    "📈 Normalised Performance",
    "🔥 Correlation Matrix",
])

# ── Tab 1: Candlestick ────────────────────────────────────────────────
with tab_candle:
    ticker_data = prices[prices["Ticker"] == chart_ticker].set_index("Date").sort_index()

    if ticker_data.empty:
        st.info(f"No OHLCV data for {chart_ticker}.")
    else:
        n_rows = 1 + int(show_rsi) + int(show_macd) + int(show_volume)
        row_heights = [0.55]
        specs = [[{"secondary_y": False}]]
        if show_rsi:
            row_heights.append(0.18); specs.append([{"secondary_y": False}])
        if show_macd:
            row_heights.append(0.18); specs.append([{"secondary_y": False}])
        if show_volume:
            row_heights.append(0.14); specs.append([{"secondary_y": False}])

        fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                            vertical_spacing=0.04, row_heights=row_heights,
                            subplot_titles=[""] * n_rows)

        fig.add_trace(go.Candlestick(
            x=ticker_data.index,
            open=ticker_data["Open"], high=ticker_data["High"],
            low=ticker_data["Low"],  close=ticker_data["Close"],
            name=chart_ticker,
            increasing_line_color="#0E9F6E", increasing_fillcolor="rgba(14,159,110,.7)",
            decreasing_line_color="#E02749", decreasing_fillcolor="rgba(224,39,73,.7)",
            showlegend=False,
        ), row=1, col=1)

        if show_bb:
            upper, mid, lower = bollinger_bands(ticker_data["Close"])
            fig.add_trace(go.Scatter(x=ticker_data.index, y=upper, name="BB Upper",
                line=dict(color="rgba(36,87,197,.5)", width=1, dash="dot"), showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=ticker_data.index, y=mid, name="BB Mid (20MA)",
                line=dict(color="rgba(199,119,0,.6)", width=1), showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=ticker_data.index, y=lower, name="BB Lower",
                line=dict(color="rgba(36,87,197,.5)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(36,87,197,.03)", showlegend=True), row=1, col=1)

        cur_row = 2
        if show_rsi:
            rsi_vals = rsi(ticker_data["Close"])
            fig.add_trace(go.Scatter(x=ticker_data.index, y=rsi_vals, name="RSI",
                line=dict(color="#C77700", width=1.5), showlegend=False), row=cur_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="rgba(224,39,73,.4)",
                          annotation_text="OB 70", annotation_position="right", row=cur_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="rgba(14,159,110,.4)",
                          annotation_text="OS 30", annotation_position="right", row=cur_row, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="rgba(224,39,73,.04)", line_width=0, row=cur_row, col=1)
            fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(14,159,110,.04)", line_width=0, row=cur_row, col=1)
            fig.update_yaxes(range=[0, 100], row=cur_row, col=1)
            cur_row += 1

        if show_macd:
            m_line, s_line, hist = macd(ticker_data["Close"])
            fig.add_trace(go.Scatter(x=ticker_data.index, y=m_line, name="MACD",
                line=dict(color="#2457C5", width=1.5), showlegend=False), row=cur_row, col=1)
            fig.add_trace(go.Scatter(x=ticker_data.index, y=s_line, name="Signal",
                line=dict(color="#C77700", width=1.2), showlegend=False), row=cur_row, col=1)
            colors = ["#0E9F6E" if v >= 0 else "#E02749" for v in hist.fillna(0)]
            fig.add_trace(go.Bar(x=ticker_data.index, y=hist, marker_color=colors,
                name="Histogram", showlegend=False, opacity=0.7), row=cur_row, col=1)
            cur_row += 1

        if show_volume:
            vol_colors = ["#0E9F6E" if c >= o else "#E02749"
                          for c, o in zip(ticker_data["Close"], ticker_data["Open"])]
            fig.add_trace(go.Bar(x=ticker_data.index, y=ticker_data["Volume"],
                marker_color=vol_colors, name="Volume", showlegend=False, opacity=0.7),
                row=cur_row, col=1)

        layout = dict(**CHART_LAYOUT)
        layout["height"] = 180 + 220 * n_rows
        layout["xaxis_rangeslider_visible"] = False
        layout["margin"] = dict(l=55, r=20, t=20, b=40)
        fig.update_layout(**layout)
        fig.update_xaxes(showgrid=True, gridcolor="#E8E2D6")
        fig.update_yaxes(showgrid=True, gridcolor="#E8E2D6")
        st.plotly_chart(fig, width='stretch')

# ── Tab 2: Normalised Performance ────────────────────────────────────
with tab_perf:
    ts = build_timeseries(prices, selected)
    if ts.empty:
        st.info("No data to display.")
    else:
        palette = ["#2457C5","#0E9F6E","#C77700","#E02749","#A78BFA",
                   "#F59E0B","#10B981","#EF4444","#3B82F6","#EC4899",
                   "#14B8A6","#F97316","#6366F1"]
        fig_line = go.Figure()
        for i, col in enumerate(ts.columns):
            fig_line.add_trace(go.Scatter(
                x=ts.index, y=ts[col], mode="lines", name=col,
                line=dict(color=palette[i % len(palette)], width=2),
            ))
        layout = dict(**CHART_LAYOUT)
        layout.update(height=480, margin=dict(l=55, r=20, t=30, b=60),
                      legend=dict(orientation="h", y=-0.15))
        fig_line.update_layout(**layout)
        fig_line.update_yaxes(title_text="Index (Start = 100)")
        st.plotly_chart(fig_line, width='stretch')

# ── Tab 3: Correlation Matrix ─────────────────────────────────────────
with tab_corr:
    if len(selected) < 2:
        st.info("Select at least 2 tickers to display the correlation matrix.")
    elif len(selected) > 20:
        st.info("Select ≤ 20 tickers to display the correlation heatmap.")
    else:
        cm = corr_matrix(prices, selected)
        if cm is not None and not cm.empty:
            tl = cm.columns.tolist()
            zv = cm.fillna(0).round(3).values.tolist()
            fig_heat = go.Figure(go.Heatmap(
                z=zv, x=tl, y=tl,
                colorscale="RdBu", reversescale=True, zmin=-1, zmax=1,
                text=[[f"{v:.2f}" for v in row] for row in zv],
                texttemplate="%{text}",
                hovertemplate="%{x} · %{y}: %{z:.3f}<extra></extra>",
            ))
            layout = dict(**CHART_LAYOUT)
            layout.update(height=max(400, len(tl) * 34 + 80),
                          margin=dict(l=80, r=20, t=30, b=80))
            fig_heat.update_layout(**layout)
            fig_heat.update_xaxes(tickangle=-45)
            st.plotly_chart(fig_heat, width='stretch')

# ── Downloads ─────────────────────────────────────────────────────────
section_header("Export")
d1, d2 = st.columns(2)
with d1:
    if not metrics_df.empty:
        st.download_button("Summary CSV", metrics_df.to_csv(index=False),
                           f"summary_{period}_{interval}.csv", "text/csv")
with d2:
    if not prices.empty:
        st.download_button("Timeseries CSV", prices.to_csv(index=False),
                           f"timeseries_{period}_{interval}.csv", "text/csv")

disclaimer()
