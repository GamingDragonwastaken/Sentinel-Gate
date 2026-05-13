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


def add_custom_css() -> None:
    """Inject all SentinelGate visual chrome once per Streamlit run.

    Every class prefix is `sg-` to avoid clashing with Streamlit's own
    BEM-style selectors. Dynamic color values (e.g. risk score color)
    are expressed as modifier classes (`.sg-risk-safe`, etc.) so no
    HTML rendered elsewhere needs an inline `style="..."` attribute.
    """
    st.markdown(
        """
        <style>
        /* ============================================================
         * SentinelGate — visual chrome
         * Theme: bg #0A0E1A, accent #00D4FF, text #E2E8F0
         * ============================================================ */

        /* --- Hero header --- */
        .sg-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 22px;
            margin: 0 0 8px 0;
            background:
                linear-gradient(135deg,
                    rgba(0,212,255,0.08) 0%,
                    rgba(0,212,255,0.02) 60%,
                    rgba(0,0,0,0) 100%);
            border-radius: 14px;
            border: 1px solid rgba(0,212,255,0.12);
        }
        .sg-hero-left { display: flex; align-items: center; gap: 16px; }
        .sg-hero-shield {
            font-size: 2.6rem;
            line-height: 1;
            filter: drop-shadow(0 0 12px rgba(0,212,255,0.5));
        }
        .sg-hero-title {
            color: #f8fafc;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -0.5px;
            margin: 0;
        }
        .sg-hero-sub {
            color: #00D4FF;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-top: 4px;
        }
        .sg-hero-status {
            background: rgba(34,197,94,0.14);
            color: #22c55e;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 2px;
            border: 1px solid rgba(34,197,94,0.35);
            box-shadow: 0 0 14px rgba(34,197,94,0.18);
        }
        .sg-divider {
            height: 1px;
            background: linear-gradient(90deg,
                rgba(0,212,255,0) 0%,
                rgba(0,212,255,0.45) 50%,
                rgba(0,212,255,0) 100%);
            margin: 4px 0 18px 0;
        }

        /* --- Response cards (chat panel) --- */
        .sg-card {
            padding: 14px 18px;
            margin: 10px 0;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        }
        .sg-card-block {
            background: #ef444410;
            border-left: 3px solid #ef4444;
        }
        .sg-card-allow {
            background: #22c55e10;
            border-left: 3px solid #22c55e;
        }
        .sg-card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        .sg-pill {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.7rem;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            line-height: 1.4;
        }
        .sg-pill-block {
            background: rgba(239,68,68,0.2);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.45);
        }
        .sg-pill-allow {
            background: rgba(34,197,94,0.2);
            color: #22c55e;
            border: 1px solid rgba(34,197,94,0.45);
        }
        .sg-pill-meta {
            background: rgba(148,163,184,0.13);
            color: #cbd5e1;
            border: 1px solid rgba(148,163,184,0.18);
            font-size: 0.68rem;
            padding: 3px 10px;
            letter-spacing: 1px;
        }
        .sg-pill-agent {
            background: rgba(0,212,255,0.13);
            color: #00d4ff;
            border: 1px solid rgba(0,212,255,0.3);
            font-size: 0.66rem;
            padding: 3px 10px;
            letter-spacing: 1.5px;
        }
        .sg-card-body {
            color: #e2e8f0;
            white-space: pre-wrap;
            line-height: 1.5;
        }
        .sg-card-citation {
            margin-top: 10px;
            color: #fca5a5;
            font-size: 0.82rem;
            padding: 8px 12px;
            background: rgba(239,68,68,0.08);
            border-left: 2px solid rgba(239,68,68,0.45);
            border-radius: 6px;
        }

        /* --- User chat bubble --- */
        .sg-user-bubble {
            display: flex;
            justify-content: flex-end;
            margin: 10px 0;
        }
        .sg-user-bubble-inner {
            background: linear-gradient(135deg, #1e3a8a, #1e40af);
            padding: 10px 16px;
            border-radius: 14px 14px 4px 14px;
            max-width: 80%;
            color: #e2e8f0;
            box-shadow: 0 2px 8px rgba(30,58,138,0.35);
            line-height: 1.45;
        }

        /* --- Risk score monitor --- */
        .sg-risk-score {
            text-align: center;
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
            margin: 6px 0 4px 0;
            text-shadow: 0 0 22px currentColor;
        }
        .sg-risk-safe     { color: #22c55e; }
        .sg-risk-medium   { color: #f59e0b; }
        .sg-risk-high     { color: #ef4444; }
        .sg-risk-critical { color: #7f1d1d; }
        .sg-risk-label-wrap {
            text-align: center;
            margin-top: 10px;
        }
        .sg-risk-label {
            display: inline-block;
            padding: 5px 16px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .sg-risk-label-safe {
            background: rgba(34,197,94,0.18);
            color: #22c55e;
            border: 1px solid rgba(34,197,94,0.35);
        }
        .sg-risk-label-medium {
            background: rgba(245,158,11,0.18);
            color: #f59e0b;
            border: 1px solid rgba(245,158,11,0.35);
        }
        .sg-risk-label-high {
            background: rgba(239,68,68,0.18);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.35);
        }
        .sg-risk-label-critical {
            background: rgba(127,29,29,0.35);
            color: #fecaca;
            border: 1px solid rgba(127,29,29,0.55);
        }

        /* --- Flag chips --- */
        .sg-flag-chip {
            display: inline-block;
            background: rgba(239,68,68,0.18);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.28);
            padding: 4px 11px;
            border-radius: 8px;
            margin: 3px 3px 0 0;
            font-size: 0.78rem;
            font-weight: 600;
        }

        /* --- Tabs (Streamlit native, restyled) --- */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 4px;
            background: rgba(17,24,39,0.55);
            padding: 5px;
            border-radius: 11px;
            border: 1px solid rgba(0,212,255,0.08);
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 8px 16px;
            background: transparent;
            font-weight: 600;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: rgba(0,212,255,0.13) !important;
            color: #00D4FF !important;
        }

        /* --- Progress bar (thinner, accent-colored) --- */
        [data-testid="stProgress"] > div > div > div {
            background-image: linear-gradient(90deg, #00D4FF, #22c55e) !important;
        }
        [data-testid="stProgress"] > div > div {
            height: 6px !important;
            border-radius: 999px !important;
            background: rgba(148,163,184,0.18) !important;
        }

        /* --- Sidebar metric cards --- */
        [data-testid="stSidebar"] [data-testid="stMetric"] {
            background: rgba(17,24,39,0.55);
            padding: 10px 14px;
            border-radius: 9px;
            margin: 5px 0;
            border-left: 2px solid rgba(0,212,255,0.4);
        }
        [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
            color: #94a3b8;
            font-size: 0.72rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        [data-testid="stSidebar"] [data-testid="stMetricValue"] {
            color: #f8fafc;
            font-weight: 800;
        }

        /* --- Buttons --- */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            letter-spacing: 0.3px;
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(0,212,255,0.12);
        }

        /* --- Scrollbar polish --- */
        ::-webkit-scrollbar { width: 9px; height: 9px; }
        ::-webkit-scrollbar-track { background: rgba(17,24,39,0.4); }
        ::-webkit-scrollbar-thumb {
            background: rgba(0,212,255,0.25);
            border-radius: 999px;
        }
        ::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,0.4); }
        </style>
        """,
        unsafe_allow_html=True,
    )


add_custom_css()

st.markdown(
    """
    <div class="sg-hero">
      <div class="sg-hero-left">
        <div class="sg-hero-shield">🛡️</div>
        <div>
          <h1 class="sg-hero-title">SentinelGate</h1>
          <div class="sg-hero-sub">Enterprise AI Security Gateway</div>
        </div>
      </div>
      <div class="sg-hero-status">● PROTECTED</div>
    </div>
    <div class="sg-divider"></div>
    """,
    unsafe_allow_html=True,
)


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
