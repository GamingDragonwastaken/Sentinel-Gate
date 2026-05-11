"""Chat & Inspect panel — submit a prompt, watch it move through the gateway."""

import streamlit as st


def render() -> None:
    """Render the Chat & Inspect tab. TODO: wire up to the security pipeline."""
    st.subheader("Chat & Inspect")
    st.caption("Submit a prompt and watch SentinelGate evaluate it in real time.")
    st.info("Chat panel — implementation pending.")
