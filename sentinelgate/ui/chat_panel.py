"""Chat & Inspect tab — the primary user-facing surface.

A two-column layout: chat history + composer on the left, live risk monitor
on the right. Every submission goes through `security.risk_scorer.process_prompt`
and the verdict drives the response card. Blocked prompts get an on-demand
Gemini Threat Intelligence expander.
"""

from __future__ import annotations

import hashlib
import uuid

import streamlit as st

from database.audit_db import get_stats
from demo.scenarios import SCENARIOS


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

def _init_session_state() -> None:
    ss = st.session_state
    if "messages" not in ss:
        ss.messages = []
    if "session_id" not in ss:
        ss.session_id = str(uuid.uuid4())
    if "last_result" not in ss:
        ss.last_result = None
    if "threat_cache" not in ss:
        ss.threat_cache = {}
    if "prompt_input" not in ss:
        ss.prompt_input = ""
    if "scenario_choice" not in ss:
        ss.scenario_choice = _SCENARIO_PLACEHOLDER


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

    with st.spinner("🧠 Generating threat intelligence..."):
        try:
            threat = explain_threat(prompt, intent_label)
        except Exception:
            threat = _placeholder_threat(intent_label)

    cache[key] = threat
    return threat


def _render_user_message(content: str) -> None:
    safe = content.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""<div style="display:flex;justify-content:flex-end;margin:8px 0;">
        <div style="background:#1e3a8a;padding:10px 14px;border-radius:12px;
                    max-width:80%;color:#e2e8f0;">{safe}</div></div>""",
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
    level = get_risk_level(score)
    color = RISK_COLORS[level]
    intent = msg.get("intent_label", "")
    agent_id = (msg.get("agent_id") or "").strip()
    citation = (msg.get("compliance_citation") or "").strip()

    if msg.get("decision") == "ALLOW":
        body = msg.get("response") or "(empty response)"
        safe_body = body.replace("<", "&lt;").replace(">", "&gt;")
        agent_badge = ""
        if agent_id:
            safe_agent = agent_id.replace("<", "&lt;").replace(">", "&gt;")
            agent_badge = (
                f"<span style='background:rgba(0,212,255,0.12);color:#00d4ff;"
                f"padding:2px 8px;border-radius:6px;margin-left:8px;"
                f"font-size:0.72em;letter-spacing:1px;text-transform:uppercase;'>"
                f"👤 {safe_agent}</span>"
            )
        st.markdown(
            f"""<div style="border-left:4px solid {color};
                        background:rgba(34,197,94,0.06);padding:10px 14px;
                        margin:8px 0;border-radius:8px;">
            <div style="color:{color};font-weight:600;font-size:0.9em;
                        margin-bottom:6px;">
            ✅ ALLOWED | Risk: {score:.2f} | Intent: {intent}{agent_badge}</div>
            <div style="color:#e2e8f0;white-space:pre-wrap;">{safe_body}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # BLOCK
    reason = msg.get("block_reason") or "Blocked by gateway"
    safe_reason = reason.replace("<", "&lt;").replace(">", "&gt;")
    citation_block = ""
    if citation:
        safe_citation = citation.replace("<", "&lt;").replace(">", "&gt;")
        citation_block = (
            f"<div style='margin-top:6px;color:#fca5a5;font-size:0.82em;'>"
            f"📋 <b>Compliance:</b> {safe_citation}</div>"
        )
    st.markdown(
        f"""<div style="border-left:4px solid {color};
                    background:rgba(239,68,68,0.06);padding:10px 14px;
                    margin:8px 0;border-radius:8px;">
        <div style="color:{color};font-weight:600;font-size:0.9em;
                    margin-bottom:6px;">
        ⛔ BLOCKED | Risk: {score:.2f} | Intent: {intent}</div>
        <div style="color:#cbd5e1;white-space:pre-wrap;">{safe_reason}</div>
        {citation_block}
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("🔍 Gemini Threat Intelligence Report"):
        _render_threat_report(msg.get("prompt", ""), intent)


def _render_risk_monitor() -> None:
    last = st.session_state.last_result
    if last is not None:
        score = float(getattr(last, "risk_score", 0.0))
        level = get_risk_level(score)
        color = RISK_COLORS[level]
        st.markdown(
            f"""<div style="text-align:center;color:{color};
                        font-size:3.2em;font-weight:800;line-height:1;">
            {score:.2f}</div>""",
            unsafe_allow_html=True,
        )
        st.progress(min(1.0, max(0.0, score)))
        st.markdown(
            f"<div style='text-align:center;color:{color};font-weight:700;"
            f"letter-spacing:2px;'>{_RISK_LABELS[level]}</div>",
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
        st.markdown("**Active Flags**")
        for flag in last.flags:
            st.markdown(
                "<span style='background:rgba(239,68,68,0.18);color:#ef4444;"
                "padding:4px 10px;border-radius:6px;margin:2px;"
                "display:inline-block;font-size:0.85em;'>"
                f"❌ {flag}</span>",
                unsafe_allow_html=True,
            )


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
    _init_session_state()

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
            send_clicked = st.button("🚀 Send", use_container_width=True)
        with bc2:
            st.selectbox(
                "⚡ Load Attack Scenario",
                [_SCENARIO_PLACEHOLDER] + list(SCENARIOS.keys()),
                key="scenario_choice",
                label_visibility="collapsed",
            )

        if send_clicked:
            prompt = (st.session_state.prompt_input or "").strip()
            if not prompt:
                st.warning("Enter a prompt before sending.")
            else:
                with st.spinner("🛡️ SentinelGate inspecting..."):
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
                    }
                )
                st.session_state.last_result = result
                st.rerun()

    with col_monitor:
        st.subheader("Live Risk Monitor")
        _render_risk_monitor()
