"""Audit Dashboard panel — counts, recent activity, and risk distribution."""

import streamlit as st


def render() -> None:
    """Render the Audit Dashboard tab. TODO: pull from database.audit_db."""
    st.subheader("Audit Dashboard")
    st.caption("Operational view of every request the gateway has seen.")
    st.info("Dashboard panel — implementation pending.")
