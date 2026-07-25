"""
AssetEra Design System v2.0
============================
Light off-white finance dashboard CSS + reusable HTML component helpers.
Call apply_styles() at the top of every page.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()   # ensure .env is loaded for every page that imports this module

# ── Shared chart palette (light theme) ────────────────────────────────
# Kept in sync with the CSS design tokens below so charts and UI match.
CHART_PLOT_BG = "#FFFFFF"
CHART_GRID    = "#E8E2D6"
CHART_ZERO    = "#C9C2B4"
CHART_ACCENT  = "#2457C5"
CHART_GREEN   = "#0E9F6E"
CHART_RED     = "#E02749"
CHART_YELLOW  = "#C77700"
CHART_TEXT    = "#1F2933"
CHART_TEXT_2  = "#5F6B7A"

# ── Plotly chart defaults ─────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=CHART_PLOT_BG,
    font=dict(family="Inter, sans-serif", color=CHART_TEXT, size=12),
    xaxis=dict(gridcolor=CHART_GRID, zeroline=False, showgrid=True),
    yaxis=dict(gridcolor=CHART_GRID, zeroline=False, showgrid=True),
    legend=dict(
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="#D8D1C3",
        borderwidth=1,
        font=dict(size=11),
    ),
    margin=dict(l=50, r=20, t=40, b=40),
    hoverlabel=dict(
        bgcolor="#FFFFFF",
        bordercolor="#D8D1C3",
        font=dict(family="JetBrains Mono, monospace", size=12, color=CHART_TEXT),
    ),
)

# ── Full CSS design system ────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Design Tokens ───────────────────────────────────────────────── */
:root {
  --bg:            #FAF8F2;
  --bg-elevated:   #F3EFE7;
  --bg-card:       #FFFFFF;
  --bg-overlay:    #F5F1E8;
  --border-dim:    #E8E2D6;
  --border:        #D8D1C3;
  --border-active: #2457C5;
  --accent:        #2457C5;
  --accent-dim:    rgba(36,87,197,0.10);
  --accent-glow:   rgba(36,87,197,0.22);
  --green:         #0E9F6E;
  --green-dim:     rgba(14,159,110,0.12);
  --red:           #E02749;
  --red-dim:       rgba(224,39,73,0.10);
  --yellow:        #C77700;
  --yellow-dim:    rgba(199,119,0,0.12);
  --text:          #1F2933;
  --text-2:        #5F6B7A;
  --text-3:        #6B7280;   /* darkened for AA contrast (≈4.6:1 on --bg) */
  --mono:          'JetBrains Mono', 'Cascadia Code', monospace;
  --sans:          'Inter', system-ui, sans-serif;
  --r-sm:  6px;
  --r-md:  10px;
  --r-lg:  14px;
  --r-xl:  20px;
}

/* ── Reset ───────────────────────────────────────────────────────── */
#MainMenu, header[data-testid="stHeader"], footer,
.stDeployButton { visibility:hidden !important; height:0 !important; }
/* Keep the sidebar expand/collapse toggle reachable even though the
   Streamlit header is hidden — otherwise native page nav can vanish. */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
  visibility:visible !important;
  height:auto !important;
  z-index:1000 !important;
}
.block-container { padding:0.5rem 1.8rem 2rem !important; max-width:100% !important; }
.stApp { background:var(--bg); color:var(--text); font-family:var(--sans); }

/* ── Shared top navigation ───────────────────────────────────────── */
.ae-nav {
  display:flex; flex-wrap:wrap; gap:6px; align-items:center;
  padding:.55rem 0 .85rem; margin:0 0 .2rem;
  border-bottom:1px solid var(--border-dim);
}
.ae-nav a {
  text-decoration:none; white-space:nowrap;
  font-size:.8rem; font-weight:600; color:var(--text-2);
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:100px; padding:.32rem .82rem; line-height:1;
  transition:border-color .15s, color .15s, background .15s;
}
.ae-nav a:hover { border-color:var(--accent); color:var(--accent); }
.ae-nav a.active {
  background:var(--accent); border-color:var(--accent); color:#fff;
}
@media (max-width:640px){ .ae-nav a { font-size:.76rem; padding:.3rem .7rem; } }

/* ── Sidebar ─────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: #F1ECE1 !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p { color:var(--text-2) !important; font-size:0.84rem !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { font-size:0.78rem !important; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-3) !important; font-weight:700 !important; margin:1.2rem 0 0.4rem !important; }

/* ── Metric cards ────────────────────────────────────────────────── */
[data-testid="metric-container"] {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-lg) !important;
  padding:1rem 1.2rem !important;
  transition: border-color .2s, box-shadow .2s;
}
[data-testid="metric-container"]:hover {
  border-color:var(--border-active) !important;
  box-shadow: 0 0 28px var(--accent-dim) !important;
}
[data-testid="stMetricLabel"] > div {
  color:var(--text-2) !important;
  font-size:0.72rem !important;
  text-transform:uppercase;
  letter-spacing:0.08em;
  font-weight:600 !important;
}
[data-testid="stMetricValue"] {
  font-family:var(--mono) !important;
  font-size:1.35rem !important;
  font-weight:600 !important;
  color:var(--text) !important;
}
[data-testid="stMetricDelta"] svg { display:none !important; }
[data-testid="stMetricDelta"] > div {
  font-family:var(--mono) !important;
  font-size:0.78rem !important;
  font-weight:700 !important;
  padding:2px 8px !important;
  border-radius:4px !important;
  display:inline-block !important;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton > button {
  border-radius:var(--r-md) !important;
  font-weight:600 !important;
  font-family:var(--sans) !important;
  font-size:0.88rem !important;
  letter-spacing:0.01em !important;
  transition: all .2s !important;
}
.stButton > button[kind="primary"] {
  background:var(--accent) !important;
  color:#fff !important;
  border:none !important;
  padding:0.52rem 1.6rem !important;
  box-shadow: 0 2px 14px var(--accent-dim) !important;
}
.stButton > button[kind="primary"]:hover {
  background:#1C46A8 !important;
  box-shadow: 0 4px 24px var(--accent-glow) !important;
  transform:translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
  background:var(--bg-card) !important;
  color:var(--text) !important;
  border:1px solid var(--border) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color:var(--border-active) !important;
  color:var(--text) !important;
}
.stDownloadButton > button {
  background:var(--bg-card) !important;
  color:var(--text) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-md) !important;
  font-weight:500 !important;
}
.stDownloadButton > button:hover { border-color:var(--accent) !important; }

/* ── Tabs ────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-lg) !important;
  padding:4px !important; gap:2px !important;
}
.stTabs [data-baseweb="tab"] {
  background:transparent !important;
  border-radius:var(--r-md) !important;
  color:var(--text-2) !important;
  font-weight:500 !important;
  font-size:0.86rem !important;
  padding:0.38rem 0.9rem !important;
}
.stTabs [aria-selected="true"] {
  background:var(--accent) !important;
  color:#fff !important;
  font-weight:600 !important;
}

/* ── Form inputs ─────────────────────────────────────────────────── */
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-md) !important;
}
.stNumberInput input, .stTextInput input, .stDateInput input {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-md) !important;
  color:var(--text) !important;
  font-family:var(--mono) !important;
}
.stCheckbox label { color:var(--text-2) !important; font-size:0.86rem !important; }

/* ── Expander ────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  border-radius:var(--r-lg) !important;
  color:var(--text) !important;
  font-weight:600 !important;
}
.streamlit-expanderContent {
  background:var(--bg-elevated) !important;
  border:1px solid var(--border) !important;
  border-top:none !important;
  border-radius:0 0 var(--r-lg) var(--r-lg) !important;
}

/* ── Dataframes ──────────────────────────────────────────────────── */
[data-testid="stDataFrameResizable"] {
  border:1px solid var(--border) !important;
  border-radius:var(--r-lg) !important;
  overflow:hidden;
}

/* ── Chat ────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  background:var(--bg-card) !important;
  border:1px solid var(--border-dim) !important;
  border-radius:var(--r-lg) !important;
}
.stChatInput textarea {
  background:var(--bg-card) !important;
  border:1px solid var(--border) !important;
  color:var(--text) !important;
  font-family:var(--sans) !important;
}

/* ── Misc ────────────────────────────────────────────────────────── */
hr { border-color:var(--border) !important; opacity:1 !important; margin:1.2rem 0 !important; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:var(--bg); }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:var(--accent); }
.stAlert { border-radius:var(--r-md) !important; }

/* ══════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS
   ══════════════════════════════════════════════════════════════════ */

/* ── Ticker Tape ─────────────────────────────────────────────────── */
.ae-tape {
  background:var(--bg-elevated);
  border-bottom:1px solid var(--border);
  overflow:hidden;
  padding:9px 0;
  margin:-0.5rem -1.8rem 1.5rem -1.8rem;
  position:relative;
}
.ae-tape::before, .ae-tape::after {
  content:''; position:absolute; top:0; width:60px; height:100%;
  z-index:2; pointer-events:none;
}
.ae-tape::before { left:0; background:linear-gradient(to right, var(--bg-elevated), transparent); }
.ae-tape::after  { right:0; background:linear-gradient(to left, var(--bg-elevated), transparent); }
.ae-tape-inner {
  display:inline-flex; gap:2.5rem; animation:ae-scroll 80s linear infinite;
  white-space:nowrap; padding:0 2rem;
}
.ae-tape-inner:hover { animation-play-state:paused; }
@keyframes ae-scroll { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
.ae-tick { display:inline-flex; align-items:center; gap:7px; font-family:var(--mono); font-size:0.79rem; }
.ae-tick-sym { font-weight:700; color:var(--text); }
.ae-tick-px { color:var(--text-2); }
.ae-tick-up  { color:var(--green); font-weight:600; }
.ae-tick-dn  { color:var(--red);   font-weight:600; }
.ae-tick-sep { color:var(--border); margin:0 0.3rem; }

/* ── Page Header ─────────────────────────────────────────────────── */
.ae-header {
  padding:1.2rem 0 1rem;
  border-bottom:1px solid var(--border-dim);
  margin-bottom:1.4rem;
  display:flex; flex-direction:column; gap:4px;
}
.ae-header-top { display:flex; align-items:center; gap:10px; }
.ae-title { font-size:1.8rem; font-weight:800; letter-spacing:-0.02em; color:var(--text); }
.ae-badge {
  display:inline-flex; align-items:center; gap:5px;
  background:var(--accent-dim); color:var(--accent);
  font-size:0.7rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.1em; padding:3px 10px; border-radius:100px;
  border:1px solid rgba(36,87,197,0.18);
}
.ae-subtitle { font-size:0.9rem; color:var(--text-2); font-weight:400; }

/* ── Section Header ──────────────────────────────────────────────── */
.ae-section {
  display:flex; align-items:center; gap:9px;
  margin:1.6rem 0 0.8rem;
}
.ae-section-bar { width:3px; height:18px; background:var(--accent); border-radius:2px; flex-shrink:0; }
.ae-section-title {
  font-size:0.78rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.1em; color:var(--text-2);
}

/* ── ETF Cards ───────────────────────────────────────────────────── */
.ae-etf-grid {
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(215px, 1fr));
  gap:10px; margin-bottom:1.5rem;
}
.ae-etf {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:1rem 1.1rem;
  transition:all .2s; cursor:default;
}
.ae-etf:hover {
  border-color:var(--accent); background:var(--bg-overlay);
  transform:translateY(-2px);
  box-shadow:0 8px 24px rgba(31,41,51,.10);
}
.ae-etf-hdr { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }
.ae-etf-sym { font-family:var(--mono); font-weight:800; font-size:0.95rem; color:var(--text); }
.ae-chip-up { background:var(--green-dim); color:var(--green); font-size:0.68rem; font-weight:700; padding:2px 7px; border-radius:4px; font-family:var(--mono); }
.ae-chip-dn { background:var(--red-dim);   color:var(--red);   font-size:0.68rem; font-weight:700; padding:2px 7px; border-radius:4px; font-family:var(--mono); }
.ae-etf-px { font-family:var(--mono); font-size:1.55rem; font-weight:700; color:var(--text); margin:4px 0 8px; }
.ae-etf-grid2 { display:grid; grid-template-columns:1fr 1fr; gap:2px 10px; font-size:0.73rem; }
.ae-ml { color:var(--text-3); }
.ae-mv-up { color:var(--green); font-weight:600; font-family:var(--mono); }
.ae-mv-dn { color:var(--red);   font-weight:600; font-family:var(--mono); }
.ae-mv-nu { color:var(--text-2); font-family:var(--mono); }
.ae-etf-rng {
  margin-top:8px; padding-top:7px;
  border-top:1px solid var(--border-dim);
  font-size:0.7rem; color:var(--text-3);
}
.ae-rng-bar { background:var(--border-dim); height:3px; border-radius:2px; margin:4px 0; }
.ae-rng-fill { background:var(--accent); height:100%; border-radius:2px; }
.ae-rng-lbl { display:flex; justify-content:space-between; font-family:var(--mono); font-size:0.66rem; color:var(--text-3); }

/* ── KPI Strip ───────────────────────────────────────────────────── */
.ae-kpi-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:1.4rem; }
.ae-kpi {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:.9rem 1.1rem;
  transition:all .2s;
}
.ae-kpi:hover { border-color:var(--accent); box-shadow:0 0 20px var(--accent-dim); }
.ae-kpi-lbl { font-size:0.67rem; font-weight:700; text-transform:uppercase; letter-spacing:.09em; color:var(--text-3); margin-bottom:.3rem; }
.ae-kpi-val { font-family:var(--mono); font-size:1.3rem; font-weight:700; color:var(--text); }
.ae-kpi-sub { font-family:var(--mono); font-size:0.74rem; font-weight:600; margin-top:2px; }
.ae-kpi-sub.up { color:var(--green); }
.ae-kpi-sub.dn { color:var(--red); }
.ae-kpi-sub.nu { color:var(--text-2); }

/* ── Landing hero ────────────────────────────────────────────────── */
.ae-hero {
  background: linear-gradient(135deg, rgba(36,87,197,.08) 0%, rgba(14,159,110,.04) 60%, transparent 100%);
  border:1px solid var(--border); border-radius:var(--r-xl);
  padding:3rem 2.5rem 2.5rem; margin-bottom:2rem; position:relative; overflow:hidden;
}
.ae-hero::before {
  content:''; position:absolute; top:-80px; right:-80px;
  width:300px; height:300px; border-radius:50%;
  background:radial-gradient(circle, rgba(36,87,197,.12) 0%, transparent 70%);
}
.ae-hero-badge {
  display:inline-flex; align-items:center; gap:6px;
  background:var(--green-dim); color:var(--green);
  font-size:0.72rem; font-weight:700; text-transform:uppercase;
  letter-spacing:.1em; padding:4px 12px; border-radius:100px;
  border:1px solid rgba(14,159,110,.2); margin-bottom:1rem;
}
.ae-status { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 6px var(--green); animation:ae-pulse 2s infinite; }
@keyframes ae-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.ae-hero-title { font-size:3rem; font-weight:800; letter-spacing:-.04em; color:var(--text); margin:0 0 .4rem; }
.ae-hero-sub { font-size:1.1rem; color:var(--text-2); font-weight:400; margin-bottom:1.5rem; }
.ae-hero-stats { display:flex; gap:2.5rem; }
.ae-stat-n { font-family:var(--mono); font-size:1.6rem; font-weight:700; color:var(--accent); }
.ae-stat-l { font-size:0.8rem; color:var(--text-2); margin-top:1px; }

/* ── Feature cards (landing) ─────────────────────────────────────── */
.ae-feat {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-xl); padding:1.6rem 1.4rem;
  transition:all .25s; height:100%;
}
.ae-feat:hover {
  border-color:var(--accent); background:var(--bg-overlay);
  transform:translateY(-3px); box-shadow:0 12px 32px rgba(31,41,51,.12);
}
.ae-feat-icon { font-size:1.8rem; margin-bottom:.8rem; }
.ae-feat-title { font-size:1rem; font-weight:700; color:var(--text); margin-bottom:.4rem; }
.ae-feat-desc { font-size:0.84rem; color:var(--text-2); line-height:1.55; }
.ae-feat-tag {
  display:inline-block; margin-top:.8rem;
  font-size:0.68rem; font-weight:700; text-transform:uppercase;
  letter-spacing:.08em; color:var(--accent);
  background:var(--accent-dim); padding:3px 9px; border-radius:100px;
}

/* ── Disclaimer ──────────────────────────────────────────────────── */
.ae-disclaimer {
  background:var(--bg-elevated); border:1px solid var(--border-dim);
  border-left:3px solid var(--yellow); border-radius:0 var(--r-md) var(--r-md) 0;
  padding:.55rem 1rem; font-size:0.76rem; color:var(--text-2); margin:1rem 0;
}

/* ── Risk score ──────────────────────────────────────────────────── */
.ae-risk-card {
  background:var(--bg-card); border-radius:var(--r-xl);
  padding:2rem; text-align:center; border:2px solid;
  box-shadow:0 0 40px;
}
</style>
"""


def apply_styles() -> None:
    """Inject the full AssetEra design system CSS."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Shared navigation ─────────────────────────────────────────────────
# (label, url). Streamlit derives each page URL from its filename minus the
# leading number/underscore, e.g. pages/1_Market_Watch.py -> /Market_Watch.
NAV_ITEMS: list[tuple[str, str]] = [
    ("Home",              "/"),
    ("Market Watch",      "/Market_Watch"),
    ("Fund Backtester",   "/Fund_Backtester"),
    ("Portfolio Builder", "/Portfolio_Builder"),
    ("Risk Profiler",     "/Risk_Profiler"),
    ("AI Advisor",        "/AI_Advisor"),
    ("Stock Research",    "/Research"),
    ("Data Workbench",    "/Data_Workbench"),
]


def nav_bar(active: str = "") -> None:
    """Render a horizontal top-nav linking to Home and all pages.

    Uses plain anchor links (target=_self) so navigation works regardless of
    whether the native Streamlit sidebar is visible or collapsed.
    """
    parts = []
    for label, url in NAV_ITEMS:
        cls = ' class="active"' if label == active else ""
        parts.append(f'<a href="{url}" target="_self"{cls}>{label}</a>')
    st.html(f'<nav class="ae-nav">{"".join(parts)}</nav>')


def page_header(title: str, subtitle: str = "", badge: str = "") -> None:
    nav_bar(active=title)
    badge_html = f'<span class="ae-badge">{badge}</span>' if badge else ""
    subtitle_html = f'<div class="ae-subtitle">{subtitle}</div>' if subtitle else ""
    st.html(
        f"""
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:.25rem;">
          <a href="/" target="_self"
             style="display:inline-flex;align-items:center;justify-content:center;
                    background:var(--bg-card);border:1px solid var(--border);
                    border-radius:10px;padding:.38rem .65rem;
                    font-family:var(--mono);font-weight:800;font-size:.85rem;
                    color:var(--accent);letter-spacing:.04em;line-height:1;
                    text-decoration:none;flex-shrink:0;
                    transition:border-color .2s,box-shadow .2s;"
             onmouseover="this.style.borderColor='var(--accent)';this.style.boxShadow='0 0 14px var(--accent-glow)'"
             onmouseout="this.style.borderColor='var(--border)';this.style.boxShadow='none'"
             title="Back to Home">AE</a>
          <div class="ae-header" style="margin:0;flex:1;">
            <div class="ae-header-top">
              <span class="ae-title">{title}</span>
              {badge_html}
            </div>
            {subtitle_html}
          </div>
        </div>
        """
    )


def section_header(title: str) -> None:
    st.html(
        f"""
        <div class="ae-section">
          <div class="ae-section-bar"></div>
          <span class="ae-section-title">{title}</span>
        </div>
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def _tape_metrics_cached():
    """Fetch + compute metrics for the small shared tape list (cached 5 min)."""
    from backend import market
    prices, _ = market.fetch_prices(market.TAPE_TICKERS, period="5d", interval="1d")
    return market.compute_metrics(prices)


def live_ticker_tape() -> None:
    """Render the shared, small, cached ticker tape.

    This is the single entry point every page should use for the decorative
    top-of-page tape. It fetches only ``market.TAPE_TICKERS`` (~10 symbols),
    is cached for 5 minutes, and never raises — the tape is cosmetic and must
    never block or break page rendering.
    """
    try:
        ticker_tape(_tape_metrics_cached())
    except Exception:
        # Decorative widget only — degrade silently rather than break the page.
        return


def ticker_tape(metrics_df: pd.DataFrame) -> None:
    """Render an animated ticker tape from a metrics DataFrame."""
    if metrics_df is None or metrics_df.empty:
        return
    items = []
    for _, row in metrics_df.iterrows():
        chg = row.get("chg_1d_pct") or 0.0
        cls = "up" if chg >= 0 else "dn"
        sign = "+" if chg >= 0 else ""
        items.append(
            f'<span class="ae-tick">'
            f'<span class="ae-tick-sym">{row["ticker"]}</span>'
            f'<span class="ae-tick-px">${row["last"]:.2f}</span>'
            f'<span class="ae-tick-{cls}">{sign}{chg:.2f}%</span>'
            f'</span>'
            f'<span class="ae-tick-sep">·</span>'
        )
    inner = "".join(items) * 2  # duplicate for seamless loop
    st.html(f'<div class="ae-tape"><div class="ae-tape-inner">{inner}</div></div>')


def etf_cards(metrics_df: pd.DataFrame) -> None:
    """Render Bloomberg-style ETF cards grid."""
    if metrics_df is None or metrics_df.empty:
        return

    def _fmt(v, pct=False, dollar=False):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        if dollar:
            return f"${v:,.2f}"
        if pct:
            return f"{'+' if v >= 0 else ''}{v:.2f}%"
        return f"{v:.2f}"

    def _cls(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "nu"
        return "up" if v >= 0 else "dn"

    cards_html = '<div class="ae-etf-grid">'
    for _, r in metrics_df.iterrows():
        chg = r.get("chg_1d_pct")
        chip_cls = "ae-chip-up" if (chg or 0) >= 0 else "ae-chip-dn"
        lo, hi, last = r.get("lo_52w"), r.get("hi_52w"), r.get("last", 0)
        pct_pos = 0.0
        if lo and hi and hi > lo:
            pct_pos = max(0, min(100, (last - lo) / (hi - lo) * 100))

        rows = [
            ("YTD", r.get("ytd_pct"), True),
            ("1M",  r.get("ret_1m_pct"), True),
            ("3M",  r.get("ret_3m_pct"), True),
            ("1Y",  r.get("ret_1y_pct"), True),
            ("VOL", r.get("vol_ann_pct"), True),
            ("6M",  r.get("ret_6m_pct"), True),
        ]
        grid_html = "".join(
            f'<span class="ae-ml">{lbl}</span>'
            f'<span class="ae-mv-{_cls(val)}">{_fmt(val, pct=is_pct)}</span>'
            for lbl, val, is_pct in rows
        )

        cards_html += f"""
        <div class="ae-etf">
          <div class="ae-etf-hdr">
            <span class="ae-etf-sym">{r["ticker"]}</span>
            <span class="{chip_cls}">{_fmt(chg, pct=True)}</span>
          </div>
          <div class="ae-etf-px">{_fmt(r.get("last"), dollar=True)}</div>
          <div class="ae-etf-grid2">{grid_html}</div>
          <div class="ae-etf-rng">
            52W Range
            <div class="ae-rng-bar"><div class="ae-rng-fill" style="width:{pct_pos:.1f}%"></div></div>
            <div class="ae-rng-lbl">
              <span>{_fmt(lo, dollar=True)}</span>
              <span>{_fmt(hi, dollar=True)}</span>
            </div>
          </div>
        </div>
        """
    cards_html += "</div>"
    st.html(cards_html)


def kpi_row(items: list[dict]) -> None:
    """
    Render a row of KPI tiles.
    items = [{"label": str, "value": str, "delta": str, "delta_dir": "up"|"dn"|"nu"}, ...]
    """
    html = '<div class="ae-kpi-row">'
    for item in items:
        sub_cls = item.get("delta_dir", "nu")
        sub_html = (
            f'<div class="ae-kpi-sub {sub_cls}">{item["delta"]}</div>'
            if item.get("delta") else ""
        )
        html += f"""
        <div class="ae-kpi">
          <div class="ae-kpi-lbl">{item["label"]}</div>
          <div class="ae-kpi-val">{item["value"]}</div>
          {sub_html}
        </div>
        """
    html += "</div>"
    st.html(html)


def disclaimer(text: str = "For educational purposes only. Not investment advice.") -> None:
    st.html(f'<div class="ae-disclaimer">⚠ {text}</div>')


def skeleton_loader(rows: int = 3, height: str = "80px") -> None:
    """Render a skeleton loading animation."""
    skeleton_css = """
    <style>
    @keyframes skeleton-loading {
      0% { background-position: -1000px 0; }
      100% { background-position: 1000px 0; }
    }
    .skeleton-loader {
      height: """ + height + """;
      background: linear-gradient(90deg, var(--bg-card) 25%, var(--bg-overlay) 50%, var(--bg-card) 75%);
      background-size: 1000px 100%;
      animation: skeleton-loading 2s infinite;
      border-radius: var(--r-lg);
      margin-bottom: 12px;
    }
    </style>
    """
    st.markdown(skeleton_css, unsafe_allow_html=True)
    for _ in range(rows):
        st.markdown('<div class="skeleton-loader"></div>', unsafe_allow_html=True)
