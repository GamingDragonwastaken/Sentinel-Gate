"""Policy Manager tab — compliance packs (top) + custom NL policies (bottom)."""

from __future__ import annotations

from html import escape as html_escape

import streamlit as st

from security.policies import (
    Policy,
    create_policy,
    delete_policy,
    get_all_policies,
    load_sample_policies,
    toggle_policy,
)
from ui.icons import LANDMARK


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
    # st.subheader doesn't render inline HTML; use st.markdown for the SVG.
    st.markdown(
        f'<h3 style="display:flex;align-items:center;gap:10px;color:#f8fafc;'
        f'margin:0 0 4px 0;font-weight:700;font-size:1.5rem;">'
        f'<span style="color:#00d4ff;display:inline-flex;">{LANDMARK}</span>'
        f"Compliance policy packs</h3>",
        unsafe_allow_html=True,
    )
    st.caption("Pre-built rules from HIPAA, SOC 2, and NIST 800-53. Activate with one click.")

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
            st.markdown(f"**{getattr(pack, 'framework', '')}**")
            st.caption(f"{getattr(pack, 'rule_count', 0)} rules · {getattr(pack, 'name', '')}")
        with c2:
            is_active = pack.name in st.session_state.active_packs
            label = "Active" if is_active else "Inactive"
            if st.button(label, key=f"pack_toggle_{pack.name}",
                         type="primary" if is_active else "secondary",
                         use_container_width=True):
                if is_active:
                    st.session_state.active_packs.remove(pack.name)
                else:
                    st.session_state.active_packs.append(pack.name)
                st.rerun()


# ---------------------------------------------------------------------------
# Section B — Custom NL policies
# ---------------------------------------------------------------------------

def _render_create_form() -> None:
    with st.expander("Add a new policy", expanded=False):
        name = st.text_input("Policy name", key="new_policy_name")
        text = st.text_area(
            "Policy (plain English)",
            key="new_policy_text",
            height=120,
            placeholder="e.g. Never allow requests that ask for customer SSNs.",
        )
        if st.button("Add policy", key="add_policy_btn", type="primary"):
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
    """Render a single policy card using the .sg-policy-* classes from app.py.

    Severity drives the left-border accent through the --sg-policy-accent
    CSS variable; status drives the tint of the inline tag pills. Inline
    styles are confined to those three variable values — every other rule
    lives in the central style block so this card visually matches the
    rest of the UI without theme drift.
    """
    sev_color = _SEVERITY_COLORS.get(p.severity, "#94a3b8")
    status_color = "#22c55e" if p.active else "#64748b"
    status_label = "Active" if p.active else "Inactive"

    name_safe = html_escape(p.name, quote=True)
    text_safe = html_escape(p.natural_language, quote=True)
    sev_safe = html_escape(p.severity, quote=True)

    st.markdown(
        f"""<div class="sg-policy-card" style="--sg-policy-accent:{sev_color};">
          <div class="sg-policy-row">
            <div class="sg-policy-name">{name_safe}</div>
            <div class="sg-policy-tags">
              <span class="sg-policy-sev"
                    style="background:{sev_color}26;color:{sev_color};">{sev_safe}</span>
              <span class="sg-policy-status"
                    style="background:{status_color}1f;color:{status_color};">{status_label}</span>
            </div>
          </div>
          <div class="sg-policy-text">{text_safe}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if p.enforcement_keywords:
        chips = "".join(
            f'<span class="sg-policy-keyword">{html_escape(kw, quote=True)}</span>'
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
        if st.button("Load sample policies", key="load_samples_btn", type="primary"):
            with st.spinner("Seeding sample policies via Gemini…"):
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
