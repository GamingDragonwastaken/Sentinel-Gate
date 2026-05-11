"""SentinelGate — Streamlit entry point.

Bootstraps the page configuration, loads environment variables, and wires up
the three primary UI surfaces: chat-with-inspection, policy management, and
the audit dashboard.
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="🛡️ SentinelGate",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ SentinelGate | Enterprise AI Security Gateway")

with st.sidebar:
    st.markdown("### System")
    st.markdown(
        "<span style='color:#22c55e;'>● ACTIVE</span> "
        "<span style='color:#94a3b8;'>System Status</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<span style='color:#94a3b8;'>Model: Gemini Flash</span>",
        unsafe_allow_html=True,
    )

chat_tab, policy_tab, dashboard_tab = st.tabs(
    ["💬 Chat & Inspect", "⚙️ Policy Manager", "📊 Audit Dashboard"]
)

with chat_tab:
    st.info("Module loading...")

with policy_tab:
    st.info("Module loading...")

with dashboard_tab:
    st.info("Module loading...")
