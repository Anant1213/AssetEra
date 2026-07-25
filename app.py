"""
AssetEra — Portfolio Intelligence Platform
===========================================
Landing page with live ticker tape and feature overview.
"""

import streamlit as st
from backend.ui import apply_styles, live_ticker_tape, nav_bar

st.set_page_config(
    page_title="AssetEra — Portfolio Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)
apply_styles()
nav_bar(active="Home")

# ── Ticker tape (shared small cached list — never the full ALLOWLIST) ───
live_ticker_tape()

# ── Hero ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="ae-hero">
      <div class="ae-hero-badge">
        <span class="ae-status"></span>
        Live Market Data · Powered by AI
      </div>
      <div class="ae-hero-title">AssetEra</div>
      <div class="ae-hero-sub">Portfolio Intelligence Platform</div>
      <p style="color:var(--text-2);max-width:620px;font-size:.95rem;line-height:1.65;margin-bottom:2rem;">
        Institutional-grade portfolio analytics, quantitative risk modelling, and
        AI-powered investment guidance — built to showcase the intersection of
        finance, machine learning, and data engineering.
      </p>
      <div class="ae-hero-stats">
        <div>
          <div class="ae-stat-n">150</div>
          <div class="ae-stat-l">US Equities</div>
        </div>
        <div>
          <div class="ae-stat-n">13+</div>
          <div class="ae-stat-l">ETFs &amp; Funds</div>
        </div>
        <div>
          <div class="ae-stat-n">1,000+</div>
          <div class="ae-stat-l">Monte Carlo Paths</div>
        </div>
        <div>
          <div class="ae-stat-n">GPT-4o</div>
          <div class="ae-stat-l">AI Advisor</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Feature cards (Row 1) ─────────────────────────────────────────────
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">📈</div>
          <div class="ae-feat-title">Market Watch</div>
          <div class="ae-feat-desc">
            Candlestick charts with RSI, Bollinger Bands &amp; MACD overlays.
            Correlation heatmap and 10 performance metrics for 13 major ETFs.
          </div>
          <span class="ae-feat-tag">Disk-Cached · No Latency</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Market Watch →", key="btn_mw", width='stretch'):
        st.switch_page("pages/1_Market_Watch.py")

with c2:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">🔬</div>
          <div class="ae-feat-title">Fund Backtester</div>
          <div class="ae-feat-desc">
            Full portfolio simulation with Beta, Alpha, Sortino, Calmar and
            Max Drawdown. Equity curves, VaR/CVaR, and upside/downside capture.
          </div>
          <span class="ae-feat-tag">Institutional Metrics</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Fund Backtester →", key="btn_bt", width='stretch'):
        st.switch_page("pages/2_Fund_Backtester.py")

with c3:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">🎯</div>
          <div class="ae-feat-title">Portfolio Builder</div>
          <div class="ae-feat-desc">
            Build custom portfolios with your own stock/ETF allocations.
            Backtest your strategy with full institutional-grade metrics and
            performance analytics. Save and manage multiple portfolios.
          </div>
          <span class="ae-feat-tag">Interactive · Backtest Enabled</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Portfolio Builder →", key="btn_pb", width='stretch'):
        st.switch_page("pages/3_Portfolio_Builder.py")

# ── Feature cards (Row 2) ─────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
c4, c5, c6 = st.columns(3)

with c4:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">🤖</div>
          <div class="ae-feat-title">Risk Profiler</div>
          <div class="ae-feat-desc">
            Gradient Boosting ML model predicts investor risk score.
            Monte Carlo (GBM, 1,000 paths) simulates portfolio growth with
            confidence bands and goal probability.
          </div>
          <span class="ae-feat-tag">ML + Quantitative Finance</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Risk Profiler →", key="btn_rp", width='stretch'):
        st.switch_page("pages/4_Risk_Profiler.py")

with c5:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">💬</div>
          <div class="ae-feat-title">AI Advisor</div>
          <div class="ae-feat-desc">
            Context-aware portfolio Q&amp;A powered by GPT-4o. Feeds fund
            allocations, risk profiles, and market data into the conversation.
          </div>
          <span class="ae-feat-tag">GPT-4o · Streaming</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open AI Advisor →", key="btn_ai", width='stretch'):
        st.switch_page("pages/5_AI_Advisor.py")

with c6:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">🔭</div>
          <div class="ae-feat-title">Stock Research</div>
          <div class="ae-feat-desc">
            Screener with 20+ filters, deep-dive candlestick charts with RSI/MACD/BB,
            and side-by-side comparison with radar charts. 150 US equities (large/mid/small cap).
          </div>
          <span class="ae-feat-tag">Live DB · 10yr History</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Stock Research →", key="btn_res", width='stretch'):
        st.switch_page("pages/6_Research.py")

# ── Row 3: Data Workbench ──────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
dw1, dw2, dw3 = st.columns([1, 2, 1])
with dw2:
    st.markdown(
        """
        <div class="ae-feat">
          <div class="ae-feat-icon">🧠</div>
          <div class="ae-feat-title">Data Workbench</div>
          <div class="ae-feat-desc">
            Upload any CSV, Excel, JSON or Parquet file.
            Get instant profiling, data quality alerts, 8+ auto-generated charts,
            and AI-powered insights. Ask questions about your data in plain English.
          </div>
          <span class="ae-feat-tag">S3 · DuckDB · GPT-4o-mini</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Data Workbench →", key="btn_dw", width='stretch'):
        st.switch_page("pages/7_Data_Workbench.py")

# ── Quick market snapshot ─────────────────────────────────────────────
if tape_df is not None and not tape_df.empty:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="ae-section"><div class="ae-section-bar"></div>'
        '<span class="ae-section-title">Today\'s Snapshot</span></div>',
        unsafe_allow_html=True,
    )

    gainers = tape_df[tape_df["chg_1d_pct"].notna()].nlargest(3, "chg_1d_pct")
    losers  = tape_df[tape_df["chg_1d_pct"].notna()].nsmallest(3, "chg_1d_pct")

    gc, lc = st.columns(2)
    with gc:
        st.markdown("**Top Gainers**")
        for _, r in gainers.iterrows():
            chg = r["chg_1d_pct"]
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:6px 10px;'
                f'background:var(--green-dim);border-radius:8px;margin:3px 0;font-family:var(--mono);font-size:.85rem;">'
                f'<span style="color:var(--text);font-weight:700;">{r["ticker"]}</span>'
                f'<span style="color:var(--green);font-weight:700;">+{chg:.2f}%</span>'
                f'<span style="color:var(--text-2);">${r["last"]:.2f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with lc:
        st.markdown("**Top Losers**")
        for _, r in losers.iterrows():
            chg = r["chg_1d_pct"]
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:6px 10px;'
                f'background:var(--red-dim);border-radius:8px;margin:3px 0;font-family:var(--mono);font-size:.85rem;">'
                f'<span style="color:var(--text);font-weight:700;">{r["ticker"]}</span>'
                f'<span style="color:var(--red);font-weight:700;">{chg:.2f}%</span>'
                f'<span style="color:var(--text-2);">${r["last"]:.2f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Footer ────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    '<div class="ae-disclaimer">'
    'AssetEra is a portfolio analytics research tool. '
    'All data is for educational purposes only and does not constitute investment advice. '
    'Past performance is not indicative of future results.'
    '</div>',
    unsafe_allow_html=True,
)
