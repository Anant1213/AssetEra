"""
Risk Profiler — ML risk prediction + Monte Carlo portfolio simulation.

ML: Gradient Boosting (64% CV accuracy on 3,000 synthetic samples).
Simulation: Geometric Brownian Motion, 1,000 paths, fan-chart with confidence bands.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.ui import apply_styles, page_header, section_header, kpi_row, ticker_tape, disclaimer, CHART_LAYOUT
from backend.market import fetch_prices, compute_metrics, ALLOWLIST
from backend.risk_profiler.risk_model import (
    predict_risk, recommend_funds, get_trained_model,
    RISK_LABELS, FUND_PROFILES,
)
from backend.indicators import monte_carlo_gbm, mc_percentiles

st.set_page_config(page_title="Risk Profiler — AssetEra", page_icon="🎯", layout="wide")
apply_styles()

@st.cache_data(ttl=300, show_spinner=False)
def _tape():
    p, _ = fetch_prices(sorted(ALLOWLIST), period="5d", interval="1d")
    return compute_metrics(p)

ticker_tape(_tape())
page_header("Risk Profiler", "ML-predicted investor risk score · Monte Carlo portfolio simulation", badge="GBM · GBT MODEL")

# ── Input form ────────────────────────────────────────────────────────
section_header("Your Investor Profile")

c1, c2, c3 = st.columns(3)
with c1:
    age            = st.number_input("Age", 18, 85, 35, 1)
    annual_income  = st.number_input("Annual Income ($)", 20_000, 1_000_000, 85_000, 5_000)
    dependents     = st.selectbox("Dependents", [0, 1, 2, 3, 4, 5], index=1)
with c2:
    marital        = st.selectbox("Marital Status", ["single", "married", "divorced", "widowed"], index=1)
    employment     = st.selectbox("Employment", ["stable", "variable", "retired"], index=0)
    horizon        = st.slider("Investment Horizon (years)", 1, 35, 15)
with c3:
    loss_tol       = st.slider("Loss Tolerance — max annual loss %", 2, 55, 20,
                               help="How much % drop could you tolerate in a bad year before selling?")
    exp_opts       = [(0,"None — first time"),(1,"Beginner < 2 yrs"),(2,"Intermediate 2–7 yrs"),(3,"Advanced 7+ yrs")]
    experience     = st.selectbox("Investment Experience", exp_opts, format_func=lambda x: x[1], index=1)
    exp_val        = experience[0]

col_btn, _ = st.columns([1, 3])
with col_btn:
    predict_btn = st.button("Predict Risk Profile", type="primary")

# ── Prediction results ────────────────────────────────────────────────
if predict_btn:
    result = predict_risk(age, annual_income, dependents, marital,
                          horizon, loss_tol, exp_val, employment)
    st.session_state["user_risk_profile"] = result["risk_profile"]
    st.session_state["risk_result"] = result

result = st.session_state.get("risk_result")
if result:

    st.markdown("---")
    section_header("Risk Assessment")

    RISK_COLOR = {1:"#00C896", 2:"#84CC16", 3:"#FFB020", 4:"#F97316", 5:"#FF3560"}
    color = RISK_COLOR.get(result["risk_profile"], "#7A8BA0")

    score_col, prob_col = st.columns([1, 2])

    with score_col:
        st.markdown(
            f"""
            <div class="ae-risk-card"
                 style="border-color:{color}; box-shadow:0 0 40px {color}22;">
              <div style="font-size:4.5rem;font-weight:800;color:{color};line-height:1;font-family:var(--mono);">
                {result["risk_profile"]}
              </div>
              <div style="font-size:1.1rem;font-weight:700;color:{color};margin:.4rem 0;">
                {result["label"]}
              </div>
              <div style="font-size:.82rem;color:var(--text-2);">
                Model Confidence: {result["confidence"]:.0%}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with prob_col:
        probs = result["probabilities"]
        fig_p = go.Figure(go.Bar(
            x=[f"{k} — {RISK_LABELS[k]}" for k in sorted(probs)],
            y=[probs[k] * 100 for k in sorted(probs)],
            marker=dict(
                color=[probs[k] * 100 for k in sorted(probs)],
                colorscale=[[0,"#00C896"],[0.5,"#FFB020"],[1,"#FF3560"]],
                showscale=False,
            ),
            text=[f"{probs[k]*100:.1f}%" for k in sorted(probs)],
            textposition="outside",
        ))
        layout = dict(**CHART_LAYOUT)
        layout.update(height=280, margin=dict(l=20, r=20, t=30, b=60),
                      yaxis=dict(range=[0, 105], title="Probability (%)", gridcolor="#1A2840"))
        fig_p.update_layout(**layout, title="Prediction Probability by Risk Level")
        st.plotly_chart(fig_p, width='stretch')

    # ── Fund recommendations ──────────────────────────────────────────
    section_header("Recommended Funds")
    funds = recommend_funds(result["risk_profile"])

    for fund in funds:
        with st.expander(f"**{fund['id']}: {fund['name']}**  ·  {fund['description']}", expanded=True):
            info_col, chart_col = st.columns([1, 1])
            with info_col:
                st.markdown(f"**Expected Return:** {fund['expected_return']}")
                st.markdown(f"**Risk Range:** {fund['risk_range'][0]} – {fund['risk_range'][1]}")
                alloc_df = pd.DataFrame(
                    sorted(fund["allocations"].items(), key=lambda x: -x[1]),
                    columns=["Ticker", "Weight"],
                )
                alloc_df["Weight"] = alloc_df["Weight"].map("{:.1%}".format)
                st.dataframe(alloc_df, width='stretch', hide_index=True)
            with chart_col:
                allocs = fund["allocations"]
                major = {t: w for t, w in allocs.items() if w >= 0.03}
                others = sum(w for w in allocs.values() if w < 0.03)
                if others > 0:
                    major["Others"] = others
                fig_pie = go.Figure(go.Pie(
                    labels=list(major.keys()),
                    values=list(major.values()),
                    hole=0.45,
                    marker=dict(colors=["#2962FF","#00C896","#FFB020","#FF3560","#A78BFA",
                                        "#10B981","#F59E0B","#EC4899","#6366F1","#14B8A6"]),
                    textinfo="label+percent",
                    textfont=dict(size=11),
                ))
                layout = dict(**CHART_LAYOUT)
                layout.update(height=330, margin=dict(l=10, r=10, t=30, b=10),
                              showlegend=False)
                fig_pie.update_layout(**layout, title="Portfolio Composition")
                st.plotly_chart(fig_pie, width='stretch')

    # ── Monte Carlo simulation ────────────────────────────────────────
    st.markdown("---")
    section_header("Monte Carlo Portfolio Simulation (GBM)")
    st.markdown(
        '<div style="font-size:.84rem;color:var(--text-2);margin-bottom:1rem;">'
        "Geometric Brownian Motion: simulates 1,000 portfolio paths using Itô's drift correction. "
        "Confidence bands show 5th–95th percentile outcomes."
        "</div>",
        unsafe_allow_html=True,
    )

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        mc_initial = st.number_input("Initial Investment ($)", 10_000, 10_000_000, 100_000, 10_000)
        mc_years   = st.slider("Simulation Horizon (years)", 1, 30, horizon)
    with mc2:
        # Suggest return/vol from selected fund's risk profile
        risk_lvl = result["risk_profile"]
        default_ret = {1: 5.0, 2: 8.0, 3: 11.0, 4: 15.0, 5: 20.0}.get(risk_lvl, 10.0)
        default_vol = {1: 8.0, 2: 12.0, 3: 16.0, 4: 22.0, 5: 30.0}.get(risk_lvl, 15.0)
        mc_ret = st.slider("Expected Annual Return (%)", 1.0, 30.0, float(default_ret), 0.5)
        mc_vol = st.slider("Annual Volatility (%)", 2.0, 50.0, float(default_vol), 0.5)
    with mc3:
        mc_goal     = st.number_input("Goal Amount ($)", 10_000, 50_000_000, int(mc_initial * 3), 50_000)
        n_sims      = st.select_slider("Simulations", [200, 500, 1000, 2000], value=1000)

    run_mc = st.button("Run Monte Carlo Simulation", type="primary")

    if run_mc or st.session_state.get("mc_ran"):
        st.session_state["mc_ran"] = True
        with st.spinner(f"Running {n_sims:,} GBM paths × {mc_years} years…"):
            paths = monte_carlo_gbm(
                initial=mc_initial,
                annual_return=mc_ret / 100,
                annual_vol=mc_vol / 100,
                n_years=mc_years,
                n_sims=n_sims,
            )
            pcts = mc_percentiles(paths)
            final = paths[:, -1]

            # x-axis in years
            xs = np.linspace(0, mc_years, paths.shape[1])

            # ── Fan chart ─────────────────────────────────────────────
            fig_mc = go.Figure()

            # 95/5 band
            fig_mc.add_trace(go.Scatter(
                x=np.concatenate([xs, xs[::-1]]),
                y=np.concatenate([pcts["p95"], pcts["p5"][::-1]]),
                fill="toself", fillcolor="rgba(41,98,255,.07)",
                line=dict(color="rgba(0,0,0,0)"), name="5–95th pct", showlegend=True,
            ))
            # 75/25 band
            fig_mc.add_trace(go.Scatter(
                x=np.concatenate([xs, xs[::-1]]),
                y=np.concatenate([pcts["p75"], pcts["p25"][::-1]]),
                fill="toself", fillcolor="rgba(41,98,255,.14)",
                line=dict(color="rgba(0,0,0,0)"), name="25–75th pct", showlegend=True,
            ))
            # Percentile lines
            for pct_key, col, lbl, dash, wd in [
                ("p95", "rgba(41,98,255,.5)",  "95th",  "dot",   1.2),
                ("p75", "rgba(41,98,255,.7)",  "75th",  "dot",   1.2),
                ("p50", "#2962FF",              "Median","solid", 2.5),
                ("p25", "rgba(255,176,32,.7)", "25th",  "dot",   1.2),
                ("p5",  "rgba(255,53,96,.5)",  "5th",   "dot",   1.2),
            ]:
                fig_mc.add_trace(go.Scatter(
                    x=xs, y=pcts[pct_key], mode="lines", name=lbl,
                    line=dict(color=col, width=wd, dash=dash),
                ))
            # Initial investment line
            fig_mc.add_hline(y=mc_initial, line_dash="dash",
                             line_color="rgba(122,139,160,.4)", line_width=1,
                             annotation_text="Initial", annotation_position="right")
            # Goal line
            fig_mc.add_hline(y=mc_goal, line_dash="dash",
                             line_color="#FFB020", line_width=1.5,
                             annotation_text=f"Goal ${mc_goal:,.0f}", annotation_position="right")

            layout = dict(**CHART_LAYOUT)
            layout.update(height=460, margin=dict(l=70, r=80, t=40, b=50),
                          yaxis=dict(title="Portfolio Value ($)", tickprefix="$", gridcolor="#1A2840"),
                          xaxis=dict(title="Years", gridcolor="#1A2840"),
                          legend=dict(orientation="h", y=-0.15))
            fig_mc.update_layout(**layout, title=f"Monte Carlo Simulation — {n_sims:,} Paths ({mc_years}y horizon)")
            st.plotly_chart(fig_mc, width='stretch')

            # ── Outcome KPIs ──────────────────────────────────────────
            goal_prob = float((final >= mc_goal).mean())
            double_prob = float((final >= mc_initial * 2).mean())
            kpi_row([
                {"label": "Median Outcome",      "value": f"${np.median(final):,.0f}",          "delta": None},
                {"label": "95th Percentile",     "value": f"${np.percentile(final,95):,.0f}",   "delta": None},
                {"label": "5th Percentile",      "value": f"${np.percentile(final,5):,.0f}",    "delta": None},
                {"label": "Prob. of Goal",        "value": f"{goal_prob:.1%}",
                 "delta": "Above target" if goal_prob >= 0.5 else "Below 50%",
                 "delta_dir": "up" if goal_prob >= 0.5 else "dn"},
                {"label": "Prob. of Doubling",   "value": f"{double_prob:.1%}", "delta": None},
                {"label": "Expected CAGR (input)","value": f"{mc_ret:.1f}%", "delta": None},
            ])

            # ── Distribution of final values ──────────────────────────
            section_header("Distribution of Final Portfolio Values")
            fig_hist = go.Figure(go.Histogram(
                x=final, nbinsx=60,
                marker=dict(color="#2962FF", opacity=0.75),
                name="Final Value",
            ))
            fig_hist.add_vline(x=mc_goal, line_dash="dash", line_color="#FFB020",
                               annotation_text="Goal", line_width=2)
            fig_hist.add_vline(x=np.median(final), line_dash="dash", line_color="#00C896",
                               annotation_text="Median", line_width=2)
            layout = dict(**CHART_LAYOUT)
            layout.update(height=300, margin=dict(l=55, r=20, t=30, b=40),
                          xaxis=dict(title="Final Value ($)", tickprefix="$"))
            fig_hist.update_layout(**layout)
            st.plotly_chart(fig_hist, width='stretch')

    # ── Model explainability ──────────────────────────────────────────
    st.markdown("---")
    section_header("Model Explainability")
    _, accuracy, importances = get_trained_model()

    e1, e2 = st.columns([1, 2])
    with e1:
        kpi_row([
            {"label": "Algorithm",          "value": "Gradient Boosting",  "delta": None},
            {"label": "CV Accuracy (5-fold)","value": f"{accuracy:.1%}",    "delta": None},
            {"label": "Training Samples",   "value": "3,000",              "delta": None},
            {"label": "Features",           "value": "8",                  "delta": None},
        ])
    with e2:
        imp = importances.reset_index(); imp.columns = ["Feature", "Importance"]
        fig_imp = go.Figure(go.Bar(
            x=imp["Importance"][::-1], y=imp["Feature"][::-1],
            orientation="h",
            marker=dict(color=imp["Importance"][::-1],
                        colorscale=[[0,"#1A2840"],[1,"#2962FF"]]),
            text=[f"{v:.3f}" for v in imp["Importance"][::-1]],
            textposition="outside",
        ))
        layout = dict(**CHART_LAYOUT)
        layout.update(height=310, margin=dict(l=20, r=60, t=30, b=20),
                      xaxis=dict(title="Importance Score", gridcolor="#1A2840"))
        fig_imp.update_layout(**layout, title="Feature Importances")
        st.plotly_chart(fig_imp, width='stretch')

    st.caption(
        "Model trained on synthetic data based on financial planning heuristics. "
        "In production, trained on real Snowflake customer data. "
        "Monte Carlo uses Geometric Brownian Motion with Itô's correction."
    )

disclaimer("Risk scores are model predictions, not financial advice. Monte Carlo results are probabilistic projections.")
