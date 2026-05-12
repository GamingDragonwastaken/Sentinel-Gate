"""SentinelGate — Streamlit entry point.

Bootstraps the page configuration, loads environment variables, and wires up
the three primary UI surfaces: chat-with-inspection, policy management, and
the audit dashboard.
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database.audit_db import clear_audit_log, count_today
from security.compliance_engine import load_compliance_packs
from security.inspector import is_lobster_running
from security.policies import get_active_policies, load_sample_policies
from ui.chat_panel import render_chat_panel
from ui.dashboard_panel import render_dashboard_panel
from ui.policy_panel import render_policy_panel


st.set_page_config(
    page_title="🛡️ SentinelGate",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ SentinelGate | Enterprise AI Security Gateway")


# ---------------------------------------------------------------------------
# First-launch auto-seed: sample custom policies + default compliance pack.
# Cheap to re-evaluate on each rerun: the policy seed is guarded by a count
# query, and pack activation is guarded by session-state presence.
# ---------------------------------------------------------------------------
if len(get_active_policies()) == 0:
    load_sample_policies()

if "active_packs" not in st.session_state:
    try:
        _packs = load_compliance_packs()
    except Exception:
        _packs = []
    # Spec asks for framework == "Standard Enterprise"; existing YAML uses
    # "Enterprise". Match both so the literal-spec intent still activates.
    st.session_state.active_packs = [
        p.name for p in _packs
        if p.framework in ("Standard Enterprise", "Enterprise")
    ]


def _sidebar_reset() -> None:
    clear_audit_log()
    st.session_state.messages = []
    st.session_state.last_result = None
    st.session_state.threat_cache = {}


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

    # Lobster Trap status dot — green if running, grey if not
    _lobster_up = is_lobster_running()
    _dot = "🟢" if _lobster_up else "⚪"
    _label = "Lobster Trap: running" if _lobster_up else "Lobster Trap: offline (fallback active)"
    st.markdown(
        f"<span style='color:#94a3b8;'>{_dot} {_label}</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    try:
        _active_count = len(get_active_policies())
    except Exception:
        _active_count = 0
    try:
        _today_count = count_today()
    except Exception:
        _today_count = 0

    st.markdown("### Stats")
    st.markdown(
        f"<div style='color:#cbd5e1;'>"
        f"<b>Active policies:</b> {_active_count}<br>"
        f"<b>Requests (24h):</b> {_today_count}"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    if st.button("🔄 Reset Demo", key="sidebar_reset_demo", use_container_width=True):
        _sidebar_reset()
        st.rerun()


chat_tab, policy_tab, dashboard_tab = st.tabs(
    ["💬 Chat & Inspect", "⚙️ Policy Manager", "📊 Audit Dashboard"]
)

with chat_tab:
    render_chat_panel()

with policy_tab:
    render_policy_panel()

with dashboard_tab:
    render_dashboard_panel()
