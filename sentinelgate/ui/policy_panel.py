"""Policy Manager tab — compliance packs (top) + custom NL policies (bottom)."""

from __future__ import annotations

import streamlit as st

from security.policies import (
    Policy,
    create_policy,
    delete_policy,
    get_all_policies,
    load_sample_policies,
    toggle_policy,
)


_SEVERITY_COLORS = {
    "low": "#22c55e",
    "medium": "#f59e0b",
    "high": "#ef4444",
    "critical": "#7f1d1d",
}


# ---------------------------------------------------------------------------
# Section A — Compliance Policy Packs (graceful fallback if module absent)
# ---------------------------------------------------------------------------

def _render_compliance_section() -> None:
    st.subheader("🏛️ Compliance Policy Packs")
    st.caption("Pre-built rules from HIPAA, SOC2, and NIST 800-53. Activate with one click.")

    try:
        from security.compliance_engine import load_compliance_packs
    except ImportError:
        st.info("Compliance packs coming soon — run Prompt 10 to enable.")
        return

    try:
        packs = load_compliance_packs()
    except Exception as exc:
        st.warning(f"Could not load compliance packs: {exc}")
        return

    if "active_packs" not in st.session_state:
        st.session_state.active_packs = []

    for pack in packs:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{getattr(pack, 'icon', '📋')} {getattr(pack, 'framework', '')}**")
            st.caption(f"{getattr(pack, 'rule_count', 0)} rules · {getattr(pack, 'name', '')}")
        with c2:
            is_active = pack.name in st.session_state.active_packs
            label = "✅ Active" if is_active else "○ Inactive"
            if st.button(label, key=f"pack_toggle_{pack.name}"):
                if is_active:
                    st.session_state.active_packs.remove(pack.name)
                else:
                    st.session_state.active_packs.append(pack.name)
                st.rerun()


# ---------------------------------------------------------------------------
# Section B — Custom NL policies
# ---------------------------------------------------------------------------

def _render_create_form() -> None:
    with st.expander("➕ Add a new policy", expanded=False):
        name = st.text_input("Policy name", key="new_policy_name")
        text = st.text_area(
            "Policy (plain English)",
            key="new_policy_text",
            height=120,
            placeholder="e.g. Never allow requests that ask for customer SSNs.",
        )
        if st.button("Add Policy", key="add_policy_btn", type="primary"):
            if not name.strip() or not text.strip():
                st.warning("Both name and policy text are required.")
            else:
                with st.spinner("Extracting keywords + severity via Gemini..."):
                    policy = create_policy(name.strip(), text.strip())
                st.success(f"Created policy: {policy.name} (severity: {policy.severity})")
                # Clear the inputs for the next add
                st.session_state.new_policy_name = ""
                st.session_state.new_policy_text = ""
                st.rerun()


def _render_policy_card(p: Policy) -> None:
    sev_color = _SEVERITY_COLORS.get(p.severity, "#94a3b8")
    status_color = "#22c55e" if p.active else "#64748b"
    status_label = "ACTIVE" if p.active else "INACTIVE"

    name_safe = p.name.replace("<", "&lt;").replace(">", "&gt;")
    text_safe = p.natural_language.replace("<", "&lt;").replace(">", "&gt;")

    st.markdown(
        f"""<div style="border-left:4px solid {sev_color};
                    background:rgba(17,24,39,0.6);padding:12px 16px;
                    margin:8px 0;border-radius:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-weight:600;color:#e2e8f0;font-size:1.05em;">{name_safe}</div>
            <div>
                <span style="background:{sev_color}33;color:{sev_color};
                            padding:2px 10px;border-radius:6px;
                            font-size:0.75em;text-transform:uppercase;
                            margin-right:6px;">{p.severity}</span>
                <span style="background:{status_color}22;color:{status_color};
                            padding:2px 10px;border-radius:6px;
                            font-size:0.75em;">{status_label}</span>
            </div>
        </div>
        <div style="color:#cbd5e1;margin-top:6px;font-size:0.92em;">{text_safe}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Keyword tags
    if p.enforcement_keywords:
        chips = "".join(
            f"<span style='background:rgba(0,212,255,0.12);color:#00d4ff;"
            f"padding:2px 8px;border-radius:6px;margin:2px;display:inline-block;"
            f"font-size:0.78em;'>{kw.replace('<', '&lt;')}</span>"
            for kw in p.enforcement_keywords
        )
        st.markdown(
            f"<div style='margin:4px 0 8px 0;'>{chips}</div>",
            unsafe_allow_html=True,
        )

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        toggle_label = "Disable" if p.active else "Enable"
        if st.button(toggle_label, key=f"policy_toggle_{p.id}", use_container_width=True):
            toggle_policy(p.id, not p.active)
            st.rerun()
    with c2:
        if st.button("Delete", key=f"policy_delete_{p.id}", use_container_width=True):
            delete_policy(p.id)
            st.rerun()


def _render_custom_section() -> None:
    st.subheader("Custom Policies (Powered by Gemini)")
    st.caption("Describe a rule in plain English; Gemini extracts the enforcement keywords.")

    policies = get_all_policies()

    if not policies:
        st.info("No policies defined yet.")
        if st.button("📥 Load Sample Policies", key="load_samples_btn", type="primary"):
            with st.spinner("Seeding sample policies via Gemini..."):
                load_sample_policies()
            st.rerun()

    _render_create_form()

    if policies:
        st.markdown(f"**{len(policies)} polic{'y' if len(policies)==1 else 'ies'} configured**")
        for p in policies:
            _render_policy_card(p)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_policy_panel() -> None:
    _render_compliance_section()
    st.divider()
    _render_custom_section()
