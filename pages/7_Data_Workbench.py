"""
Data Workbench — Upload, profile, explore and query any structured dataset.
"""
from __future__ import annotations
import json
import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from backend.ui import apply_styles, page_header, section_header, CHART_LAYOUT

st.set_page_config(page_title="Data Workbench — AssetEra", page_icon="🧠", layout="wide")
apply_styles()

# ═══════════════════════════════════════════════════════════════
# GLOBAL CSS
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── KPI strip ───────────────────────────────────── */
.dw-kpi-strip { display:flex; flex-wrap:wrap; gap:12px; margin:1rem 0; }
.dw-kpi-card {
  flex:1 1 140px; min-width:130px;
  background:linear-gradient(135deg,var(--bg-card) 0%,rgba(41,98,255,.04) 100%);
  border:1px solid var(--border); border-radius:var(--r-lg);
  padding:.9rem 1.1rem; position:relative; overflow:hidden;
}
.dw-kpi-card::before {
  content:''; position:absolute; top:0; left:0; width:3px; height:100%;
  background:var(--kpi-accent, var(--accent));
}
.dw-kpi-label { font-size:.62rem; color:var(--text-2); text-transform:uppercase;
  letter-spacing:.08em; margin-bottom:.35rem; }
.dw-kpi-value { font-size:1.3rem; font-weight:800; font-family:var(--mono);
  color:var(--text); line-height:1; }
.dw-kpi-sub { font-size:.7rem; color:var(--text-2); margin-top:.3rem; }

/* ── Score ring ──────────────────────────────────── */
.score-ring-wrap { text-align:center; padding:1rem 0; }
.score-big { font-size:3.5rem; font-weight:900; font-family:var(--mono); line-height:1; }
.score-label { font-size:.78rem; color:var(--text-2); text-transform:uppercase;
  letter-spacing:.08em; margin-top:.4rem; }

/* ── Issue cards ─────────────────────────────────── */
.issue-high    { border-left:4px solid #FF3560; padding:8px 12px;
  background:rgba(255,53,96,.07); border-radius:0 8px 8px 0; margin:5px 0; font-size:.84rem; }
.issue-warning { border-left:4px solid #FFB020; padding:8px 12px;
  background:rgba(255,176,32,.07); border-radius:0 8px 8px 0; margin:5px 0; font-size:.84rem; }
.issue-info    { border-left:4px solid #2962FF; padding:8px 12px;
  background:rgba(41,98,255,.07); border-radius:0 8px 8px 0; margin:5px 0; font-size:.84rem; }

/* ── AI badge ────────────────────────────────────── */
.ai-badge { display:inline-block; font-size:.58rem; font-weight:700;
  color:var(--accent); border:1px solid var(--accent); border-radius:10px;
  padding:1px 6px; margin-left:6px; text-transform:uppercase; letter-spacing:.06em; }

/* ── SQL box ─────────────────────────────────────── */
.sql-box { font-family:var(--mono); font-size:.8rem;
  background:var(--bg-overlay); color:#00C896;
  border:1px solid var(--border); border-radius:var(--r-md);
  padding:.8rem 1rem; margin:.5rem 0; overflow-x:auto; white-space:pre-wrap; }

/* ── Chart card wrapper ──────────────────────────── */
.chart-card {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:1rem; margin-bottom:1rem;
  transition: border-color .2s, box-shadow .2s;
}
.chart-card:hover { border-color:rgba(41,98,255,.4); box-shadow:0 4px 24px rgba(41,98,255,.08); }
.chart-title { font-size:.82rem; font-weight:700; color:var(--text-2);
  text-transform:uppercase; letter-spacing:.06em; margin-bottom:.5rem; }
.chart-expl { font-size:.76rem; color:var(--text-2); margin-bottom:.6rem; line-height:1.5; }

/* ── Selector bar ────────────────────────────────── */
.sel-bar {
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:.9rem 1.2rem; margin-bottom:.9rem;
}

/* ── Upload zone ─────────────────────────────────── */
.upload-hint {
  background:linear-gradient(135deg,rgba(41,98,255,.06) 0%,rgba(0,200,150,.04) 100%);
  border:1.5px dashed rgba(41,98,255,.35); border-radius:var(--r-lg);
  padding:1.4rem 1.6rem; margin-bottom:1rem; text-align:center;
}
.upload-hint p { color:var(--text-2); font-size:.86rem; margin:.3rem 0; }

/* ── Data preview table ──────────────────────────── */
.preview-label { font-size:.7rem; color:var(--text-2); text-transform:uppercase;
  letter-spacing:.07em; margin:.4rem 0 .3rem; }
</style>
""", unsafe_allow_html=True)

page_header("Data Workbench", "Upload · Profile · Explore · Ask", badge="BETA")


# ═══════════════════════════════════════════════════════════════
# STORE IMPORTS
# ═══════════════════════════════════════════════════════════════
from backend.data_workbench.store import (
    create_project, list_projects, get_project,
    create_dataset, list_datasets, get_dataset, delete_dataset,
    get_profile, list_views, list_columns,
)

# ═══════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════
for _k in ("project_id", "dataset_id", "profile", "quality", "views", "llm"):
    if _k not in st.session_state:
        st.session_state[_k] = None

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
_PALETTE = ["#2962FF","#00C896","#FFB020","#FF3560","#A78BFA",
            "#10B981","#F59E0B","#EC4899","#6366F1","#14B8A6",
            "#F97316","#06B6D4","#84CC16"]

def _cl(n: int) -> str:
    return _PALETTE[n % len(_PALETTE)]

def _lyt(h=340, title="", **kw) -> dict:
    d = dict(CHART_LAYOUT)
    d.update(height=h, title=title, margin=dict(l=50,r=20,t=40,b=40))
    d.update(kw)
    return d

def _kpi(label: str, value: str, sub: str = "", accent: str = "var(--accent)") -> str:
    return (
        f'<div class="dw-kpi-card" style="--kpi-accent:{accent};">'
        f'<div class="dw-kpi-label">{label}</div>'
        f'<div class="dw-kpi-value">{value}</div>'
        f'{"<div class=dw-kpi-sub>" + sub + "</div>" if sub else ""}'
        f'</div>'
    )

def _issue_html(issue: dict) -> str:
    sev = issue.get("severity", "info").lower()
    icon = {"high":"🔴","warning":"🟡","info":"🔵"}.get(sev,"•")
    return f'<div class="issue-{sev}">{icon} {issue.get("message","")}</div>'

# ═══════════════════════════════════════════════════════════════
# _render_chart  — MUST be defined before tab_views block
# ═══════════════════════════════════════════════════════════════
def _render_chart(spec: dict, df: pd.DataFrame, profile: dict) -> go.Figure | None:
    ct    = spec.get("chart_type", "bar")
    x     = spec.get("x_col")
    y     = spec.get("y_col")
    cc    = spec.get("color_col")
    title = spec.get("title", "")
    lyt   = _lyt(360, title)

    if ct == "kpi":
        return None   # handled in overview

    # Missingness
    if ct == "missingness":
        data = [(c["column_name"], round(c.get("null_pct", 0) * 100, 2))
                for c in profile.get("columns", []) if c.get("null_pct", 0) > 0]
        if not data:
            return None
        ndf = pd.DataFrame(data, columns=["col", "pct"]).sort_values("pct", ascending=True)
        colors = ["#FF3560" if v > 50 else ("#FFB020" if v > 20 else "#2962FF") for v in ndf["pct"]]
        fig = go.Figure(go.Bar(x=ndf["pct"], y=ndf["col"], orientation="h",
                               marker_color=colors, opacity=0.85))
        lyt["height"] = max(220, len(ndf) * 28 + 80)
        fig.update_layout(**lyt)
        fig.update_xaxes(title="Missing %")
        return fig

    # Histogram
    if ct == "histogram" and x and x in df.columns:
        s = pd.to_numeric(df[x], errors="coerce").dropna()
        if s.empty:
            return None
        fig = go.Figure(go.Histogram(
            x=s, nbinsx=40,
            marker=dict(color="#2962FF", opacity=0.85,
                        line=dict(color="rgba(41,98,255,.3)", width=0.5)),
        ))
        fig.update_layout(**lyt)
        fig.update_xaxes(title=x)
        fig.update_yaxes(title="Count")
        return fig

    # Bar (categorical counts or aggregation)
    if ct == "bar" and x and x in df.columns:
        if not y or y == "count" or y not in df.columns:
            vc = df[x].value_counts().head(15).reset_index()
            vc.columns = [x, "count"]
            colors = [_cl(i) for i in range(len(vc))]
            fig = go.Figure(go.Bar(x=vc[x], y=vc["count"],
                                   marker_color=colors, opacity=0.85))
            fig.update_layout(**lyt)
            fig.update_yaxes(title="Count")
        else:
            agg  = spec.get("aggregate", "mean")
            col_y = f"{agg}_{y}"
            grp  = df.groupby(x)[y].agg(agg).reset_index().rename(columns={y: col_y}).head(15)
            grp  = grp.sort_values(col_y, ascending=False)
            colors = [_cl(i) for i in range(len(grp))]
            fig = go.Figure(go.Bar(x=grp[x], y=grp[col_y],
                                   marker_color=colors, opacity=0.85))
            fig.update_layout(**lyt)
            fig.update_yaxes(title=col_y)
        return fig

    # Line / rolling line
    if ct in ("line", "rolling_line") and x and y and x in df.columns and y in df.columns:
        dfc = df[[x, y]].copy()
        try:
            dfc[x] = pd.to_datetime(dfc[x], errors="coerce")
            dfc = dfc.dropna().sort_values(x)
        except Exception:
            pass
        dfc[y] = pd.to_numeric(dfc[y], errors="coerce")
        fig = go.Figure()
        if ct == "rolling_line":
            w = spec.get("window", 7)
            dfc[f"roll_{w}"] = dfc[y].rolling(w, min_periods=1).mean()
            fig.add_trace(go.Scatter(x=dfc[x], y=dfc[y], name=y,
                                     line=dict(color="rgba(41,98,255,.35)", width=1)))
            fig.add_trace(go.Scatter(x=dfc[x], y=dfc[f"roll_{w}"],
                                     name=f"{w}-period MA",
                                     line=dict(color="#00C896", width=2.2)))
        else:
            fig.add_trace(go.Scatter(x=dfc[x], y=dfc[y], name=y,
                                     fill="tozeroy",
                                     fillcolor="rgba(41,98,255,.06)",
                                     line=dict(color="#2962FF", width=2)))
        fig.update_layout(**lyt)
        return fig

    # Heatmap (correlations)
    if ct == "heatmap":
        cols = spec.get("columns", profile.get("numeric_columns", []))[:14]
        cols = [c for c in cols if c in df.columns]
        if len(cols) < 2:
            return None
        corr = df[cols].apply(pd.to_numeric, errors="coerce").corr().round(2)
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.index,
            colorscale=[[0,"#FF3560"],[0.5,"#0A1220"],[1,"#00C896"]],
            zmid=0, zmin=-1, zmax=1,
            text=corr.values, texttemplate="%{text:.2f}",
            textfont=dict(size=9),
        ))
        lyt["height"] = max(340, len(cols) * 36 + 80)
        fig.update_layout(**lyt)
        return fig

    # Scatter
    if ct == "scatter" and x and y and x in df.columns and y in df.columns:
        dfc = df.sample(min(2000, len(df)), random_state=42)
        kw  = dict(x=x, y=y)
        if cc and cc in dfc.columns:
            kw["color"] = cc
        fig = px.scatter(dfc, **kw, opacity=0.6,
                         color_discrete_sequence=_PALETTE)
        fig.update_layout(**lyt)
        return fig

    # Box
    if ct == "box" and y and y in df.columns:
        dfc = df.copy()
        dfc[y] = pd.to_numeric(dfc[y], errors="coerce")
        if x and x in dfc.columns:
            cats = dfc[x].value_counts().head(10).index.tolist()
            dfc  = dfc[dfc[x].isin(cats)]
            fig  = px.box(dfc, x=x, y=y, color=x,
                          color_discrete_sequence=_PALETTE)
        else:
            fig = px.box(dfc, y=y, color_discrete_sequence=["#2962FF"])
        fig.update_layout(**lyt)
        return fig

    # Pie / donut
    if ct in ("pie", "donut") and x and x in df.columns:
        vc = df[x].value_counts().head(10)
        fig = go.Figure(go.Pie(
            labels=vc.index, values=vc.values,
            hole=0.45 if ct == "donut" else 0,
            marker=dict(colors=_PALETTE),
            textinfo="label+percent",
            textfont=dict(size=11),
        ))
        fig.update_layout(**lyt)
        return fig

    return None


# ═══════════════════════════════════════════════════════════════
# INLINE PROJECT / DATASET SELECTOR
# ═══════════════════════════════════════════════════════════════
projects = list_projects()

st.markdown('<div class="sel-bar">', unsafe_allow_html=True)
proj_l, proj_r = st.columns([3, 2])

with proj_l:
    st.markdown("**Project**")
    if projects:
        names = [p["name"] for p in projects]
        ids   = [p["id"]   for p in projects]
        idx   = ids.index(st.session_state["project_id"]) if st.session_state["project_id"] in ids else 0
        sel   = st.selectbox("Project", names, index=idx, key="sel_proj", label_visibility="collapsed")
        st.session_state["project_id"] = ids[names.index(sel)]
    else:
        st.markdown("<p style='color:var(--text-2);font-size:.88rem;margin:0;'>No projects — create one →</p>",
                    unsafe_allow_html=True)

with proj_r:
    with st.expander("＋  New project", expanded=not projects):
        np_name = st.text_input("Name", key="np_name", placeholder="My Analysis")
        np_desc = st.text_area("Description", key="np_desc", height=50)
        if st.button("Create", key="btn_create_proj", type="primary"):
            if np_name.strip():
                p = create_project(np_name.strip(), np_desc.strip())
                st.session_state["project_id"] = p["id"]
                st.rerun()
            else:
                st.error("Enter a name.")

st.markdown("</div>", unsafe_allow_html=True)

project_id = st.session_state["project_id"]

if project_id:
    datasets = list_datasets(project_id)
    if datasets:
        st.markdown('<div class="sel-bar" style="padding:.7rem 1.2rem;">', unsafe_allow_html=True)
        ds_l, ds_r = st.columns([4, 1])
        with ds_l:
            ds_names = [d["name"] for d in datasets]
            ds_ids   = [d["id"]   for d in datasets]
            d_idx    = ds_ids.index(st.session_state["dataset_id"]) if st.session_state["dataset_id"] in ds_ids else 0
            sel_ds   = st.selectbox("Dataset", ds_names, index=d_idx, key="sel_ds")
            st.session_state["dataset_id"] = ds_ids[ds_names.index(sel_ds)]
        with ds_r:
            st.markdown("<div style='margin-top:1.55rem;'></div>", unsafe_allow_html=True)
            if st.button("Delete", key="btn_del_ds", type="secondary"):
                delete_dataset(st.session_state["dataset_id"])
                st.session_state["dataset_id"] = None
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
else:
    datasets = []

dataset_id = st.session_state["dataset_id"]


# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
tab_upload, tab_overview, tab_quality, tab_views, tab_ask = st.tabs([
    "📤  Upload",
    "📊  Overview",
    "🛡️  Quality",
    "🎨  Auto Views",
    "💬  Ask Data",
])


# ───────────────────────────────────────────────────────────────
# TAB 1 — UPLOAD
# ───────────────────────────────────────────────────────────────
with tab_upload:
    if not project_id:
        st.info("Create a project above first.")
    else:
        u_l, u_r = st.columns([3, 2])

        with u_l:
            section_header("Upload a Dataset")

            from backend.data_workbench.ingest import classify_file, sha256_bytes

            st.markdown(
                '<div class="upload-hint">'
                '<p style="font-size:1rem;font-weight:700;color:var(--text);">Drop your file here</p>'
                '<p>CSV · XLSX · JSON · Parquet · up to 200 MB</p>'
                '</div>',
                unsafe_allow_html=True,
            )

            ds_name  = st.text_input("Dataset name", placeholder="e.g. Retail Transactions Q1 2024", key="ds_name")
            ctx_hint = st.text_area(
                "Context hint for AI (optional)",
                placeholder="e.g. Daily insurance claims from B2C platform, includes fraud labels",
                height=65, key="ctx_hint",
            )
            uploaded = st.file_uploader("File", type=["csv","xlsx","xls","json","parquet"],
                                        key="uploaded_file", label_visibility="collapsed")

            if uploaded:
                fmb = uploaded.size / 1e6
                ft  = classify_file(uploaded.name)
                st.markdown(
                    f'<div style="background:var(--bg-card);border:1px solid var(--border);'
                    f'border-radius:var(--r-md);padding:.6rem 1rem;font-size:.84rem;margin:.5rem 0;">'
                    f'📄 <b>{uploaded.name}</b> &nbsp;·&nbsp; {fmb:.1f} MB &nbsp;·&nbsp; {ft}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if st.button("Process & Profile", key="btn_process", type="primary", use_container_width=True):
                    if not ds_name.strip():
                        st.error("Enter a dataset name.")
                    else:
                        content = uploaded.read()
                        sha     = sha256_bytes(content)

                        ds_rec = create_dataset(project_id, ds_name.strip(), context_hint=ctx_hint.strip())
                        ds_id  = ds_rec["id"]

                        from backend.data_workbench.store import create_upload, update_dataset
                        create_upload(ds_id, uploaded.name, len(content), sha)
                        update_dataset(ds_id, file_count=1)

                        steps = [
                            (10, "Parsing file…"),
                            (35, "Building column profiles…"),
                            (60, "Running quality checks…"),
                            (78, "Generating AI insights…"),
                            (92, "Creating auto views…"),
                            (100, "Done!"),
                        ]
                        bar = st.progress(0, text=steps[0][1])

                        from backend.data_workbench.ingest import ingest
                        result = ingest(ds_id, uploaded.name, content)
                        bar.progress(steps[0][0], text=steps[1][1])

                        if not result["ok"]:
                            st.error(f"Parse error: {result.get('error')}")
                            delete_dataset(ds_id)
                        else:
                            from backend.data_workbench.profile import build_profile
                            sample_df = result.get("sample_df", result["df"])
                            profile   = build_profile(sample_df, ds_id, ctx_hint.strip())
                            bar.progress(steps[1][0], text=steps[2][1])

                            from backend.data_workbench.quality import run_quality_checks
                            quality = run_quality_checks(profile)
                            bar.progress(steps[2][0], text=steps[3][1])

                            from backend.data_workbench.llm import get_llm_summary
                            llm = get_llm_summary(profile, quality, ctx_hint.strip())
                            bar.progress(steps[3][0], text=steps[4][1])

                            from backend.data_workbench.views import generate_view_specs
                            from backend.data_workbench.store import save_profile, save_views
                            specs = generate_view_specs(profile, llm)
                            save_profile(ds_id, profile, quality, llm.get("summary",""), json.dumps(llm))
                            save_views(ds_id, specs)
                            update_dataset(ds_id, status="ready")
                            bar.progress(100, text=steps[5][1])

                            st.session_state.update({
                                "dataset_id": ds_id,
                                "profile":    profile,
                                "quality":    quality,
                                "llm":        llm,
                                "views":      specs,
                            })

                            rows = result["rows"]
                            cols = result["columns"]
                            score = quality["score"]
                            sc = "#00C896" if score >= 80 else ("#FFB020" if score >= 60 else "#FF3560")
                            st.markdown(
                                f'<div style="background:linear-gradient(135deg,rgba(0,200,150,.08),rgba(41,98,255,.06));'
                                f'border:1px solid rgba(0,200,150,.3);border-radius:var(--r-lg);'
                                f'padding:1rem 1.3rem;margin-top:.8rem;">'
                                f'<div style="font-size:1rem;font-weight:700;color:#00C896;margin-bottom:.4rem;">✓ Dataset ready</div>'
                                f'<div style="color:var(--text-2);font-size:.86rem;">'
                                f'<b style="color:var(--text);">{rows:,}</b> rows &nbsp;·&nbsp; '
                                f'<b style="color:var(--text);">{cols}</b> columns &nbsp;·&nbsp; '
                                f'Quality score: <b style="color:{sc};">{score}/100</b></div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            time.sleep(0.6)
                            st.rerun()

        with u_r:
            if datasets:
                section_header("Datasets in this project")
                for d in datasets[:10]:
                    sc_col = "#00C896" if d.get("status") == "ready" else "#FFB020"
                    st.markdown(
                        f'<div style="background:var(--bg-card);border:1px solid var(--border);'
                        f'border-radius:var(--r-md);padding:.65rem 1rem;margin:.4rem 0;'
                        f'display:flex;align-items:center;gap:10px;">'
                        f'<span style="width:7px;height:7px;border-radius:50%;background:{sc_col};'
                        f'display:inline-block;flex-shrink:0;"></span>'
                        f'<span style="flex:1;font-size:.86rem;font-weight:600;">{d["name"]}</span>'
                        f'<span style="font-size:.75rem;color:var(--text-2);">'
                        f'{d.get("row_count") or "—":,} rows · {d.get("column_count") or "—"} cols</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


# ───────────────────────────────────────────────────────────────
# TAB 2 — OVERVIEW
# ───────────────────────────────────────────────────────────────
with tab_overview:
    if not dataset_id:
        st.info("Upload or select a dataset above.")
    else:
        ds = get_dataset(dataset_id)
        if not ds:
            st.info("Dataset not found.")
        else:
            if st.session_state["profile"] is None:
                p = get_profile(dataset_id)
                if p:
                    st.session_state["profile"] = p["profile_json"]
                    st.session_state["quality"] = p["quality_json"]
                    try:
                        st.session_state["llm"] = json.loads(p.get("llm_hints") or "{}")
                    except Exception:
                        st.session_state["llm"] = {}

            profile = st.session_state["profile"]
            quality = st.session_state["quality"]
            llm     = st.session_state["llm"] or {}

            if not profile:
                st.warning("No profile found. Re-process the dataset from the Upload tab.")
            else:
                q_score  = (quality or {}).get("score", 0) if quality else 0
                q_color  = "#00C896" if q_score >= 80 else ("#FFB020" if q_score >= 60 else "#FF3560")
                dup_pct  = profile.get("duplicate_pct", 0) * 100
                mem_mb   = profile.get("memory_mb", "—")

                # ── KPI strip ──────────────────────────────────────────────
                st.markdown(
                    '<div class="dw-kpi-strip">'
                    + _kpi("Rows",          f"{profile.get('row_count', 0):,}",   "total records",  "#2962FF")
                    + _kpi("Columns",       str(profile.get("column_count", 0)),  "features",       "#00C896")
                    + _kpi("Memory",        f"{mem_mb} MB",                       "in-memory size", "#FFB020")
                    + _kpi("Duplicates",    f"{dup_pct:.1f}%",                    "duplicate rows", "#F97316" if dup_pct > 5 else "#7A8BA0")
                    + _kpi("Numeric cols",  str(len(profile.get("numeric_columns",   []))), "", "#A78BFA")
                    + _kpi("Date cols",     str(len(profile.get("date_columns",      []))), "", "#06B6D4")
                    + _kpi("Category cols", str(len(profile.get("categorical_columns",[]))), "", "#10B981")
                    + f'<div class="dw-kpi-card" style="--kpi-accent:{q_color};">'
                    f'<div class="dw-kpi-label">Quality Score</div>'
                    f'<div class="dw-kpi-value" style="color:{q_color};">{q_score}/100</div>'
                    f'<div class="dw-kpi-sub">data health</div></div>'
                    + '</div>',
                    unsafe_allow_html=True,
                )

                # ── AI summary ─────────────────────────────────────────────
                if llm.get("summary"):
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,rgba(41,98,255,.06),rgba(0,200,150,.03));'
                        f'border:1px solid rgba(41,98,255,.2);border-radius:var(--r-lg);'
                        f'padding:1.1rem 1.4rem;margin:.8rem 0;">'
                        f'<div style="font-size:.7rem;color:var(--accent);text-transform:uppercase;'
                        f'letter-spacing:.08em;margin-bottom:.5rem;font-weight:700;">AI Summary</div>'
                        f'<div style="color:var(--text);font-size:.92rem;line-height:1.75;">{llm["summary"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if llm.get("key_observations"):
                        obs_html = "".join(
                            f'<div style="display:flex;align-items:flex-start;gap:8px;margin:.3rem 0;">'
                            f'<span style="color:#2962FF;font-weight:700;margin-top:2px;">›</span>'
                            f'<span style="font-size:.88rem;color:var(--text-2);">{o}</span></div>'
                            for o in llm["key_observations"]
                        )
                        st.markdown(obs_html, unsafe_allow_html=True)

                st.markdown('<hr style="border-color:var(--border);margin:.9rem 0;">', unsafe_allow_html=True)

                # ── Schema + quick column charts ───────────────────────────
                ov_l, ov_r = st.columns([3, 2])

                with ov_l:
                    section_header("Schema")
                    cols_data = list_columns(dataset_id)
                    if cols_data:
                        schema_df = pd.DataFrame([{
                            "Column":   c["column_name"],
                            "Type":     c["inferred_type"],
                            "Null %":   f"{(c.get('null_pct') or 0)*100:.1f}%",
                            "Distinct": f"{c.get('distinct_count') or 0:,}",
                            "Min":      c.get("min_value") or "—",
                            "Max":      c.get("max_value") or "—",
                        } for c in cols_data])
                        st.dataframe(schema_df, use_container_width=True, hide_index=True,
                                     height=min(480, 45 + len(schema_df) * 35))

                with ov_r:
                    section_header("Column Types")
                    type_counts = {}
                    for c in profile.get("columns", []):
                        t = c.get("inferred_type", "other")
                        type_counts[t] = type_counts.get(t, 0) + 1
                    if type_counts:
                        fig_types = go.Figure(go.Pie(
                            labels=list(type_counts.keys()),
                            values=list(type_counts.values()),
                            hole=0.5,
                            marker=dict(colors=_PALETTE[:len(type_counts)]),
                            textinfo="label+value",
                            textfont=dict(size=12),
                        ))
                        fig_types.update_layout(**_lyt(260, ""))
                        st.plotly_chart(fig_types, use_container_width=True)

                # ── Data preview ───────────────────────────────────────────
                from backend.data_workbench.ingest import read_curated
                curated_key = ds.get("curated_key")
                if curated_key:
                    try:
                        @st.cache_data(ttl=300, show_spinner=False)
                        def _load_preview(key: str) -> pd.DataFrame:
                            return read_curated("", key)
                        prev_df = _load_preview(curated_key)
                        if not prev_df.empty:
                            st.markdown('<hr style="border-color:var(--border);margin:.9rem 0;">', unsafe_allow_html=True)
                            section_header("Data Preview")
                            st.dataframe(prev_df.head(10), use_container_width=True, hide_index=True)
                    except Exception:
                        pass

                # ── AI KPIs / questions ────────────────────────────────────
                if llm.get("suggested_kpis") or llm.get("next_questions"):
                    st.markdown('<hr style="border-color:var(--border);margin:.9rem 0;">', unsafe_allow_html=True)
                    kpi_col, q_col = st.columns(2)
                    with kpi_col:
                        if llm.get("suggested_kpis"):
                            section_header("Suggested KPIs")
                            for k in llm["suggested_kpis"][:5]:
                                st.markdown(
                                    f'<div style="border-left:3px solid #2962FF;padding:5px 10px;margin:4px 0;'
                                    f'font-size:.86rem;">'
                                    f'<b style="color:var(--text);">{k.get("name","")}</b>'
                                    f'<br><span style="color:var(--text-2);">{k.get("how","")}</span></div>',
                                    unsafe_allow_html=True,
                                )
                    with q_col:
                        if llm.get("next_questions"):
                            section_header("Jump to a Question")
                            for q in llm["next_questions"][:5]:
                                if st.button(f"→ {q}", key=f"nq_{hash(q)}", use_container_width=True):
                                    st.session_state["prefill_question"] = q
                                    st.rerun()


# ───────────────────────────────────────────────────────────────
# TAB 3 — QUALITY
# ───────────────────────────────────────────────────────────────
with tab_quality:
    _q_loaded = st.session_state.get("quality")
    if not _q_loaded and dataset_id:
        p = get_profile(dataset_id)
        if p:
            st.session_state["quality"] = p["quality_json"]
            _q_loaded = p["quality_json"]

    if not _q_loaded:
        st.info("Upload or select a dataset to see the quality report.")
    else:
        quality = _q_loaded
        profile = st.session_state["profile"] or {}
        score   = quality.get("score", 0)
        summary = quality.get("summary", {})
        sc_col  = "#00C896" if score >= 80 else ("#FFB020" if score >= 60 else "#FF3560")

        # ── Score hero ─────────────────────────────────────────────────
        hero_l, hero_r = st.columns([1, 2])
        with hero_l:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,rgba(41,98,255,.05),rgba(0,0,0,0));'
                f'border:1px solid var(--border);border-radius:var(--r-xl);padding:2rem 1.5rem;text-align:center;">'
                f'<div style="font-size:.65rem;color:var(--text-2);text-transform:uppercase;'
                f'letter-spacing:.1em;margin-bottom:.6rem;">Data Health Score</div>'
                f'<div style="font-size:4.5rem;font-weight:900;font-family:var(--mono);'
                f'color:{sc_col};line-height:1;">{score}</div>'
                f'<div style="font-size:1.1rem;color:var(--text-2);margin-top:.2rem;">/100</div>'
                f'<div style="margin-top:1rem;display:flex;justify-content:center;gap:12px;'
                f'flex-wrap:wrap;font-size:.78rem;">'
                f'<span style="color:#FF3560;">🔴 {summary.get("high",0)} critical</span>'
                f'<span style="color:#FFB020;">🟡 {summary.get("warning",0)} warnings</span>'
                f'<span style="color:#2962FF;">🔵 {summary.get("info",0)} info</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        with hero_r:
            # Score breakdown bar chart
            cats   = ["Completeness", "Uniqueness", "Consistency", "Validity"]
            issues = quality.get("issues", [])
            high_n = sum(1 for i in issues if i.get("severity")=="high")
            warn_n = sum(1 for i in issues if i.get("severity")=="warning")
            # Approximate sub-scores
            comp_score = max(0, 100 - high_n * 15 - warn_n * 5)
            uniq_score = max(0, 100 - int(profile.get("duplicate_pct", 0) * 200))
            cons_score = max(0, 100 - warn_n * 8)
            val_score  = score

            fig_scores = go.Figure(go.Bar(
                x=[comp_score, uniq_score, cons_score, val_score],
                y=cats,
                orientation="h",
                marker=dict(
                    color=[comp_score, uniq_score, cons_score, val_score],
                    colorscale=[[0,"#FF3560"],[0.6,"#FFB020"],[1,"#00C896"]],
                    cmin=0, cmax=100, showscale=False,
                ),
                text=[f"{v}/100" for v in [comp_score, uniq_score, cons_score, val_score]],
                textposition="outside",
            ))
            fig_scores.update_layout(**_lyt(240, "Score Breakdown"))
            fig_scores.update_xaxes(range=[0, 120])
            st.plotly_chart(fig_scores, use_container_width=True)

        # ── Issues ─────────────────────────────────────────────────────
        issues = quality.get("issues", [])
        if issues:
            st.markdown('<hr style="border-color:var(--border);margin:.8rem 0;">', unsafe_allow_html=True)
            section_header("Issues")
            for sev, label in [("high","Critical"), ("warning","Warnings"), ("info","Info")]:
                grp = [i for i in issues if i.get("severity") == sev]
                if grp:
                    st.markdown(
                        f'<div style="font-size:.75rem;font-weight:700;color:var(--text-2);'
                        f'text-transform:uppercase;letter-spacing:.07em;margin:.8rem 0 .3rem;">'
                        f'{label} ({len(grp)})</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("".join(_issue_html(i) for i in grp), unsafe_allow_html=True)
        else:
            st.success("No issues — this dataset is clean!")

        # ── Missingness chart ──────────────────────────────────────────
        col_profiles = profile.get("columns", [])
        null_data = [(c["column_name"], round(c.get("null_pct", 0) * 100, 2))
                     for c in col_profiles if c.get("null_pct", 0) > 0]

        if null_data:
            st.markdown('<hr style="border-color:var(--border);margin:.8rem 0;">', unsafe_allow_html=True)
            section_header("Missing Values by Column")
            ndf = pd.DataFrame(null_data, columns=["Column","Pct"]).sort_values("Pct", ascending=True)
            colors = ["#FF3560" if v > 50 else ("#FFB020" if v > 20 else "#2962FF") for v in ndf["Pct"]]
            fig_null = go.Figure(go.Bar(
                x=ndf["Pct"], y=ndf["Column"], orientation="h",
                marker_color=colors, opacity=0.85,
                text=[f"{v:.1f}%" for v in ndf["Pct"]],
                textposition="outside",
            ))
            fig_null.update_layout(**_lyt(max(200, len(ndf)*30+80), ""))
            fig_null.update_xaxes(title="Missing %", range=[0, 115])
            st.plotly_chart(fig_null, use_container_width=True)

        st.download_button(
            "Download Quality Report (JSON)",
            data=json.dumps(quality, indent=2).encode(),
            file_name="quality_report.json",
            mime="application/json",
            key="dl_quality",
        )


# ───────────────────────────────────────────────────────────────
# TAB 4 — AUTO VIEWS
# ───────────────────────────────────────────────────────────────
with tab_views:
    if not dataset_id:
        st.info("Upload or select a dataset above to see auto-generated charts.")
    else:
        ds = get_dataset(dataset_id)
        curated_key = ds.get("curated_key") if ds else None
        if not curated_key:
            st.warning("No curated parquet found. Re-process from the Upload tab.")
        else:
            from backend.data_workbench.ingest import read_curated

            @st.cache_data(ttl=300, show_spinner=False)
            def _load_df(key: str) -> pd.DataFrame:
                return read_curated("", key)

            df = _load_df(curated_key)
            if df.empty:
                st.warning("Could not load the curated dataset.")
            else:
                views   = list_views(dataset_id)
                profile = st.session_state["profile"] or (get_profile(dataset_id) or {}).get("profile_json", {})

                # Separate KPI view from chart views
                kpi_view = next((v for v in views if v["chart_type"] == "kpi"), None)
                chart_views = [v for v in views if v["chart_type"] != "kpi"]

                if not chart_views:
                    st.info("No chart views generated yet. Re-process the dataset from the Upload tab.")
                else:
                    # ── Level filter ───────────────────────────────────────
                    lv_cols = st.columns([1, 1, 1, 1, 3])
                    with lv_cols[0]:
                        lv_all = st.button("All", key="lv_all",
                                           type="primary" if st.session_state.get("view_level","All")=="All" else "secondary",
                                           use_container_width=True)
                    with lv_cols[1]:
                        lv_basic = st.button("Basic", key="lv_basic",
                                             type="primary" if st.session_state.get("view_level","")=="Basic" else "secondary",
                                             use_container_width=True)
                    with lv_cols[2]:
                        lv_inter = st.button("Intermediate", key="lv_inter",
                                             type="primary" if st.session_state.get("view_level","")=="Intermediate" else "secondary",
                                             use_container_width=True)
                    with lv_cols[3]:
                        lv_adv   = st.button("Advanced", key="lv_adv",
                                             type="primary" if st.session_state.get("view_level","")=="Advanced" else "secondary",
                                             use_container_width=True)
                    if lv_all:   st.session_state["view_level"] = "All"
                    if lv_basic: st.session_state["view_level"] = "Basic"
                    if lv_inter: st.session_state["view_level"] = "Intermediate"
                    if lv_adv:   st.session_state["view_level"] = "Advanced"

                    active_level = st.session_state.get("view_level", "All")
                    filtered = [
                        v for v in chart_views
                        if active_level == "All" or v.get("view_level","").title() == active_level
                    ]

                    if not filtered:
                        st.info(f"No {active_level.lower()} views for this dataset.")
                    else:
                        st.markdown(
                            f"<p style='color:var(--text-2);font-size:.8rem;margin:.5rem 0 1rem;'>"
                            f"Showing <b style='color:var(--text);'>{len(filtered)}</b> charts</p>",
                            unsafe_allow_html=True,
                        )

                        # ── 2-column chart grid ────────────────────────────
                        for row_i in range(0, len(filtered), 2):
                            row_views = filtered[row_i: row_i + 2]
                            cols = st.columns(len(row_views))

                            for col, view in zip(cols, row_views):
                                with col:
                                    spec  = view.get("spec") or {}
                                    name  = view.get("view_name", "Chart")
                                    level = view.get("view_level", "basic")
                                    expl  = view.get("explanation", "")
                                    ai_b  = '<span class="ai-badge">AI</span>' if spec.get("ai_generated") else ""
                                    lv_c  = {"basic":"#00C896","intermediate":"#FFB020","advanced":"#FF3560"}.get(level,"#7A8BA0")

                                    st.markdown(
                                        f'<div class="chart-card">'
                                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:.4rem;">'
                                        f'<span style="width:8px;height:8px;border-radius:50%;'
                                        f'background:{lv_c};display:inline-block;"></span>'
                                        f'<span class="chart-title">{name}</span>{ai_b}'
                                        f'</div>'
                                        + (f'<div class="chart-expl">{expl}</div>' if expl else "")
                                        + "</div>",
                                        unsafe_allow_html=True,
                                    )
                                    try:
                                        fig = _render_chart(spec, df, profile)
                                        if fig:
                                            fig.update_layout(margin=dict(l=40,r=16,t=28,b=36), height=300)
                                            st.plotly_chart(fig, use_container_width=True,
                                                            key=f"v_{view.get('id',row_i)}")
                                        else:
                                            st.caption("Chart type not supported for display.")
                                    except Exception as e:
                                        st.caption(f"Render error: {e}")


# ───────────────────────────────────────────────────────────────
# TAB 5 — ASK DATA
# ───────────────────────────────────────────────────────────────
with tab_ask:
    if not dataset_id:
        st.info("Upload or select a dataset above to start asking questions.")
    else:
        ds = get_dataset(dataset_id)
        curated_key = ds.get("curated_key") if ds else None
        if not curated_key:
            st.warning("No curated parquet found. Re-process from the Upload tab.")
        else:
            from backend.data_workbench.queries import ask_dataset, run_sql

            section_header("Ask a Question About Your Data")

            prefill = st.session_state.pop("prefill_question", "")

            example_qs = [
                "What are the top 10 rows by the largest numeric column?",
                "How many distinct values does each categorical column have?",
                "Show average values grouped by the first categorical column.",
                "What is the overall count of records?",
            ]

            st.markdown(
                "<p style='font-size:.8rem;color:var(--text-2);margin-bottom:.4rem;'>Quick examples:</p>",
                unsafe_allow_html=True,
            )
            eq_cols = st.columns(len(example_qs))
            for i, eq in enumerate(example_qs):
                if eq_cols[i].button(eq, key=f"eq_{i}", use_container_width=True):
                    prefill = eq

            st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

            question = st.text_area(
                "Your question",
                value=prefill,
                placeholder="e.g. Which product category had the highest average order value?",
                height=90, key="ask_question",
            )
            mode = st.radio("Mode", ["Natural Language (AI)", "Direct SQL"],
                            horizontal=True, key="ask_mode")

            if mode == "Direct SQL":
                direct_sql = st.text_area(
                    "SQL — use FROM dataset",
                    height=90,
                    placeholder="SELECT category, AVG(amount) FROM dataset GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
                    key="direct_sql",
                )

            if st.button("Run Query", key="btn_run_query", type="primary"):
                if mode != "Direct SQL" and not question.strip():
                    st.warning("Enter a question first.")
                else:
                    with st.spinner("Running…"):
                        if mode == "Direct SQL":
                            result = run_sql(direct_sql, curated_key)
                            result["sql_generated"] = direct_sql
                            result["explanation"] = ""
                        else:
                            result = ask_dataset(dataset_id, question.strip())

                    if not result.get("ok"):
                        st.error(f"Query error: {result.get('error')}")
                    else:
                        sql_disp = result.get("sql_executed") or result.get("sql_generated","")
                        if sql_disp:
                            with st.expander("SQL executed", expanded=True):
                                st.markdown(f'<div class="sql-box">{sql_disp}</div>',
                                            unsafe_allow_html=True)

                        if result.get("explanation"):
                            st.markdown(
                                f'<div style="background:var(--bg-card);border:1px solid var(--border);'
                                f'border-radius:var(--r-md);padding:.75rem 1rem;font-size:.88rem;'
                                f'margin:.6rem 0;">{result["explanation"]}</div>',
                                unsafe_allow_html=True,
                            )

                        df_result = result.get("df", pd.DataFrame())
                        if not df_result.empty:
                            st.markdown(
                                f"<p style='font-size:.8rem;color:var(--text-2);'>"
                                f"{result['row_count']:,} rows returned</p>",
                                unsafe_allow_html=True,
                            )
                            st.dataframe(df_result, use_container_width=True, hide_index=True)

                            num_c = df_result.select_dtypes(include="number").columns.tolist()
                            cat_c = df_result.select_dtypes(include="object").columns.tolist()

                            if cat_c and num_c and len(df_result) <= 50:
                                fig_r = px.bar(df_result.head(20), x=cat_c[0], y=num_c[0],
                                               color=cat_c[0], color_discrete_sequence=_PALETTE)
                                fig_r.update_layout(**_lyt(300, "Query Result"))
                                st.plotly_chart(fig_r, use_container_width=True)
                            elif num_c and not cat_c and len(df_result) > 5:
                                fig_r = go.Figure(go.Histogram(
                                    x=df_result[num_c[0]].dropna(),
                                    nbinsx=30, marker_color="#2962FF", opacity=0.8,
                                ))
                                fig_r.update_layout(**_lyt(260, "Result Distribution"))
                                st.plotly_chart(fig_r, use_container_width=True)

                            st.download_button(
                                "Download result CSV",
                                data=df_result.to_csv(index=False).encode(),
                                file_name="query_result.csv",
                                mime="text/csv",
                                key="dl_result",
                            )
                        else:
                            st.info("Query returned no rows.")
