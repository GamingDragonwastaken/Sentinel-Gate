"""Chat & Inspect tab — the primary user-facing surface.

A two-column layout: chat history + composer on the left, live risk monitor
on the right. Every submission goes through `security.risk_scorer.process_prompt`
and the verdict drives the response card. Blocked prompts get an on-demand
Gemini Threat Intelligence expander.
"""

from __future__ import annotations

import hashlib
from html import escape as html_escape

import plotly.graph_objects as go
import streamlit as st

from database.audit_db import get_recent_logs, get_stats
from demo.scenarios import SCENARIOS
from ui.icons import (
    BAN,
    CHECK_CIRCLE,
    CLIPBOARD_CHECK,
    USER,
    X_MARK,
)


RISK_COLORS = {
    "safe": "#22c55e",
    "medium": "#f59e0b",
    "high": "#ef4444",
    "critical": "#7f1d1d",
}

_RISK_LABELS = {
    "safe": "SAFE",
    "medium": "MEDIUM RISK",
    "high": "HIGH RISK",
    "critical": "CRITICAL THREAT",
}

_SCENARIO_PLACEHOLDER = "(choose a scenario...)"


def get_risk_level(score: float) -> str:
    """Bucket a risk score into one of four labels.

    Bucket boundaries (spec):
      0.0–0.3   safe
      0.3–0.7   medium
      0.7–0.9   high
      0.9–1.0   critical
    """
    if score < 0.3:
        return "safe"
    if score < 0.7:
        return "medium"
    if score < 0.9:
        return "high"
    return "critical"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Session state is initialized centrally in app.py::_init_session_state().
# This panel intentionally does not re-init — duplicate initializers can drift
# and cause the panel that runs first to "win" when keys diverge.
def _e(value: object) -> str:
    """HTML-escape with quote escaping — safer than ad-hoc str.replace pairs.

    A bare ``str.replace("<", "&lt;")`` chain misses ampersands, single
    quotes, and double quotes, which means a hostile prompt containing
    ``</style><script>...`` could break out of the surrounding context.
    Using stdlib ``html.escape(value, quote=True)`` is the correct
    boundary discipline.
    """
    return html_escape(str(value), quote=True)


def _threat_cache_key(prompt: str, intent_label: str) -> str:
    return hashlib.sha256(f"{prompt[:100]}|{intent_label}".encode("utf-8")).hexdigest()


def _placeholder_threat(intent_label: str) -> dict:
    return {
        "attack_type": (intent_label or "unknown").replace("_", " ").title(),
        "confidence": 0,
        "severity": "Unknown",
        "explanation": "Threat intelligence module not yet wired in.",
        "technique": "TODO: wire explain_threat() in llm/gemini_client.py",
        "remediation": "Implement the explainer to populate this report.",
        "compliance_impact": "Pending implementation.",
    }


def _get_threat(prompt: str, intent_label: str) -> dict:
    """Cached threat-report lookup; degrades gracefully if explain_threat absent."""
    key = _threat_cache_key(prompt, intent_label)
    cache = st.session_state.threat_cache
    if key in cache:
        return cache[key]

    try:
        from llm.gemini_client import explain_threat
    except ImportError:
        # TODO: wire explain_threat() in llm/gemini_client.py
        threat = _placeholder_threat(intent_label)
        cache[key] = threat
        return threat

    with st.spinner("Generating threat intelligence…"):
        try:
            threat = explain_threat(prompt, intent_label)
        except Exception:
            threat = _placeholder_threat(intent_label)

    cache[key] = threat
    return threat


def _render_user_message(content: str) -> None:
    st.markdown(
        f"""<div class="sg-user-bubble">
        <div class="sg-user-bubble-inner">{_e(content)}</div></div>""",
        unsafe_allow_html=True,
    )


def _render_threat_report(prompt: str, intent_label: str) -> None:
    threat = _get_threat(prompt, intent_label)
    c1, c2, c3 = st.columns(3)
    c1.metric("Attack Type", threat["attack_type"])
    c2.metric("Confidence", f"{threat['confidence']}%")
    c3.metric("Severity", threat["severity"])
    st.markdown(f"**What happened:** {threat['explanation']}")
    st.markdown(f"**Technique:** {threat['technique']}")
    st.info(f"**Remediation:** {threat['remediation']}")
    st.warning(f"**Compliance impact:** {threat['compliance_impact']}")


def _render_assistant_message(msg: dict) -> None:
    score = float(msg.get("risk_score", 0.0))
    intent = msg.get("intent_label", "")
    agent_id = (msg.get("agent_id") or "").strip()
    citation = (msg.get("compliance_citation") or "").strip()
    inspection_ms = float(msg.get("inspection_ms") or 0.0)
    # Latency uses its own pill class (mono font + tabular nums + cyan dot)
    # so it visually reads as an instrument reading, not a label.
    lat_pill = (
        f'<span class="sg-pill sg-pill-latency" title="Inspection latency">'
        f"{inspection_ms:.1f}ms</span>"
        if inspection_ms
        else ""
    )

    if msg.get("decision") == "ALLOW":
        body = msg.get("response") or "(empty response)"
        agent_badge = ""
        if agent_id:
            agent_badge = (
                f'<span class="sg-pill sg-pill-agent">{USER}{_e(agent_id)}</span>'
            )
        card_html = "".join(
            [
                '<div class="sg-card sg-card-allow">',
                '<div class="sg-card-header">',
                f'<span class="sg-pill sg-pill-allow">{CHECK_CIRCLE}Allowed</span>',
                f'<span class="sg-pill sg-pill-meta">Risk {score:.2f}</span>',
                f'<span class="sg-pill sg-pill-meta">Intent: {_e(intent)}</span>',
                lat_pill,
                agent_badge,
                "</div>",
                f'<div class="sg-card-body">{_e(body)}</div>',
                "</div>",
            ]
        )
        st.markdown(card_html, unsafe_allow_html=True)
        return

    # BLOCK
    reason = msg.get("block_reason") or "Blocked by gateway"
    citation_block = ""
    if citation:
        citation_block = (
            f'<div class="sg-card-citation">'
            f'<span style="display:inline-flex;align-items:center;gap:6px;">'
            f'{CLIPBOARD_CHECK}<b>Compliance:</b> {_e(citation)}</span></div>'
        )
    card_html = "".join(
        [
            '<div class="sg-card sg-card-block">',
            '<div class="sg-card-header">',
            f'<span class="sg-pill sg-pill-block">{BAN}Blocked</span>',
            f'<span class="sg-pill sg-pill-meta">Risk {score:.2f}</span>',
            f'<span class="sg-pill sg-pill-meta">Intent: {_e(intent)}</span>',
            lat_pill,
            "</div>",
            f'<div class="sg-card-body">{_e(reason)}</div>',
            citation_block,
            "</div>",
        ]
    )
    st.markdown(card_html, unsafe_allow_html=True)
    with st.expander("Gemini threat intelligence report"):
        _render_threat_report(msg.get("prompt", ""), intent)


def _render_risk_sparkline(logs: list[dict], limit: int = 15) -> None:
    """Render a 32px tall sparkline of the last `limit` risk scores.

    Wrapped in a labeled container (.sg-sparkline-wrap) so the chart reads
    as a dashboard instrument rather than floating in the column. Both the
    open and close <div> tags are emitted as separate st.markdown calls
    because Streamlit cannot interleave a plotly chart inside a single
    markdown block — the chart is its own rendered widget.
    """
    recent_logs = list(logs[:limit])
    scores = []
    for log in reversed(recent_logs):
        try:
            scores.append(float(log.get("risk_score", 0.0)))
        except (TypeError, ValueError):
            continue

    if len(scores) < 2:
        return

    fig = go.Figure(
        data=[
            go.Scatter(
                x=list(range(len(scores))),
                y=scores,
                mode="lines",
                line=dict(color="#00D4FF", width=1.6, shape="spline", smoothing=0.6),
                fill="tozeroy",
                fillcolor="rgba(0, 212, 255, 0.10)",
                hoverinfo="skip",
            )
        ]
    )
    fig.update_layout(
        height=52,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, range=[0, 1], fixedrange=True),
        showlegend=False,
    )

    st.markdown(
        f'<div class="sg-sparkline-label">'
        f"<span>Risk history</span>"
        f'<span class="sg-sparkline-count">{len(scores)} of {limit}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_risk_monitor() -> None:
    last = st.session_state.last_result
    if last is not None:
        score = float(getattr(last, "risk_score", 0.0))
        level = get_risk_level(score)
        st.markdown(
            f'<div class="sg-risk-score sg-risk-{level}">{score:.2f}</div>',
            unsafe_allow_html=True,
        )
        st.progress(min(1.0, max(0.0, score)))
        try:
            logs = get_recent_logs(limit=15)
        except Exception:
            logs = []
        _render_risk_sparkline(logs, limit=15)
        st.markdown(
            f'<div class="sg-risk-label-wrap">'
            f'<span class="sg-risk-label sg-risk-label-{level}">'
            f"{_RISK_LABELS[level]}</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Send a prompt to populate live risk metrics.")

    st.divider()
    try:
        stats = get_stats()
    except Exception:
        stats = {"total": 0, "blocked": 0, "allowed": 0}
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", stats.get("total", 0))
    c2.metric("Blocked", stats.get("blocked", 0))
    c3.metric("Allowed", stats.get("allowed", 0))

    if last is not None and getattr(last, "flags", None):
        st.divider()
        st.markdown("**Active flags**")
        chips = "".join(
            f'<span class="sg-flag-chip">{X_MARK}{_e(flag)}</span>'
            for flag in last.flags
        )
        st.markdown(chips, unsafe_allow_html=True)


def _handle_scenario_load() -> None:
    """If the user picked a scenario, copy it into the prompt input and rerun.

    Streamlit forbids mutating a widget's session key after instantiation in
    the same run — so this *must* run before the text_area renders.
    """
    choice = st.session_state.get("scenario_choice", _SCENARIO_PLACEHOLDER)
    if choice and choice != _SCENARIO_PLACEHOLDER and choice in SCENARIOS:
        st.session_state.prompt_input = SCENARIOS[choice]
        st.session_state.scenario_choice = _SCENARIO_PLACEHOLDER
        st.rerun()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_chat_panel() -> None:
    """Render the Chat & Inspect tab in full."""
    # Session state is initialized centrally in app.py — do not re-init here.

    # Lazy import — avoid the import-time cost when this module is loaded
    # by app.py, and also break a potential circular when other security
    # modules grow to import UI helpers.
    from security.risk_scorer import process_prompt

    agent_id = st.selectbox(
        "Monitored Agent",
        ["billing-agent", "support-agent", "research-agent"],
        help="Simulates multi-agent enterprise environment",
    )

    # Handle a pending scenario load *before* any widget that uses prompt_input
    # is instantiated — otherwise Streamlit raises a state-mutation error.
    _handle_scenario_load()

    col_chat, col_monitor = st.columns([65, 35])

    with col_chat:
        st.subheader("Enterprise AI Assistant")
        st.caption("Protected by SentinelGate | All requests inspected in real-time")

        for msg in st.session_state.messages:
            if msg.get("role") == "user":
                _render_user_message(msg.get("content", ""))
            else:
                _render_assistant_message(msg)

        st.text_area("Your prompt:", key="prompt_input", height=100)

        bc1, bc2 = st.columns(2)
        with bc1:
            send_clicked = st.button("Send", use_container_width=True, type="primary")
        with bc2:
            st.selectbox(
                "Load attack scenario",
                [_SCENARIO_PLACEHOLDER] + list(SCENARIOS.keys()),
                key="scenario_choice",
                label_visibility="collapsed",
            )

        if send_clicked:
            prompt = (st.session_state.prompt_input or "").strip()
            if not prompt:
                st.warning("Enter a prompt before sending.")
            else:
                with st.spinner("SentinelGate inspecting…"):
                    result = process_prompt(
                        prompt,
                        session_id=st.session_state.session_id,
                        agent_id=agent_id,
                    )
                st.session_state.messages.append(
                    {"role": "user", "content": prompt}
                )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "prompt": prompt,
                        "decision": result.decision,
                        "risk_score": result.risk_score,
                        "intent_label": result.intent_label,
                        "response": result.response,
                        "block_reason": result.block_reason,
                        "flags": list(result.flags),
                        "agent_id": getattr(result, "agent_id", agent_id),
                        "compliance_citation": getattr(result, "compliance_citation", ""),
                        "inspection_ms": getattr(result, "inspection_ms", 0.0),
                    }
                )
                st.session_state.last_result = result
                st.rerun()

    with col_monitor:
        st.subheader("Live Risk Monitor")
        _render_risk_monitor()
