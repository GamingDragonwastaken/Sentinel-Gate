"""SentinelGate — Streamlit entry point.

Bootstraps the page configuration, loads environment variables, and wires up
the three primary UI surfaces: chat-with-inspection, policy management, and
the audit dashboard.
"""

import os
import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Item 4 — fail fast on missing API key BEFORE anything else touches Gemini.
# Streamlit's secrets.toml on the cloud is exposed via os.getenv after
# `load_dotenv()` has already run (Streamlit Cloud injects secrets into env).
# ---------------------------------------------------------------------------
if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    st.error(
        "⚠️ GEMINI_API_KEY not configured. "
        "Add it to .env locally or to Streamlit secrets on the cloud."
    )
    st.stop()


# Item 5 — SQLite persistence note (and trigger init via the import below).
# Note: SQLite persists within a session but resets on redeployment.
# For production, swap for PostgreSQL or Supabase free tier.
from database.audit_db import (
    clear_audit_log,
    count_blocked_today,
    count_today,
    get_stats,
)
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
# Item 7 — central session-state initialization.
# Every key any panel reads gets created here, so opening any tab first
# (without visiting Chat) can never raise KeyError.
# ---------------------------------------------------------------------------
def _init_session_state() -> None:
    defaults = {
        "messages": [],
        "session_id": str(uuid.uuid4()),
        "last_result": None,
        "threat_cache": {},
        "prompt_input": "",
        "scenario_choice": "(choose a scenario...)",
        "active_packs": None,  # filled below once packs load
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()


# ---------------------------------------------------------------------------
# First-launch auto-seed: sample custom policies + default compliance pack.
# Cheap to re-evaluate on each rerun: the policy seed is guarded by a count
# query, and pack activation is guarded by session-state presence.
# ---------------------------------------------------------------------------
try:
    if len(get_active_policies()) == 0:
        load_sample_policies()
except Exception as exc:  # never crash the page on a seed failure
    st.warning(f"Policy auto-seed skipped: {exc}")

if st.session_state.active_packs is None:
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


def _full_reset() -> None:
    """Shared reset handler used by the sidebar AND the dashboard button."""
    try:
        clear_audit_log()
    except Exception:
        pass
    st.session_state.messages = []
    st.session_state.last_result = None
    st.session_state.threat_cache = {}


# ---------------------------------------------------------------------------
# Item 9 — sidebar polish.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<span style='color:#22c55e;font-weight:600;'>🟢 ACTIVE</span> "
        "<span style='color:#94a3b8;'>System Status</span>",
        unsafe_allow_html=True,
    )

    # Lobster Trap status — green if reachable, grey otherwise. The probe
    # is cheap (loopback refused returns in ms) but failures must never
    # surface; wrap defensively.
    try:
        _lobster_up = is_lobster_running()
    except Exception:
        _lobster_up = False
    _dot = "🟢" if _lobster_up else "⚪"
    _label = "Lobster Trap: running" if _lobster_up else "Lobster Trap: offline (fallback active)"
    st.markdown(
        f"<span style='color:#94a3b8;font-size:0.9em;'>{_dot} {_label}</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Quantitative metrics — defended against DB failures.
    try:
        _active_policies = len(get_active_policies())
    except Exception:
        _active_policies = 0
    try:
        _stats = get_stats()
        _total_requests = int(_stats.get("total", 0))
    except Exception:
        _total_requests = 0
    try:
        _blocked_today = count_blocked_today()
    except Exception:
        _blocked_today = 0

    st.metric("Active Policies", _active_policies)
    st.metric("Total Requests", _total_requests)
    st.metric("Blocked Today", _blocked_today)

    st.divider()

    st.markdown(
        "<span style='color:#64748b;font-size:0.78em;'>"
        "Powered by Veea Lobster Trap + Gemini Flash"
        "</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    if st.button("🔄 Reset Demo", key="sidebar_reset_demo", use_container_width=True):
        _full_reset()
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
