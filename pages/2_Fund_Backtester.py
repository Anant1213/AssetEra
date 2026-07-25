"""
Fund Backtester — Institutional-grade portfolio simulation.

Metrics: CAGR, Sharpe, Sortino, Calmar, Beta, Alpha, Max Drawdown, VaR/CVaR.
"""

from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.ui import apply_styles, page_header, section_header, kpi_row, live_ticker_tape, disclaimer, CHART_LAYOUT
from backend.market import fetch_prices
from backend.indicators import (
    max_drawdown, drawdown_series, compute_beta_alpha,
    sortino_ratio, calmar_ratio,
)

st.set_page_config(page_title="Fund Backtester — AssetEra", page_icon="🔬", layout="wide")
apply_styles()

TRADING_DAYS = 252

# ── Fund definitions ──────────────────────────────────────────────────
FUNDS: Dict[str, Dict] = {
    "F1": {"name": "Fund 1 — Core Income",         "risk": 1,
        "allocations": {"LQD":0.50,"IEF":0.20,"GLD":0.10,"VEA":0.10,"MSFT":0.02,"APH":0.02,"GWW":0.02,"PH":0.02,"BSX":0.02}, "default_fee":0.002},
    "F2": {"name": "Fund 2 — Pro Core",             "risk": 2,
        "allocations": {"LQD":0.30,"IEF":0.10,"GLD":0.08,"VEA":0.12,"SPY":0.12,"MSFT":0.03,"APH":0.03,"GWW":0.03,"PH":0.03,"BSX":0.03,"ETN":0.03,"EME":0.025,"PWR":0.025,"FAST":0.025,"BWXT":0.025}, "default_fee":0.002},
    "F3": {"name": "Fund 3 — Pro Growth 17",        "risk": 3,
        "allocations": {"LQD":0.098,"IEF":0.098,"SPY":0.06,"VEA":0.12,"GLD":0.112,"NVDA":0.025,"AVGO":0.025,"MSFT":0.025,"KLAC":0.025,"CDNS":0.025,"ETN":0.025,"PH":0.025,"HEI":0.025,"EME":0.025,"PWR":0.025,"FAST":0.025,"BWXT":0.025,"IDCC":0.03029,"RDNT":0.03029,"DY":0.03029,"GPI":0.03029,"ACLS":0.03029,"TTMI":0.03029,"AGM":0.03029}, "default_fee":0.002},
    "F4": {"name": "Fund 4 — Redeem Surge 31",      "risk": 5,
        "allocations": {"NVDA":0.24,"AVGO":0.12,"KLAC":0.06,"CDNS":0.06,"IDCC":0.0125,"RDNT":0.0125,"ACLS":0.0125,"GPI":0.0125,"VWO":0.32,"GLD":0.15}, "default_fee":0.002},
    "F5": {"name": "Fund 5 — Bridge Growth 26",     "risk": 4,
        "allocations": {"NVDA":0.10,"AVGO":0.07,"KLAC":0.06,"CDNS":0.05,"MSFT":0.05,"ETN":0.05,"EME":0.04,"PWR":0.04,"FAST":0.025,"BWXT":0.025,"IDCC":0.06,"RDNT":0.06,"ACLS":0.06,"GPI":0.05,"AGM":0.05,"TTMI":0.05,"VEA":0.08,"GLD":0.04,"VWO":0.02,"LQD":0.012,"IEF":0.008}, "default_fee":0.002},
}
BENCHMARKS = {
    "SPY":  {"name":"S&P 500 (SPY)",          "def":{"type":"single","ticker":"SPY"}},
    "GLD":  {"name":"Gold (GLD)",              "def":{"type":"single","ticker":"GLD"}},
    "VEA":  {"name":"Developed ex-US (VEA)",   "def":{"type":"single","ticker":"VEA"}},
    "IEF":  {"name":"UST 7-10y (IEF)",         "def":{"type":"single","ticker":"IEF"}},
    "LQD":  {"name":"US IG Corp (LQD)",         "def":{"type":"single","ticker":"LQD"}},
    "60/40":{"name":"60/40 (SPY/IEF)",         "def":{"type":"mix","weights":{"SPY":0.6,"IEF":0.4}}},
    "80/20":{"name":"80/20 (SPY/IEF)",         "def":{"type":"mix","weights":{"SPY":0.8,"IEF":0.2}}},
    "AW":   {"name":"All-Weather (35/35/30)", "def":{"type":"mix","weights":{"SPY":0.35,"IEF":0.35,"GLD":0.30}}},
}

# ── Helpers ───────────────────────────────────────────────────────────
def _clamp(d): return min(d, date.today())
def _years(d0, d1): return max((d1-d0).days,0)/365.25

@st.cache_data(show_spinner=False, ttl=300)
def _fetch(tickers: tuple, start: date, end: date) -> pd.DataFrame:
    """Load prices from configured market store (PostgreSQL/CSV fallback)."""
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

def _renorm(w, keep):
    f={t:v for t,v in w.items() if t in keep and v>0}
    s=sum(f.values())
    return {t:v/s for t,v in f.items()} if s>0 else {}

def _portfolio_path(rets, weights, rebalance="Annual", fee=0.0):
    tickers=list(weights.keys())
    W=np.array([weights[t] for t in tickers],dtype=float)
    r=rets[tickers].dropna(how="any")
    if r.empty: return pd.Series(dtype=float)
    fd=fee/TRADING_DAYS; idx=r.index; R=r.values
    w=W.copy(); eq=np.zeros(len(idx))
    eq[0]=1.0*(1-fd)*(1+(w*R[0]).sum())
    for i in range(1,len(idx)):
        w=w*(1+R[i-1]); s=w.sum(); w=w/s if s else W.copy()
        if rebalance.lower()=="annual" and idx[i-1].year!=idx[i].year: w=W.copy()
        eq[i]=eq[i-1]*(1-fd)*(1+(w*R[i]).sum())
    return pd.Series(eq,index=idx,name="Portfolio")

def _bench_equity(rets_all, defn):
    t=defn.get("type")
    if t=="single":
        tk=defn["ticker"]
        if tk not in rets_all.columns: return pd.Series(dtype=float)
        r=rets_all[[tk]].dropna(how="any")
        return (1+r[tk]).cumprod().rename(tk) if not r.empty else pd.Series(dtype=float)
    elif t=="mix":
        w=defn["weights"]; cols=[c for c in rets_all.columns if c in w]
        if not cols: return pd.Series(dtype=float)
        r=rets_all[cols].dropna(how="any")
        if r.empty: return pd.Series(dtype=float)
        wv=np.array([w[c] for c in cols]); wv/=wv.sum()
        return ((1+r).dot(wv)).cumprod().rename("mix")
    return pd.Series(dtype=float)

def _kpis(eq, start_amt, d0, d1, rf=0.0):
    if eq.empty or len(eq)<2: return None
    daily=eq.pct_change(fill_method=None).dropna()
    yrs=_years(d0,d1)
    total=float(eq.iloc[-1]/eq.iloc[0]-1)
    cagr=(float(eq.iloc[-1]/eq.iloc[0]))**(1/yrs)-1 if yrs>0 else np.nan
    vol=float(daily.std()*math.sqrt(TRADING_DAYS)) if len(daily)>1 else np.nan
    rf_d=rf/TRADING_DAYS
    sharpe=float(((daily.mean()-rf_d)/daily.std())*math.sqrt(TRADING_DAYS)) if daily.std()>0 else np.nan
    return {"fv":start_amt*float(eq.iloc[-1]),"ret":total,"cagr":cagr,"vol":vol,"sharpe":sharpe}

def _perc(x):
    try: return f"{x*100:.2f}%"
    except: return "—"
def _money(x,c="USD"):
    sym="$" if c=="USD" else "₹"
    try: return f"{sym}{x:,.0f}"
    except: return f"{sym}{x}"

# ── Ticker tape (shared small cached list — never the full ALLOWLIST) ──
live_ticker_tape()

page_header("Fund Backtester", "Historical simulation · Institutional risk metrics", badge="LIVE DATA")

# ── Front-page configuration ──────────────────────────────────────────
section_header("Backtest Control Center")

today = date.today()
default_start = today - timedelta(days=365 * 10)

st.markdown(
    """
    <div style="
      background:linear-gradient(135deg, rgba(36,87,197,.14), rgba(14,159,110,.06));
      border:1px solid var(--border);
      border-radius:14px;
      padding:14px 16px;
      margin-bottom:12px;
      color:var(--text-2);
      font-size:.86rem;
      line-height:1.6;">
      Configure your strategy here, then run the backtest from this panel.
      No sidebar setup needed.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("bt_front_config"):
    c1, c2, c3 = st.columns([1.25, 1.05, 1.15])

    with c1:
        st.markdown("**Strategy & Benchmarks**")
        fund_id = st.selectbox(
            "Fund",
            list(FUNDS.keys()),
            format_func=lambda k: f"{k} — {FUNDS[k]['name']}",
        )
        bench_sel = st.multiselect(
            "Benchmarks (max 3)",
            list(BENCHMARKS.keys()),
            default=["SPY", "60/40", "GLD"],
            max_selections=3,
        )
        fmeta = FUNDS[fund_id]
        st.markdown(
            f'<div style="margin-top:8px;padding:10px 12px;background:var(--bg-card);'
            f'border:1px solid var(--border);border-radius:10px;font-size:.8rem;color:var(--text-2);">'
            f'<b style="color:var(--text);">{fmeta["name"]}</b><br>'
            f'Risk Level: <span style="color:var(--accent);font-family:var(--mono);">{fmeta["risk"]}/5</span> · '
            f'Holdings: <span style="color:var(--text);font-family:var(--mono);">{len(fmeta["allocations"])}</span> · '
            f'Default TER: <span style="color:var(--text);font-family:var(--mono);">{fmeta["default_fee"]:.2%}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("**Date Window**")
        start_date = st.date_input("Start Date", value=default_start, max_value=today)
        end_date = st.date_input("End Date", value=today, max_value=today)
        rebalance = st.selectbox("Rebalance", ["Annual", "None"], index=0)

    with c3:
        st.markdown("**Capital & Risk Inputs**")
        start_amount = st.number_input("Starting Amount ($)", min_value=1000.0, value=100000.0, step=5000.0)
        currency = st.selectbox("Currency", ["USD", "INR"], index=0)
        fee_on = st.checkbox("Apply annual fee (TER)", value=True)
        fee_val = st.number_input(
            "Annual fee",
            min_value=0.0,
            max_value=0.05,
            value=float(FUNDS[fund_id]["default_fee"]),
            step=0.0005,
            format="%.4f",
            disabled=not fee_on,
        )
        rf_rate = st.number_input(
            "Risk-free rate (Sharpe/Sortino)",
            min_value=0.0,
            max_value=0.15,
            value=0.04,
            step=0.005,
            format="%.3f",
        )

    a1, a2 = st.columns([1.8, 1.0])
    with a1:
        run = st.form_submit_button("▶ Run Backtest", type="primary", use_container_width=True)
    with a2:
        clear_cache = st.form_submit_button("Clear Cache", use_container_width=True)

if isinstance(start_date, tuple):
    start_date = start_date[0]
if isinstance(end_date, tuple):
    end_date = end_date[0]

end_date = _clamp(end_date)
if clear_cache:
    st.cache_data.clear()
    st.success("Data cache cleared.")

if start_date >= end_date:
    st.error("Start date must be before end date.")
    run = False

# ── Main ──────────────────────────────────────────────────────────────
if run:
    with st.spinner("Fetching prices and computing metrics…"):
        target_w=FUNDS[fund_id]["allocations"].copy()
        fund_tickers=set(target_w.keys())
        bench_tickers={d["def"]["ticker"] if d["def"]["type"]=="single" else None for b in bench_sel for _,d in [("",BENCHMARKS[b])] }
        bench_tickers.discard(None)
        for b in bench_sel:
            if BENCHMARKS[b]["def"]["type"]=="mix":
                bench_tickers.update(BENCHMARKS[b]["def"]["weights"].keys())
        needed=sorted(fund_tickers|bench_tickers)
        prices=_fetch(tuple(needed),start_date,end_date)
        if prices.empty: st.error("No data returned."); st.stop()

        present=[t for t in fund_tickers if t in prices.columns]
        missing=sorted(fund_tickers-set(present))
        if missing: st.warning(f"Dropped (no data, weights renormalized): {missing}")
        weights=_renorm(target_w,present)
        if not weights: st.error("No fund tickers have data."); st.stop()

        rets_all=prices.pct_change(fill_method=None)
        r_port=rets_all[present].dropna(how="any")
        if r_port.empty or len(r_port)<2: st.error("Insufficient overlapping data."); st.stop()

        fee=float(fee_val) if fee_on else 0.0
        eq=_portfolio_path(r_port,weights,rebalance=rebalance,fee=fee)
        if eq.empty: st.error("Empty equity series."); st.stop()

        eq=eq/eq.iloc[0]
        d0,d1=eq.index[0].date(),eq.index[-1].date()
        yrs=_years(d0,d1)
        kpi=_kpis(eq,float(start_amount),d0,d1,rf=rf_rate)

        # ── Enhanced metrics ─────────────────────────────────────────
        mdd=max_drawdown(eq)
        sort=sortino_ratio(eq,rf_annual=rf_rate)
        calm=calmar_ratio(eq,yrs)

        # Beta & Alpha vs first benchmark
        beta_val=alpha_val=np.nan
        if bench_sel:
            spy_eq=_bench_equity(rets_all,BENCHMARKS[bench_sel[0]]["def"])
            if not spy_eq.empty:
                spy_eq=spy_eq.reindex(eq.index).ffill().dropna()
                if not spy_eq.empty:
                    spy_eq=spy_eq/spy_eq.iloc[0]
                    beta_val,alpha_val=compute_beta_alpha(
                        eq.pct_change(fill_method=None).dropna(),
                        spy_eq.pct_change(fill_method=None).dropna(),
                        rf_annual=rf_rate,
                    )

        monthly=eq.resample("ME").last().pct_change(fill_method=None).dropna()
        pct_pos=(monthly>0).mean() if not monthly.empty else np.nan

        # ── KPI strip ─────────────────────────────────────────────────
        section_header("Performance Summary")
        kpi_row([
            {"label":"Final Value",      "value":_money(kpi["fv"],currency),          "delta":None},
            {"label":"Total Return",     "value":_perc(kpi["ret"]),                   "delta":None,
             "delta_dir":"up" if kpi["ret"]>=0 else "dn"},
            {"label":"CAGR",             "value":_perc(kpi["cagr"]) if np.isfinite(kpi["cagr"]) else "—", "delta":None},
            {"label":"Sharpe Ratio",     "value":f"{kpi['sharpe']:.2f}" if np.isfinite(kpi['sharpe']) else "—", "delta":None},
            {"label":"Sortino Ratio",    "value":f"{sort:.2f}"  if np.isfinite(sort)  else "—", "delta":None},
            {"label":"Calmar Ratio",     "value":f"{calm:.2f}"  if np.isfinite(calm)  else "—", "delta":None},
            {"label":"Max Drawdown",     "value":f"{mdd*100:.1f}%", "delta":None, "delta_dir":"dn"},
            {"label":"Beta",             "value":f"{beta_val:.2f}"  if np.isfinite(beta_val)  else "—", "delta":None},
            {"label":"Alpha (ann.)",     "value":_perc(alpha_val) if np.isfinite(alpha_val) else "—",
             "delta":None, "delta_dir":"up" if (alpha_val or 0)>=0 else "dn"},
            {"label":"% Positive Months","value":_perc(pct_pos) if np.isfinite(pct_pos) else "—", "delta":None},
        ])

        # ── Build benchmark equity series ─────────────────────────────
        bench_series=[]
        for b in bench_sel:
            bs=_bench_equity(rets_all,BENCHMARKS[b]["def"])
            if not bs.empty:
                bs=bs.reindex(eq.index).ffill().dropna()
                if not bs.empty:
                    bs=bs/bs.iloc[0]; bs.name=BENCHMARKS[b]["name"]; bench_series.append(bs)

        # ── Equity curve ──────────────────────────────────────────────
        section_header("Equity Curve")
        df_plot=pd.DataFrame({"Portfolio":eq})
        for s in bench_series: df_plot[s.name]=s.reindex(df_plot.index,method="ffill")

        fig_eq=go.Figure()
        palette=["#2457C5","#0E9F6E","#C77700","#E02749","#A78BFA"]
        for i,col in enumerate(df_plot.columns):
            fig_eq.add_trace(go.Scatter(
                x=df_plot.index, y=df_plot[col], mode="lines", name=col,
                line=dict(color=palette[i%len(palette)],
                          width=3 if col=="Portfolio" else 1.5,
                          dash="solid" if col=="Portfolio" else "dot"),
            ))
        layout=dict(**CHART_LAYOUT); layout.update(height=420,margin=dict(l=55,r=20,t=30,b=40))
        fig_eq.update_layout(**layout)
        fig_eq.update_yaxes(title_text="Growth (×1 at start)")
        st.plotly_chart(fig_eq,width='stretch')

        # ── Drawdown chart ────────────────────────────────────────────
        section_header("Drawdown")
        dd=drawdown_series(eq)*100
        fig_dd=go.Figure(go.Scatter(x=dd.index,y=dd,fill="tozeroy",
            fillcolor="rgba(224,39,73,.12)",line=dict(color="#E02749",width=1.5),name="Drawdown"))
        layout=dict(**CHART_LAYOUT); layout.update(height=220,margin=dict(l=55,r=20,t=20,b=40))
        fig_dd.update_layout(**layout)
        fig_dd.update_yaxes(title_text="Drawdown (%)")
        st.plotly_chart(fig_dd,width='stretch')

        # ── Analytics tabs ────────────────────────────────────────────
        t1,t2,t3,t4=st.tabs(["Rolling 12-month","Yearly Returns","Distribution & VaR","Capture Ratios"])

        with t1:
            roll=(eq/eq.shift(TRADING_DAYS)-1)*100
            roll=roll.dropna()
            if not roll.empty:
                fig_r=go.Figure(go.Scatter(x=roll.index,y=roll,fill="tozeroy",
                    fillcolor="rgba(36,87,197,.08)",line=dict(color="#2457C5",width=1.5)))
                fig_r.add_hline(y=0,line_color="#C9C2B4",line_width=1)
                layout=dict(**CHART_LAYOUT); layout.update(height=320,margin=dict(l=55,r=20,t=20,b=40))
                fig_r.update_layout(**layout); fig_r.update_yaxes(title_text="Trailing 12M Return (%)")
                st.plotly_chart(fig_r,width='stretch')

        with t2:
            yr_eq=eq.resample("YE").last(); yr=yr_eq.pct_change(fill_method=None).dropna()
            yr.index=yr.index.year
            if not yr.empty:
                colors=["#0E9F6E" if v>=0 else "#E02749" for v in yr]
                fig_y=go.Figure(go.Bar(x=yr.index,y=yr*100,marker_color=colors))
                fig_y.add_hline(y=0,line_color="#C9C2B4",line_width=1)
                layout=dict(**CHART_LAYOUT); layout.update(height=320,margin=dict(l=55,r=20,t=20,b=40))
                fig_y.update_layout(**layout); fig_y.update_yaxes(title_text="Annual Return (%)")
                st.plotly_chart(fig_y,width='stretch')

        with t3:
            if not monthly.empty:
                var95=float(np.percentile(monthly,5))
                cvar95=float(monthly[monthly<=var95].mean()) if (monthly<=var95).any() else var95
                fig_d=go.Figure(go.Histogram(x=monthly*100,nbinsx=30,
                    marker_color="#2457C5",opacity=0.7))
                fig_d.add_vline(x=var95*100,line_dash="dash",line_color="#E02749",
                    annotation_text=f"VaR 95%: {var95*100:.1f}%")
                layout=dict(**CHART_LAYOUT); layout.update(height=320,margin=dict(l=55,r=20,t=30,b=40))
                fig_d.update_layout(**layout); fig_d.update_xaxes(title_text="Monthly Return (%)")
                st.plotly_chart(fig_d,width='stretch')
                k1,k2,k3,k4=st.columns(4)
                k1.metric("VaR 95%",   f"{var95*100:.2f}%")
                k2.metric("CVaR 95%",  f"{cvar95*100:.2f}%")
                k3.metric("Avg Month", f"{float(monthly.mean())*100:.2f}%")
                k4.metric("Volatility (ann.)", _perc(kpi["vol"]))

        with t4:
            if bench_sel:
                primary=BENCHMARKS[bench_sel[0]]
                b_eq=_bench_equity(rets_all,primary["def"])
                if not b_eq.empty:
                    b_eq=b_eq.reindex(eq.index).ffill().dropna()
                    if not b_eq.empty:
                        b_eq=b_eq/b_eq.iloc[0]
                        pm=eq.resample("ME").last().pct_change(fill_method=None).dropna()
                        bm=b_eq.resample("ME").last().pct_change(fill_method=None).dropna()
                        pair=pd.concat([pm.rename("fund"),bm.rename("bench")],axis=1).dropna()
                        up=pair[pair["bench"]>0]; dn=pair[pair["bench"]<0]
                        uc=float(up["fund"].mean()/up["bench"].mean()) if not up.empty else np.nan
                        dc=float(dn["fund"].mean()/dn["bench"].mean()) if not dn.empty else np.nan
                        c1,c2=st.columns(2)
                        c1.metric(f"Upside Capture vs {primary['name']}",
                                  _perc(uc) if np.isfinite(uc) else "—")
                        c2.metric(f"Downside Capture vs {primary['name']}",
                                  _perc(dc) if np.isfinite(dc) else "—")

        # ── Download ──────────────────────────────────────────────────
        section_header("Export")
        out=pd.DataFrame({"equity":eq}); out.index.name="date"
        st.download_button("Download Daily Equity CSV",
                           out.to_csv().encode(),
                           f"{fund_id}_equity_{d0}_{d1}.csv","text/csv")

        section_header("Assumptions")
        st.markdown(
            f"- **Fund:** {FUNDS[fund_id]['name']}  \n"
            f"- **Window:** {d0} → {d1} ({yrs:.1f} years)  \n"
            f"- **Rebalance:** {rebalance} · **Fee:** {fee:.2%}  \n"
            f"- **Risk-free rate:** {rf_rate:.2%}  \n"
            f"- Prices via yfinance (auto-adjusted). Simulation assumes zero slippage."
        )

else:
    st.info("Set your inputs in the Backtest Control Center above, then click **Run Backtest**.")

disclaimer("Past performance is not indicative of future results. Zero slippage / commission assumed.")
