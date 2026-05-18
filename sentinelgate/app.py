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
    # st.error already prefixes a red alert glyph natively; no emoji needed.
    st.error(
        "GEMINI_API_KEY not configured. "
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
from ui.icons import DOT_FILLED, DOT_HOLLOW, SHIELD
from ui.policy_panel import render_policy_panel


st.set_page_config(
    page_title="SentinelGate — AI Security Gateway",
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
         * SentinelGate — visual chrome v2
         * Theme: navy #070B14 base, accent #00D4FF cyan, text #E2E8F0
         * Animations are deliberately off-beat (1.2s, 2.0s, 2.5s, 3.0s)
         * so the UI feels like independent live signals rather than a
         * marquee. Every .sg-* selector below preserves its identifier
         * from v1; this is a CSS-only enhancement.
         * ============================================================ */

        /* --- Item 1: Background with cyan corona at top --- */
        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"] {
            background: radial-gradient(
                ellipse 150% 40% at 50% -8%,
                rgba(0, 212, 255, 0.055) 0%,
                rgba(0, 212, 255, 0.015) 35%,
                #070B14 65%
            ) !important;
            background-attachment: fixed !important;
        }

        /* --- Item 10: Refined divider --- */
        .sg-divider {
            height: 1px !important;
            background: linear-gradient(
                90deg,
                rgba(0,212,255,0) 0%,
                rgba(0,212,255,0.5) 30%,
                rgba(0,212,255,0.5) 70%,
                rgba(0,212,255,0) 100%
            ) !important;
            margin: 6px 0 20px 0 !important;
        }

        /* --- Item 2: Hero header — more assertive --- */
        .sg-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 22px;
            margin: 0 0 8px 0;
            background: linear-gradient(
                135deg,
                rgba(0, 212, 255, 0.10) 0%,
                rgba(0, 212, 255, 0.04) 50%,
                rgba(0, 0, 0, 0) 100%
            ) !important;
            border-radius: 14px;
            border: 1px solid rgba(0, 212, 255, 0.20) !important;
            box-shadow:
                0 0 0 1px rgba(0,212,255,0.06),
                0 0 60px rgba(0, 212, 255, 0.06),
                inset 0 1px 0 rgba(0, 212, 255, 0.12),
                0 4px 32px rgba(0, 0, 0, 0.4) !important;
        }
        .sg-hero-left { display: flex; align-items: center; gap: 16px; }

        /* Item 2: animated shield breathe */
        @keyframes sg-shield-breathe {
            0%, 100% { filter: drop-shadow(0 0 12px rgba(0,212,255,0.5)); }
            50%      { filter: drop-shadow(0 0 24px rgba(0,212,255,0.75)); }
        }
        .sg-hero-shield {
            font-size: 2.6rem;
            line-height: 1;
            filter: drop-shadow(0 0 12px rgba(0,212,255,0.5));
            animation: sg-shield-breathe 3s ease-in-out infinite !important;
        }
        .sg-hero-shield svg {
            display: block;
            width: 44px;
            height: 44px;
        }

        /* Item 2: gradient hero title */
        .sg-hero-title {
            color: #f8fafc;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -0.5px;
            margin: 0;
            background: linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 50%, #CBD5E1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 12px rgba(255,255,255,0.10));
        }
        .sg-hero-sub {
            color: #00D4FF;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-top: 4px;
        }

        /* Item 3: PROTECTED badge with active pulse */
        @keyframes sg-protected-pulse {
            0%, 100% {
                box-shadow:
                    0 0 14px rgba(34,197,94,0.18),
                    0 0 0 0 rgba(34,197,94,0.40);
            }
            50% {
                box-shadow:
                    0 0 22px rgba(34,197,94,0.30),
                    0 0 0 5px rgba(34,197,94,0);
            }
        }
        .sg-hero-status {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(34,197,94,0.14);
            color: #22c55e;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 2px;
            border: 1px solid rgba(34,197,94,0.35);
            animation: sg-protected-pulse 2.5s ease-in-out infinite !important;
        }
        .sg-hero-status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 6px rgba(34,197,94,0.9);
        }

        /* --- Item 4: Glassmorphism response cards --- */
        .sg-card {
            padding: 14px 18px;
            margin: 10px 0;
            border-radius: 10px;
            backdrop-filter: blur(12px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(12px) saturate(160%) !important;
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.04),
                0 4px 24px rgba(0,0,0,0.4),
                inset 0 1px 0 rgba(255,255,255,0.04) !important;
            transition: box-shadow 0.2s ease, transform 0.2s ease !important;
        }
        .sg-card-block {
            background: rgba(239, 68, 68, 0.07) !important;
            border-left: 3px solid #ef4444 !important;
            box-shadow:
                0 0 0 1px rgba(239,68,68,0.15),
                0 0 30px rgba(239,68,68,0.07),
                0 4px 20px rgba(0,0,0,0.4) !important;
        }
        .sg-card-allow {
            background: rgba(34, 197, 94, 0.06) !important;
            border-left: 3px solid #22c55e !important;
            box-shadow:
                0 0 0 1px rgba(34,197,94,0.15),
                0 0 30px rgba(34,197,94,0.06),
                0 4px 20px rgba(0,0,0,0.4) !important;
        }
        .sg-card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }

        /* --- Item 6: Sharper, more premium pills --- */
        .sg-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 14px !important;
            border-radius: 999px;
            font-weight: 800 !important;
            font-size: 0.68rem !important;
            letter-spacing: 2px !important;
            text-transform: uppercase;
            line-height: 1.4;
        }
        .sg-pill-block {
            background: rgba(239,68,68,0.15) !important;
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.50) !important;
            box-shadow: 0 0 12px rgba(239,68,68,0.15) !important;
        }
        .sg-pill-allow {
            background: rgba(34,197,94,0.15) !important;
            color: #22c55e;
            border: 1px solid rgba(34,197,94,0.50) !important;
            box-shadow: 0 0 12px rgba(34,197,94,0.15) !important;
        }
        .sg-pill-meta {
            background: rgba(148,163,184,0.13);
            color: #cbd5e1;
            border: 1px solid rgba(148,163,184,0.18);
            font-size: 0.66rem !important;
            padding: 3px 10px !important;
            letter-spacing: 1.2px !important;
            font-weight: 700 !important;
        }
        .sg-pill-agent {
            background: rgba(0,212,255,0.10) !important;
            color: #00d4ff;
            border: 1px solid rgba(0,212,255,0.35) !important;
            box-shadow: 0 0 10px rgba(0,212,255,0.10) !important;
            font-size: 0.66rem !important;
            padding: 3px 10px !important;
            letter-spacing: 1.5px !important;
        }
        .sg-pill svg {
            width: 12px;
            height: 12px;
            flex-shrink: 0;
        }
        .sg-card-body {
            color: #e2e8f0;
            white-space: pre-wrap;
            line-height: 1.55;
        }

        /* --- Item 11: Refined citation block --- */
        .sg-card-citation {
            margin-top: 10px;
            color: #fca5a5;
            font-size: 0.82rem;
            padding: 8px 12px;
            background: rgba(239,68,68,0.06) !important;
            border-left: 2px solid rgba(239,68,68,0.50) !important;
            border-radius: 6px !important;
            box-shadow: 0 0 0 1px rgba(239,68,68,0.08) !important;
        }

        /* --- Item 12: Polished user chat bubble --- */
        .sg-user-bubble {
            display: flex;
            justify-content: flex-end;
            margin: 10px 0;
        }
        .sg-user-bubble-inner {
            background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%) !important;
            padding: 10px 16px;
            border-radius: 14px 14px 4px 14px;
            max-width: 80%;
            color: #e2e8f0;
            box-shadow:
                0 0 0 1px rgba(30,58,138,0.40),
                0 4px 16px rgba(30,58,138,0.40) !important;
            line-height: 1.45;
        }

        /* --- Item 5: Risk score — focal point with state-based glow --- */
        @keyframes sg-risk-glow-high {
            0%, 100% { text-shadow: 0 0 20px rgba(239,68,68,0.6); }
            50%      { text-shadow:
                          0 0 40px rgba(239,68,68,0.9),
                          0 0 60px rgba(239,68,68,0.3); }
        }
        @keyframes sg-risk-glow-critical {
            0%, 100% { text-shadow: 0 0 20px rgba(185,28,28,0.8); }
            50%      { text-shadow:
                          0 0 50px rgba(239,68,68,1.0),
                          0 0 80px rgba(239,68,68,0.4); }
        }
        .sg-risk-score {
            text-align: center;
            font-size: 3.8rem !important;
            font-weight: 900 !important;
            line-height: 1;
            margin: 6px 0 4px 0;
            font-variant-numeric: tabular-nums;
            letter-spacing: -2px;
        }
        .sg-risk-safe     { color: #22c55e; text-shadow: 0 0 18px rgba(34,197,94,0.45); }
        .sg-risk-medium   { color: #f59e0b; text-shadow: 0 0 18px rgba(245,158,11,0.45); }
        .sg-risk-high {
            color: #ef4444;
            animation: sg-risk-glow-high 2s ease-in-out infinite !important;
        }
        .sg-risk-critical {
            color: #fecaca;
            animation: sg-risk-glow-critical 1.2s ease-in-out infinite !important;
        }
        .sg-risk-label-wrap {
            text-align: center;
            margin-top: 10px;
        }
        .sg-risk-label {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 5px 16px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .sg-risk-label svg { width: 12px; height: 12px; }
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

        /* --- Flag chips (kept) --- */
        .sg-flag-chip {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: rgba(239,68,68,0.18);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,0.28);
            padding: 4px 11px;
            border-radius: 8px;
            margin: 3px 3px 0 0;
            font-size: 0.78rem;
            font-weight: 600;
        }
        .sg-flag-chip svg { width: 11px; height: 11px; flex-shrink: 0; }

        /* --- Item 8: Crisper tab states --- */
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
            transition: background 0.15s ease, color 0.15s ease;
        }
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            background: rgba(0,212,255,0.06) !important;
            color: rgba(0,212,255,0.80) !important;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: rgba(0, 212, 255, 0.12) !important;
            color: #00D4FF !important;
            box-shadow:
                inset 0 0 0 1px rgba(0,212,255,0.25),
                0 0 16px rgba(0,212,255,0.08) !important;
            font-weight: 700 !important;
        }

        /* --- Progress bar (kept) --- */
        [data-testid="stProgress"] > div > div > div {
            background-image: linear-gradient(90deg, #00D4FF, #22c55e) !important;
        }
        [data-testid="stProgress"] > div > div {
            height: 6px !important;
            border-radius: 999px !important;
            background: rgba(148,163,184,0.18) !important;
        }

        /* --- Item 7: Sidebar — cyan accent border + metric polish --- */
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(0, 212, 255, 0.12) !important;
            box-shadow: 2px 0 20px rgba(0, 212, 255, 0.04) !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetric"] {
            background: rgba(7, 11, 20, 0.80) !important;
            padding: 10px 14px;
            border-radius: 9px;
            margin: 5px 0;
            border-left: 2px solid rgba(0, 212, 255, 0.45) !important;
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.03),
                0 2px 8px rgba(0,0,0,0.3) !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetric"]:hover {
            border-left-color: rgba(0,212,255,0.70) !important;
            box-shadow:
                0 0 0 1px rgba(0,212,255,0.08),
                0 0 16px rgba(0,212,255,0.06),
                0 2px 8px rgba(0,0,0,0.3) !important;
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
            transition: transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(0,212,255,0.18);
        }
        .stButton > button:active {
            transform: translateY(0);
        }

        /* --- Item 9: Cyan-tinted scrollbar --- */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(7,11,20,0.5); }
        ::-webkit-scrollbar-thumb {
            background: rgba(0, 212, 255, 0.2);
            border-radius: 999px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 212, 255, 0.4);
        }

        /* --- Inline-SVG sizing helper used across pills/badges --- */
        .sg-icon { display: inline-block; vertical-align: -2px; }

        /* --- Policy card (migrated from inline styles in W5) --- */
        .sg-policy-card {
            background: rgba(17,24,39,0.60);
            padding: 12px 16px;
            margin: 8px 0;
            border-radius: 8px;
            border-left: 4px solid var(--sg-policy-accent, #94a3b8);
        }
        .sg-policy-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }
        .sg-policy-name {
            font-weight: 700;
            color: #e2e8f0;
            font-size: 1.02em;
            letter-spacing: -0.2px;
        }
        .sg-policy-tags { display: inline-flex; gap: 6px; }
        .sg-policy-sev,
        .sg-policy-status {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 6px;
            font-size: 0.72em;
            letter-spacing: 1px;
            text-transform: uppercase;
            font-weight: 700;
        }
        .sg-policy-text {
            color: #cbd5e1;
            margin-top: 6px;
            font-size: 0.92em;
            line-height: 1.55;
        }
        .sg-policy-keyword {
            display: inline-block;
            background: rgba(0,212,255,0.12);
            color: #00d4ff;
            border: 1px solid rgba(0,212,255,0.20);
            padding: 2px 9px;
            border-radius: 6px;
            margin: 3px 3px 0 0;
            font-size: 0.76em;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


add_custom_css()

st.markdown(
    f"""
    <div class="sg-hero">
      <div class="sg-hero-left">
        <div class="sg-hero-shield">{SHIELD}</div>
        <div>
          <h1 class="sg-hero-title">SentinelGate</h1>
          <div class="sg-hero-sub">Enterprise AI Security Gateway</div>
        </div>
      </div>
      <div class="sg-hero-status">
        <span class="sg-hero-status-dot" aria-hidden="true"></span>PROTECTED
      </div>
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
        f"<span style='color:#22c55e;font-weight:600;display:inline-flex;"
        f"align-items:center;gap:6px;'>{DOT_FILLED} ACTIVE</span> "
        f"<span style='color:#94a3b8;margin-left:6px;'>System Status</span>",
        unsafe_allow_html=True,
    )

    # Lobster Trap status — green if reachable, grey otherwise. The probe
    # is cheap (loopback refused returns in ms) but failures must never
    # surface; wrap defensively.
    try:
        _lobster_up = is_lobster_running()
    except Exception:
        _lobster_up = False
    _dot_svg = DOT_FILLED if _lobster_up else DOT_HOLLOW
    _dot_color = "#22c55e" if _lobster_up else "#64748b"
    _label = "Lobster Trap: running" if _lobster_up else "Lobster Trap: offline (fallback active)"
    st.markdown(
        f"<span style='color:#94a3b8;font-size:0.9em;display:inline-flex;"
        f"align-items:center;gap:6px;'>"
        f"<span style='color:{_dot_color};display:inline-flex;'>{_dot_svg}</span>"
        f"{_label}</span>",
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

    if st.button("Reset demo", key="sidebar_reset_demo", use_container_width=True):
        _full_reset()
        st.rerun()


chat_tab, policy_tab, dashboard_tab = st.tabs(
    ["Chat & Inspect", "Policy Manager", "Audit Dashboard"]
)

with chat_tab:
    render_chat_panel()

with policy_tab:
    render_policy_panel()

with dashboard_tab:
    render_dashboard_panel()
