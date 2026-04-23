"""
AI Advisor — GPT-4o powered portfolio Q&A with AssetEra fund context.
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from backend.ui import apply_styles, page_header, section_header, ticker_tape, disclaimer, CHART_LAYOUT
from backend.market import fetch_prices, compute_metrics, ALLOWLIST
from backend.ai_advisor.advisor import get_system_prompt, stream_response

st.set_page_config(page_title="AI Advisor — AssetEra", page_icon="🤖", layout="wide")
apply_styles()

@st.cache_data(ttl=300, show_spinner=False)
def _tape():
    p, _ = fetch_prices(sorted(ALLOWLIST), period="5d", interval="1d")
    return compute_metrics(p)

ticker_tape(_tape())
page_header("AI Advisor", "Context-aware portfolio Q&A · Powered by GPT-4o", badge="GPT-4o · STREAMING")

# ── API key check ─────────────────────────────────────────────────────
api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    st.markdown(
        """
        <div style="background:var(--bg-card);border:1px solid var(--border);border-left:3px solid var(--yellow);
                    border-radius:0 var(--r-lg) var(--r-lg) 0;padding:1.2rem 1.5rem;margin:1rem 0;">
          <div style="font-weight:700;color:var(--yellow);margin-bottom:.5rem;">⚠ OPENAI_API_KEY not configured</div>
          <div style="color:var(--text-2);font-size:.88rem;line-height:1.6;">
            Add your key to <code>.env</code>:<br>
            <code>OPENAI_API_KEY=sk-proj-...</code><br><br>
            Then restart: <code>streamlit run app.py</code>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Session context from Risk Profiler ───────────────────────────────
user_risk = st.session_state.get("user_risk_profile")
system    = get_system_prompt(user_risk=user_risk)

# ── Inline top bar: risk badge + clear chat ───────────────────────────
top_left, top_right = st.columns([3, 1])

with top_left:
    if user_risk:
        RISK_LABELS = {1: "Conservative", 2: "Moderately Conservative", 3: "Moderate",
                       4: "Moderately Aggressive", 5: "Aggressive"}
        risk_label = RISK_LABELS.get(user_risk, "")
        st.markdown(
            f'<div style="background:var(--green-dim);border:1px solid rgba(0,200,150,.25);'
            f'border-radius:10px;padding:.6rem 1rem;display:inline-flex;align-items:center;gap:12px;">'
            f'<span style="color:var(--green);font-weight:700;font-size:.82rem;">RISK PROFILE LOADED</span>'
            f'<span style="color:var(--text);font-size:1.3rem;font-weight:800;font-family:var(--mono);">{user_risk}/5</span>'
            f'<span style="color:var(--text-2);font-size:.78rem;">{risk_label} · Advisor context active</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;'
            'padding:.6rem 1rem;font-size:.84rem;color:var(--text-2);display:inline-block;">'
            '💡 Run the <b>Risk Profiler</b> first to give the advisor your risk context.'
            '</div>',
            unsafe_allow_html=True,
        )

with top_right:
    if st.button("Clear Chat", type="secondary", use_container_width=True):
        st.session_state.advisor_messages = []
        st.session_state.pop("mc_ran", None)
        st.rerun()

st.markdown("<div style='margin:.6rem 0;'></div>", unsafe_allow_html=True)

# ── Example questions (inline chips) ─────────────────────────────────
examples = [
    "What's the safest fund for a 60-year-old retiree?",
    "Compare Fund 3 vs Fund 5 for moderate risk",
    "How is Fund 4 allocated and what are the main risks?",
    "Explain the difference between Sharpe and Sortino ratios",
    "How should I diversify across the five funds?",
    "What is Geometric Brownian Motion?",
]

with st.expander("Example questions — click any to ask", expanded=False):
    eq_cols = st.columns(3)
    for i, ex in enumerate(examples):
        if eq_cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
            if "advisor_messages" not in st.session_state:
                st.session_state.advisor_messages = []
            st.session_state.advisor_messages.append({"role": "user", "content": ex})
            st.rerun()

# ── Chat ──────────────────────────────────────────────────────────────
if "advisor_messages" not in st.session_state:
    st.session_state.advisor_messages = []

# Welcome message
if not st.session_state.advisor_messages:
    st.markdown(
        """
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:14px;
                    padding:1.5rem;margin-bottom:1.5rem;text-align:center;">
          <div style="font-size:2rem;margin-bottom:.6rem;">🤖</div>
          <div style="font-weight:700;font-size:1rem;color:var(--text);margin-bottom:.4rem;">
            AssetEra AI Advisor
          </div>
          <div style="color:var(--text-2);font-size:.88rem;max-width:500px;margin:0 auto;line-height:1.6;">
            Ask me about AssetEra's five model funds, risk profiles, portfolio allocation,
            or any quantitative finance concepts. I have full context of the fund lineup.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Render history
for msg in st.session_state.advisor_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Ask about portfolio strategy, fund analysis, or risk management…"):
    st.session_state.advisor_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    api_msgs = [{"role": m["role"], "content": m["content"]}
                for m in st.session_state.advisor_messages]

    with st.chat_message("assistant"):
        try:
            response = st.write_stream(stream_response(api_msgs, system, api_key))
            st.session_state.advisor_messages.append({"role": "assistant", "content": response})
        except Exception as e:
            err = str(e)
            if "auth" in err.lower() or "api_key" in err.lower() or "401" in err:
                st.error("Invalid API key. Check your OPENAI_API_KEY in .env")
            else:
                st.error(f"Error: {err}")

disclaimer("AI responses are for educational purposes only and do not constitute investment advice.")
