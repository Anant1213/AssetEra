"""
Stock Research — Screener, Deep Dive, and Comparison for US equities.
Data served from the analytics schema in Supabase (PostgreSQL).
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backend.ui import apply_styles, page_header, section_header, CHART_LAYOUT
from backend.stock_research.analytics_store import (
    get_snapshot,
    get_ohlcv,
    get_analytics_history,
    get_tickers,
)
from backend.stock_research.analytics_store import is_enabled

st.set_page_config(
    page_title="Stock Research — AssetEra",
    page_icon="🔭",
    layout="wide",
)
apply_styles()

# ── Extra CSS for this page ────────────────────────────────────────────
st.markdown("""
<style>
.kpi-grid { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:1rem; }
.kpi-card {
  flex:1 1 140px; min-width:130px; max-width:200px;
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-md); padding:.75rem 1rem;
  transition: border-color .2s, box-shadow .2s;
}
.kpi-card:hover { border-color:var(--border-active); box-shadow:0 0 20px var(--accent-dim); }
.kpi-label { font-size:.65rem; color:var(--text-2); text-transform:uppercase; letter-spacing:.07em; margin-bottom:.3rem; }
.kpi-value { font-size:1.1rem; font-weight:700; font-family:var(--mono); color:var(--text); }
.kpi-value.pos { color:var(--green); }
.kpi-value.neg { color:var(--red); }
.kpi-value.neu { color:var(--yellow); }

.ticker-pill {
  display:inline-block; padding:3px 10px;
  background:var(--accent-dim); border:1px solid var(--accent);
  border-radius:20px; font-family:var(--mono); font-size:.8rem;
  color:var(--accent); font-weight:700; margin-right:6px;
}

.section-rule {
  border:none; border-top:1px solid var(--border); margin:1.2rem 0 .8rem;
}

.preset-btn-row { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)

# ── DB gate ────────────────────────────────────────────────────────────
if not is_enabled():
    page_header("Stock Research", "Screener · Deep Dive · Compare")
    st.error("No data backend configured. Set DATA_BUCKET + AWS credentials (S3) or POSTGRES_URL in your .env file.")
    st.stop()

page_header("Stock Research", "Screener · Deep Dive · Compare", badge="LIVE DB")

# ── Inline universe selector ───────────────────────────────────────────
st.markdown(
    "<div style='background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--r-lg);padding:.9rem 1.2rem;margin-bottom:1rem;'>",
    unsafe_allow_html=True,
)

uc1, uc2, uc3 = st.columns([2, 2, 4])
with uc1:
    market_label = st.selectbox(
        "Market",
        ["US Equities (NYSE/NASDAQ)", "US ETFs & Funds"],
        index=0,
        label_visibility="visible",
    )
    MARKET = "US_EQ" if "Equities" in market_label else "US"

with uc2:
    cap_options = ["All Caps", "Large Cap", "Mid Cap", "Small Cap"]
    cap_sel = st.selectbox("Cap Tier", cap_options, index=0) if MARKET == "US_EQ" else "All Caps"
    CAP = None if cap_sel == "All Caps" else cap_sel.split()[0].upper()

with uc3:
    st.markdown(
        "<p style='font-size:.78rem;color:var(--text-2);line-height:1.6;margin-top:.4rem;'>"
        "Analytics from 10 years of daily OHLCV data. "
        "Rolling metrics: 21d / 63d / 252d windows. "
        "Benchmark: equal-weight large-cap S&P 500 proxy."
        "</p>",
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

# ── Cached data loaders ────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _load_snapshot(market: str, cap: str | None) -> pd.DataFrame:
    return get_snapshot(market, cap)


@st.cache_data(ttl=600, show_spinner=False)
def _load_ohlcv(ticker: str, market: str) -> pd.DataFrame:
    return get_ohlcv(ticker, market, lookback_days=504)


@st.cache_data(ttl=600, show_spinner=False)
def _load_history(ticker: str, market: str) -> dict:
    return get_analytics_history(ticker, market, lookback_days=504)


@st.cache_data(ttl=600, show_spinner=False)
def _load_tickers(market: str, cap: str | None) -> list[str]:
    return get_tickers(market, cap)


# ── Load snapshot ──────────────────────────────────────────────────────
with st.spinner("Loading analytics…"):
    snap = _load_snapshot(MARKET, CAP)

if snap.empty:
    st.warning(
        "No analytics data found. Run `python scripts/run_analytics.py` to populate the database."
    )
    st.stop()

# Numeric coercion helper
_num_cols = [c for c in snap.columns if c not in ("ticker", "as_of", "cap_category", "golden_cross")]
snap[_num_cols] = snap[_num_cols].apply(pd.to_numeric, errors="coerce")

TICKERS = sorted(snap["ticker"].dropna().unique().tolist())

# ── Tabs ───────────────────────────────────────────────────────────────
tab_screen, tab_dive, tab_compare = st.tabs([
    "🔍  Screener",
    "🔬  Deep Dive",
    "⚖️  Compare",
])


# ══════════════════════════════════════════════════════════════════════
# TAB 1 — SCREENER
# ══════════════════════════════════════════════════════════════════════
with tab_screen:

    # ── Metric selector & filters ──────────────────────────────────────
    section_header("Quick Presets")

    PRESETS: dict[str, dict] = {
        "Momentum Leaders":  {"mom_3m_min": 0.05, "rsi_max": 70},
        "Oversold Bounce":   {"rsi_max": 35, "mom_1m_min": -0.10},
        "High Sharpe":       {"sharpe_252d_min": 1.0, "vol_252d_max": 0.30},
        "Near 52w High":     {"hi_52w_pct_min": -3.0},
        "Strong Relative RS":{"rs_vs_bench_min": 1.05},
        "Low Volatility":    {"vol_252d_max": 0.18},
        "Deep Value":        {"pct_vs_ma200_max": -10.0},
        "Golden Cross":      {"golden_cross": True},
    }

    preset_clicked = None
    cols_p = st.columns(len(PRESETS))
    for i, (name, _) in enumerate(PRESETS.items()):
        if cols_p[i].button(name, key=f"preset_{i}"):
            preset_clicked = name

    if preset_clicked:
        st.session_state["active_preset"] = preset_clicked

    active_preset = st.session_state.get("active_preset")
    if active_preset and st.button(f"Clear preset: {active_preset}", key="clear_preset"):
        st.session_state.pop("active_preset", None)
        active_preset = None

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

    # ── Manual filters ─────────────────────────────────────────────────
    section_header("Manual Filters")

    fc1, fc2, fc3, fc4 = st.columns(4)

    with fc1:
        st.markdown("**Returns**")
        ret1d_min  = st.number_input("1d ret ≥ (%)",  value=-100.0, step=0.5, key="f_r1d")
        ret5d_min  = st.number_input("5d ret ≥ (%)",  value=-100.0, step=1.0, key="f_r5d")
        ret21d_min = st.number_input("21d ret ≥ (%)", value=-100.0, step=1.0, key="f_r21d")
        ret63d_min = st.number_input("63d ret ≥ (%)", value=-100.0, step=1.0, key="f_r63d")

    with fc2:
        st.markdown("**Momentum**")
        mom1m_min  = st.number_input("1m mom ≥ (%)",  value=-100.0, step=1.0, key="f_m1m")
        mom3m_min  = st.number_input("3m mom ≥ (%)",  value=-100.0, step=1.0, key="f_m3m")
        mom12m_min = st.number_input("12m mom ≥ (%)", value=-100.0, step=1.0, key="f_m12m")
        rs_min     = st.number_input("RS vs bench ≥", value=0.0, step=0.05, key="f_rs")

    with fc3:
        st.markdown("**Risk**")
        vol_max    = st.number_input("Annual vol ≤ (%)",   value=200.0, step=5.0, key="f_vol")
        sharpe_min = st.number_input("Sharpe 252d ≥",     value=-10.0, step=0.25, key="f_sh")
        dd_max     = st.number_input("Max DD 252d ≥ (%)", value=-100.0, step=5.0, key="f_dd")
        beta_max   = st.number_input("Beta ≤",            value=5.0,  step=0.1,  key="f_beta")

    with fc4:
        st.markdown("**Technical**")
        rsi_min    = st.number_input("RSI ≥",             value=0.0,   step=1.0,  key="f_rsi_min")
        rsi_max    = st.number_input("RSI ≤",             value=100.0, step=1.0,  key="f_rsi_max")
        pct50_min  = st.number_input("% vs MA50 ≥ (%)",  value=-100.0, step=1.0, key="f_ma50")
        pct200_min = st.number_input("% vs MA200 ≥ (%)", value=-100.0, step=1.0, key="f_ma200")

    # ── Apply filters ──────────────────────────────────────────────────
    df = snap.copy()

    # Preset overrides manual
    if active_preset and active_preset in PRESETS:
        p = PRESETS[active_preset]
        if "mom_3m_min"       in p: df = df[df["mom_3m"].fillna(-999)      >= p["mom_3m_min"]]
        if "mom_1m_min"       in p: df = df[df["mom_1m"].fillna(-999)      >= p["mom_1m_min"]]
        if "rsi_max"          in p: df = df[df["rsi_14"].fillna(999)        <= p["rsi_max"]]
        if "sharpe_252d_min"  in p: df = df[df["sharpe_252d"].fillna(-999) >= p["sharpe_252d_min"]]
        if "vol_252d_max"     in p: df = df[df["vol_252d"].fillna(999)      <= p["vol_252d_max"]]
        if "hi_52w_pct_min"   in p: df = df[df["hi_52w_pct"].fillna(-999)  >= p["hi_52w_pct_min"]]
        if "rs_vs_bench_min"  in p: df = df[df["rs_vs_bench"].fillna(-999) >= p["rs_vs_bench_min"]]
        if "pct_vs_ma200_max" in p: df = df[df["pct_vs_ma200"].fillna(999) <= p["pct_vs_ma200_max"]]
        if "golden_cross"     in p: df = df[df["golden_cross"].fillna(False).astype(bool)]
    else:
        # Manual filters (convert % inputs to decimals where needed)
        df = df[df["ret_1d"].fillna(-999)       * 100 >= ret1d_min]
        df = df[df["ret_5d"].fillna(-999)       * 100 >= ret5d_min]
        df = df[df["ret_21d"].fillna(-999)      * 100 >= ret21d_min]
        df = df[df["ret_63d"].fillna(-999)      * 100 >= ret63d_min]
        df = df[df["mom_1m"].fillna(-999)       * 100 >= mom1m_min]
        df = df[df["mom_3m"].fillna(-999)       * 100 >= mom3m_min]
        df = df[df["mom_12m"].fillna(-999)      * 100 >= mom12m_min]
        df = df[df["rs_vs_bench"].fillna(-999)        >= rs_min]
        df = df[df["vol_252d"].fillna(999)      * 100 <= vol_max]
        df = df[df["sharpe_252d"].fillna(-999)        >= sharpe_min]
        df = df[df["max_dd_252d"].fillna(-999)  * 100 >= dd_max]
        df = df[df["beta_252d"].fillna(999)           <= beta_max]
        df = df[df["rsi_14"].fillna(0)                >= rsi_min]
        df = df[df["rsi_14"].fillna(100)              <= rsi_max]
        df = df[df["pct_vs_ma50"].fillna(-999)        >= pct50_min]
        df = df[df["pct_vs_ma200"].fillna(-999)       >= pct200_min]

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:var(--text-2);font-size:.82rem;margin-bottom:.6rem;'>"
        f"Showing <b style='color:var(--text);'>{len(df)}</b> of "
        f"<b style='color:var(--text);'>{len(snap)}</b> tickers"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Display columns ────────────────────────────────────────────────
    DISPLAY_COLS = {
        "ticker":       "Ticker",
        "last_price":   "Price",
        "ret_1d":       "1d %",
        "ret_5d":       "5d %",
        "ret_21d":      "21d %",
        "mom_3m":       "3m Mom%",
        "mom_12m":      "12m Mom%",
        "rsi_14":       "RSI",
        "vol_252d":     "Ann Vol%",
        "sharpe_252d":  "Sharpe",
        "max_dd_252d":  "MaxDD%",
        "beta_252d":    "Beta",
        "rs_vs_bench":  "RS Bench",
        "rank_universe":"Universe Rank",
        "hi_52w_pct":   "52w Hi%",
        "pct_vs_ma50":  "vs MA50%",
        "pct_vs_ma200": "vs MA200%",
        "golden_cross": "GldCross",
    }

    available = [c for c in DISPLAY_COLS if c in df.columns]
    disp = df[available].copy().rename(columns=DISPLAY_COLS)

    # Format percentage columns
    pct_cols_map = {
        "1d %": 100, "5d %": 100, "21d %": 100,
        "3m Mom%": 100, "12m Mom%": 100,
        "Ann Vol%": 100, "MaxDD%": 100,
        "52w Hi%": 1, "vs MA50%": 1, "vs MA200%": 1,
    }
    for col, mult in pct_cols_map.items():
        if col in disp.columns:
            disp[col] = (disp[col] * mult).round(2)

    for col in ["RSI", "Sharpe", "Beta", "RS Bench"]:
        if col in disp.columns:
            disp[col] = disp[col].round(3)

    if "Price" in disp.columns:
        disp["Price"] = disp["Price"].round(2)

    sort_col = st.selectbox(
        "Sort by",
        options=list(DISPLAY_COLS.values())[1:],
        index=list(DISPLAY_COLS.values()).index("3m Mom%") - 1,
        key="screen_sort",
    )
    sort_asc = st.checkbox("Ascending", value=False, key="screen_asc")

    actual_sort = sort_col if sort_col in disp.columns else "Ticker"
    try:
        disp = disp.sort_values(actual_sort, ascending=sort_asc, na_position="last")
    except Exception:
        pass

    # Color-code numeric cells
    def _color_df(df_in: pd.DataFrame):
        styles = pd.DataFrame("", index=df_in.index, columns=df_in.columns)
        green_cols = ["1d %", "5d %", "21d %", "3m Mom%", "12m Mom%", "Sharpe", "RS Bench"]
        red_cols   = ["Ann Vol%", "MaxDD%"]
        for col in green_cols:
            if col in df_in.columns:
                styles[col] = df_in[col].apply(
                    lambda v: "color:#00C896;font-weight:700" if isinstance(v, (int, float)) and v > 0
                    else ("color:#FF3560;font-weight:700" if isinstance(v, (int, float)) and v < 0 else "")
                )
        return styles

    styled = disp.style.apply(_color_df, axis=None)
    st.dataframe(
        styled,
        use_container_width=True,
        height=min(600, 45 + len(disp) * 35),
        hide_index=True,
    )

    # CSV download
    csv_data = disp.to_csv(index=False).encode()
    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name=f"screener_{MARKET}_{CAP or 'ALL'}.csv",
        mime="text/csv",
        key="dl_screen",
    )


# ══════════════════════════════════════════════════════════════════════
# TAB 2 — DEEP DIVE
# ══════════════════════════════════════════════════════════════════════
with tab_dive:

    dd_ticker = st.selectbox("Select ticker", TICKERS, key="dd_ticker")

    row = snap[snap["ticker"] == dd_ticker]
    if row.empty:
        st.warning("No data for this ticker.")
    else:
        row = row.iloc[0]

        # ── KPI cards ──────────────────────────────────────────────────────
        section_header(f"{dd_ticker}  ·  KPI Dashboard")

        def _kpi(label: str, value, fmt: str = "{:.2f}", suffix: str = "", pct_mult: float = 1.0):
            try:
                v = float(value) * pct_mult
                fmtd = fmt.format(v) + suffix
                cls = "pos" if v > 0 else ("neg" if v < 0 else "neu")
            except (TypeError, ValueError):
                fmtd = "—"
                cls = "neu"
            return (
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value {cls}">{fmtd}</div>'
                f'</div>'
            )

        kpi_html = '<div class="kpi-grid">'
        kpi_html += _kpi("Last Price",  row.get("last_price"), "${:.2f}")
        kpi_html += _kpi("1d Return",   row.get("ret_1d"),  "{:+.2f}", "%", 100)
        kpi_html += _kpi("5d Return",   row.get("ret_5d"),  "{:+.2f}", "%", 100)
        kpi_html += _kpi("21d Return",  row.get("ret_21d"), "{:+.2f}", "%", 100)
        kpi_html += _kpi("3m Momentum", row.get("mom_3m"),  "{:+.2f}", "%", 100)
        kpi_html += _kpi("12m Momentum",row.get("mom_12m"), "{:+.2f}", "%", 100)
        kpi_html += _kpi("RSI (14)",    row.get("rsi_14"),  "{:.1f}")
        kpi_html += _kpi("Ann Vol",     row.get("vol_252d"),"{:.1f}",  "%", 100)
        kpi_html += _kpi("Sharpe 252d", row.get("sharpe_252d"), "{:.2f}")
        kpi_html += _kpi("Sortino",     row.get("sortino_252d"), "{:.2f}")
        kpi_html += _kpi("Max DD 252d", row.get("max_dd_252d"), "{:.1f}", "%", 100)
        kpi_html += _kpi("Beta",        row.get("beta_252d"), "{:.2f}")
        kpi_html += _kpi("Alpha (ann)", row.get("alpha_252d"), "{:+.2f}", "%", 100)
        kpi_html += _kpi("RS vs Bench", row.get("rs_vs_bench"), "{:.3f}")
        kpi_html += _kpi("52w Hi Dist", row.get("hi_52w_pct"), "{:+.1f}", "%")
        kpi_html += _kpi("52w Lo Dist", row.get("lo_52w_pct"), "{:+.1f}", "%")
        kpi_html += _kpi("MACD Hist",   row.get("macd_hist"),  "{:+.4f}")
        kpi_html += _kpi("BB %B",       row.get("bb_pct_b"),   "{:.3f}")
        kpi_html += _kpi("vs MA50",     row.get("pct_vs_ma50"),  "{:+.1f}", "%")
        kpi_html += _kpi("vs MA200",    row.get("pct_vs_ma200"), "{:+.1f}", "%")
        kpi_html += '</div>'
        st.markdown(kpi_html, unsafe_allow_html=True)

        # ── Load OHLCV & history ────────────────────────────────────────────
        with st.spinner("Loading price history…"):
            ohlcv = _load_ohlcv(dd_ticker, MARKET)
            hist  = _load_history(dd_ticker, MARKET)

        if ohlcv.empty:
            st.warning("No OHLCV data available for this ticker.")
        else:
            st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
            section_header("Price Chart")

            show_bb  = st.checkbox("Bollinger Bands", value=True, key="dd_bb")
            show_ma  = st.checkbox("Moving Averages (50 / 200)", value=True, key="dd_ma")
            show_rsi = st.checkbox("RSI (14)", value=True, key="dd_rsi")
            show_mac = st.checkbox("MACD", value=False, key="dd_macd")
            show_vol = st.checkbox("Volume", value=True, key="dd_vol")

            # Build subplot row spec
            row_heights = [0.55]
            if show_rsi: row_heights.append(0.15)
            if show_mac: row_heights.append(0.15)
            if show_vol: row_heights.append(0.15)
            n_rows = len(row_heights)

            specs = [[{"secondary_y": False}]] * n_rows
            fig = make_subplots(
                rows=n_rows, cols=1,
                shared_xaxes=True,
                row_heights=row_heights,
                vertical_spacing=0.02,
                specs=specs,
            )

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=ohlcv["Date"], open=ohlcv["Open"], high=ohlcv["High"],
                low=ohlcv["Low"], close=ohlcv["Close"],
                name=dd_ticker,
                increasing_line_color="#00C896",
                decreasing_line_color="#FF3560",
                increasing_fillcolor="#00C896",
                decreasing_fillcolor="#FF3560",
            ), row=1, col=1)

            # Bollinger Bands
            if show_bb and "technical" in hist:
                tec = hist["technical"]
                if "bb_upper" in tec.columns:
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["bb_upper"], name="BB Upper",
                        line=dict(color="rgba(41,98,255,0.45)", width=1, dash="dot"),
                        showlegend=False,
                    ), row=1, col=1)
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["bb_mid"] if "bb_mid" in tec.columns else tec["ma_20"],
                        name="BB Mid",
                        line=dict(color="rgba(41,98,255,0.6)", width=1),
                        showlegend=False,
                    ), row=1, col=1)
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["bb_lower"], name="BB Lower",
                        fill="tonexty" if False else None,
                        line=dict(color="rgba(41,98,255,0.45)", width=1, dash="dot"),
                        showlegend=False,
                    ), row=1, col=1)

            # Moving averages
            if show_ma and "technical" in hist:
                tec = hist["technical"]
                if "ma_50" in tec.columns:
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["ma_50"], name="MA 50",
                        line=dict(color="#FFB020", width=1.2),
                    ), row=1, col=1)
                if "ma_200" in tec.columns:
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["ma_200"], name="MA 200",
                        line=dict(color="#9C27B0", width=1.2),
                    ), row=1, col=1)

            cur_row = 2
            # RSI
            if show_rsi and "technical" in hist:
                tec = hist["technical"]
                if "rsi_14" in tec.columns:
                    fig.add_trace(go.Scatter(
                        x=tec.index, y=tec["rsi_14"], name="RSI 14",
                        line=dict(color="#2962FF", width=1.5),
                    ), row=cur_row, col=1)
                    fig.add_hline(y=70, line=dict(color="#FF3560", dash="dot", width=1), row=cur_row, col=1)
                    fig.add_hline(y=30, line=dict(color="#00C896", dash="dot", width=1), row=cur_row, col=1)
                    fig.update_yaxes(title_text="RSI", row=cur_row, col=1, range=[0, 100])
                    cur_row += 1

            # MACD
            if show_mac and "technical" in hist:
                tec = hist["technical"]
                if "macd_hist" in tec.columns:
                    colors_mac = ["#00C896" if v >= 0 else "#FF3560" for v in tec["macd_hist"].fillna(0)]
                    fig.add_trace(go.Bar(
                        x=tec.index, y=tec["macd_hist"], name="MACD Hist",
                        marker_color=colors_mac, opacity=0.75,
                    ), row=cur_row, col=1)
                    if "macd_line" in tec.columns:
                        fig.add_trace(go.Scatter(
                            x=tec.index, y=tec["macd_line"], name="MACD",
                            line=dict(color="#2962FF", width=1.2),
                        ), row=cur_row, col=1)
                    if "macd_signal" in tec.columns:
                        fig.add_trace(go.Scatter(
                            x=tec.index, y=tec["macd_signal"], name="Signal",
                            line=dict(color="#FFB020", width=1.2),
                        ), row=cur_row, col=1)
                    fig.update_yaxes(title_text="MACD", row=cur_row, col=1)
                    cur_row += 1

            # Volume
            if show_vol:
                vol_colors = [
                    "#00C896" if ohlcv["Close"].iloc[i] >= ohlcv["Open"].iloc[i] else "#FF3560"
                    for i in range(len(ohlcv))
                ]
                fig.add_trace(go.Bar(
                    x=ohlcv["Date"], y=ohlcv["Volume"], name="Volume",
                    marker_color=vol_colors, opacity=0.55,
                ), row=cur_row, col=1)
                fig.update_yaxes(title_text="Volume", row=cur_row, col=1)

            layout_kw = dict(CHART_LAYOUT)
            layout_kw.update(dict(
                height=300 + 130 * (n_rows - 1),
                title=f"{dd_ticker} — Price History",
                xaxis_rangeslider_visible=False,
                showlegend=True,
            ))
            fig.update_layout(**layout_kw)
            fig.update_xaxes(type="date")
            st.plotly_chart(fig, use_container_width=True)

        # ── Analytics panels ────────────────────────────────────────────────
        if hist:
            st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
            section_header("Analytics History")

            panel_tabs = st.tabs(["Returns", "Risk", "Momentum", "Z-Scores", "Technical"])

            RETURNS_COLS = {
                "ret_1d": "1d Ret", "ret_5d": "5d Ret",
                "ret_21d": "21d Ret", "ret_63d": "63d Ret",
                "ret_126d": "6m Ret", "ret_252d": "1yr Ret",
            }
            RISK_COLS = {
                "vol_21d": "Vol 21d", "vol_63d": "Vol 63d", "vol_252d": "Vol 252d",
                "sharpe_63d": "Sharpe 63d", "sharpe_252d": "Sharpe 252d",
                "sortino_252d": "Sortino", "max_dd_252d": "MaxDD",
                "beta_252d": "Beta", "alpha_252d": "Alpha",
            }
            MOM_COLS = {
                "mom_1m": "1m", "mom_3m": "3m", "mom_6m": "6m", "mom_12m": "12m",
                "hi_52w_pct": "52w Hi%", "lo_52w_pct": "52w Lo%",
                "rs_vs_bench": "RS Bench",
            }
            Z_COLS = {
                "z_price_21d": "Price Z 21d", "z_price_63d": "Price Z 63d",
                "z_ret_21d": "Ret Z 21d", "z_cs_ret_1d": "CS Ret Z",
                "pct_ret_1d": "Ret pct", "pct_mom_3m": "Mom3m pct",
            }
            TEC_COLS = {
                "rsi_14": "RSI", "bb_pct_b": "BB %B", "bb_width": "BB Width",
                "macd_hist": "MACD Hist", "pct_vs_ma50": "vs MA50",
                "pct_vs_ma200": "vs MA200",
            }

            def _history_chart(panel_tab, module: str, cols_map: dict, title: str):
                with panel_tab:
                    if module not in hist:
                        st.info(f"No {module} history available.")
                        return
                    df_h = hist[module]
                    available = {k: v for k, v in cols_map.items() if k in df_h.columns}
                    if not available:
                        st.info("No columns available.")
                        return

                    selected_cols = st.multiselect(
                        "Metrics to display",
                        options=list(available.values()),
                        default=list(available.values())[:4],
                        key=f"hist_{module}",
                    )
                    if not selected_cols:
                        st.info("Select at least one metric.")
                        return

                    rev_map = {v: k for k, v in available.items()}
                    sel_keys = [rev_map[c] for c in selected_cols if c in rev_map]

                    fig_h = go.Figure()
                    colors_cycle = ["#2962FF", "#00C896", "#FFB020", "#FF3560", "#9C27B0", "#00BCD4"]
                    for i, key in enumerate(sel_keys):
                        fig_h.add_trace(go.Scatter(
                            x=df_h.index,
                            y=df_h[key],
                            name=available[key],
                            line=dict(color=colors_cycle[i % len(colors_cycle)], width=1.5),
                        ))

                    layout_h = dict(CHART_LAYOUT)
                    layout_h.update(height=320, title=title)
                    fig_h.update_layout(**layout_h)
                    st.plotly_chart(fig_h, use_container_width=True)

            _history_chart(panel_tabs[0], "returns",  RETURNS_COLS, "Return History")
            _history_chart(panel_tabs[1], "risk",     RISK_COLS,    "Risk History")
            _history_chart(panel_tabs[2], "momentum", MOM_COLS,     "Momentum History")
            _history_chart(panel_tabs[3], "zscore",   Z_COLS,       "Z-Score History")
            _history_chart(panel_tabs[4], "technical",TEC_COLS,     "Technical History")


# ══════════════════════════════════════════════════════════════════════
# TAB 3 — COMPARE
# ══════════════════════════════════════════════════════════════════════
with tab_compare:

    section_header("Multi-Ticker Comparison")

    default_tickers = TICKERS[:min(5, len(TICKERS))]
    compare_tickers = st.multiselect(
        "Select tickers to compare (2–10)",
        options=TICKERS,
        default=default_tickers,
        max_selections=10,
        key="cmp_tickers",
    )

    if len(compare_tickers) < 2:
        st.info("Select at least 2 tickers to compare.")
    else:
        # ── Normalised price performance ────────────────────────────────
        section_header("Normalised Price Performance (base = 100)")

        perf_data: dict[str, pd.Series] = {}
        with st.spinner("Loading price data for comparison…"):
            for t in compare_tickers:
                ohlcv_t = _load_ohlcv(t, MARKET)
                if not ohlcv_t.empty:
                    s = ohlcv_t.set_index("Date")["Close"].sort_index()
                    first_valid = s.first_valid_index()
                    if first_valid is not None:
                        perf_data[t] = s / s[first_valid] * 100

        if perf_data:
            fig_c = go.Figure()
            colors_c = ["#2962FF", "#00C896", "#FFB020", "#FF3560", "#9C27B0",
                        "#00BCD4", "#FF7043", "#8BC34A", "#E91E63", "#607D8B"]
            for i, (tkr, series) in enumerate(perf_data.items()):
                fig_c.add_trace(go.Scatter(
                    x=series.index, y=series.values,
                    name=tkr,
                    line=dict(color=colors_c[i % len(colors_c)], width=1.8),
                ))
            layout_c = dict(CHART_LAYOUT)
            layout_c.update(height=420, title="Normalised Performance (rebased to 100)")
            fig_c.update_layout(**layout_c)
            st.plotly_chart(fig_c, use_container_width=True)

        # ── Side-by-side metrics table ───────────────────────────────────
        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
        section_header("Metrics Comparison")

        COMPARE_METRICS = {
            "last_price": "Price",
            "ret_1d":     "1d Ret%",
            "ret_5d":     "5d Ret%",
            "mom_3m":     "3m Mom%",
            "mom_12m":    "12m Mom%",
            "rsi_14":     "RSI",
            "vol_252d":   "Ann Vol%",
            "sharpe_252d":"Sharpe",
            "sortino_252d":"Sortino",
            "max_dd_252d":"MaxDD%",
            "beta_252d":  "Beta",
            "alpha_252d": "Alpha%",
            "rs_vs_bench":"RS Bench",
            "rank_universe":"Rank",
            "hi_52w_pct": "52w Hi%",
            "pct_vs_ma50":"vs MA50%",
            "pct_vs_ma200":"vs MA200%",
            "bb_pct_b":   "BB %B",
            "macd_hist":  "MACD Hist",
        }

        cmp_rows = snap[snap["ticker"].isin(compare_tickers)].copy()
        available_m = {k: v for k, v in COMPARE_METRICS.items() if k in cmp_rows.columns}
        cmp_disp = cmp_rows[["ticker"] + list(available_m.keys())].copy()
        cmp_disp = cmp_disp.rename(columns={"ticker": "Ticker", **available_m})
        cmp_disp = cmp_disp.set_index("Ticker")

        # Scale percent columns
        pct_scale = {
            "1d Ret%": 100, "5d Ret%": 100, "3m Mom%": 100, "12m Mom%": 100,
            "Ann Vol%": 100, "MaxDD%": 100, "Alpha%": 100,
        }
        for col, mult in pct_scale.items():
            if col in cmp_disp.columns:
                cmp_disp[col] = (cmp_disp[col] * mult).round(2)

        for col in ["RSI", "Sharpe", "Sortino", "Beta", "RS Bench", "BB %B", "MACD Hist",
                    "52w Hi%", "vs MA50%", "vs MA200%"]:
            if col in cmp_disp.columns:
                cmp_disp[col] = cmp_disp[col].round(3)

        if "Price" in cmp_disp.columns:
            cmp_disp["Price"] = cmp_disp["Price"].round(2)

        if "Rank" in cmp_disp.columns:
            cmp_disp["Rank"] = cmp_disp["Rank"].astype("Int64")

        def _color_compare(s: pd.Series):
            positive_better = {"1d Ret%", "5d Ret%", "3m Mom%", "12m Mom%",
                                "Sharpe", "Sortino", "RS Bench"}
            negative_better = {"Ann Vol%", "MaxDD%"}
            if s.name in positive_better:
                norm = (s - s.min()) / (s.max() - s.min() + 1e-9)
                return [
                    f"background-color:rgba(0,200,150,{v*0.25:.2f});color:var(--text)"
                    if v > 0.6 else (
                        f"background-color:rgba(255,53,96,{(1-v)*0.2:.2f});color:var(--text)"
                        if v < 0.35 else "color:var(--text)"
                    )
                    for v in norm.fillna(0)
                ]
            elif s.name in negative_better:
                norm = (s - s.min()) / (s.max() - s.min() + 1e-9)
                return [
                    f"background-color:rgba(255,53,96,{v*0.2:.2f});color:var(--text)"
                    if v > 0.6 else (
                        f"background-color:rgba(0,200,150,{(1-v)*0.25:.2f});color:var(--text)"
                        if v < 0.35 else "color:var(--text)"
                    )
                    for v in norm.fillna(0)
                ]
            return ["color:var(--text)"] * len(s)

        cmp_styled = cmp_disp.T.style.apply(_color_compare, axis=1)
        st.dataframe(cmp_styled, use_container_width=True)

        # ── Radar chart for risk profile ─────────────────────────────────
        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
        section_header("Risk / Return Radar")

        radar_cols = {
            "sharpe_252d": "Sharpe",
            "vol_252d":    "Vol (inv)",
            "mom_3m":      "3m Mom",
            "rs_vs_bench": "Rel Strength",
            "max_dd_252d": "DrawDown (inv)",
            "rsi_14":      "RSI norm",
        }

        radar_data: dict[str, list[float]] = {}
        for t in compare_tickers:
            tr = snap[snap["ticker"] == t]
            if tr.empty:
                continue
            tr = tr.iloc[0]

            def _safe(v, default=0.0):
                try: return float(v)
                except: return default

            sharpe   = _safe(tr.get("sharpe_252d"))
            vol      = _safe(tr.get("vol_252d"))
            mom3m    = _safe(tr.get("mom_3m"))
            rs       = _safe(tr.get("rs_vs_bench"), 1.0)
            maxdd    = _safe(tr.get("max_dd_252d"))   # negative
            rsi_val  = _safe(tr.get("rsi_14"), 50.0)

            # Normalise to 0–1 scale for radar
            sharpe_n  = max(0.0, min(1.0, (sharpe + 1) / 4))
            vol_inv_n = max(0.0, min(1.0, 1 - vol / 0.6))
            mom3m_n   = max(0.0, min(1.0, (mom3m + 0.2) / 0.5))
            rs_n      = max(0.0, min(1.0, (rs - 0.5) / 1.0))
            dd_inv_n  = max(0.0, min(1.0, 1 + maxdd / 0.5))
            rsi_n     = max(0.0, min(1.0, 1 - abs(rsi_val - 50) / 50))

            radar_data[t] = [sharpe_n, vol_inv_n, mom3m_n, rs_n, dd_inv_n, rsi_n]

        if radar_data:
            fig_r = go.Figure()
            categories = list(radar_cols.values())
            colors_r = ["#2962FF", "#00C896", "#FFB020", "#FF3560", "#9C27B0",
                        "#00BCD4", "#FF7043", "#8BC34A", "#E91E63", "#607D8B"]

            def _hex_rgba(hex_color: str, alpha: float) -> str:
                h = hex_color.lstrip("#")
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"rgba({r},{g},{b},{alpha})"

            for i, (tkr, vals) in enumerate(radar_data.items()):
                line_color = colors_r[i % len(colors_r)]
                fig_r.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=categories + [categories[0]],
                    name=tkr,
                    line=dict(color=line_color, width=2),
                    fill="toself",
                    fillcolor=_hex_rgba(line_color, 0.10),
                    opacity=0.9,
                ))
            layout_r = dict(CHART_LAYOUT)
            layout_r.update(dict(
                polar=dict(
                    bgcolor="#0A1220",
                    radialaxis=dict(visible=True, range=[0, 1], gridcolor="#1A2840", color="#7A8BA0"),
                    angularaxis=dict(gridcolor="#1A2840", color="#7A8BA0"),
                ),
                height=440,
                title="Risk / Return Profile Radar (normalised 0–1)",
            ))
            fig_r.update_layout(**layout_r)
            st.plotly_chart(fig_r, use_container_width=True)
