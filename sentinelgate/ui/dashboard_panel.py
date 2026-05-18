"""Audit Dashboard tab — operational view of every request the gateway has seen."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database.audit_db import (
    clear_audit_log,
    get_agent_breakdown,
    get_recent_logs,
    get_stats,
)


_RISK_COLORS = {
    "Safe (0–0.3)": "#22c55e",
    "Medium (0.3–0.6)": "#f59e0b",
    "High (0.6–0.8)": "#ef4444",
    "Critical (0.8–1.0)": "#7f1d1d",
}

_PLOT_BG = "#111827"
_PLOT_PAPER = "rgba(0,0,0,0)"
_PLOT_FONT = "#e2e8f0"


def _bucket_risk(score: float) -> str:
    if score < 0.3:
        return "Safe (0–0.3)"
    if score < 0.6:
        return "Medium (0.3–0.6)"
    if score < 0.8:
        return "High (0.6–0.8)"
    return "Critical (0.8–1.0)"


def _style_decision(val: str) -> str:
    if val == "ALLOW":
        return "color: #22c55e; font-weight: 600;"
    if val == "BLOCK":
        return "color: #ef4444; font-weight: 600;"
    return ""


def _render_metrics(stats: dict) -> None:
    total = int(stats.get("total", 0))
    blocked = int(stats.get("blocked", 0))
    allowed = int(stats.get("allowed", 0))
    avg_risk = float(stats.get("avg_risk_score", 0.0))

    blocked_pct = (blocked / total * 100) if total else 0
    allowed_pct = (allowed / total * 100) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Requests", total)
    c2.metric(
        "Blocked",
        blocked,
        delta=f"{blocked_pct:.0f}%" if total else None,
        delta_color="inverse",
    )
    c3.metric(
        "Allowed",
        allowed,
        delta=f"{allowed_pct:.0f}%" if total else None,
    )
    c4.metric("Avg Risk Score", f"{avg_risk:.2f}")


def _render_pie_chart(stats: dict) -> None:
    allowed = int(stats.get("allowed", 0))
    blocked = int(stats.get("blocked", 0))
    if allowed + blocked == 0:
        st.info("No data yet — send some prompts to populate the chart.")
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["ALLOW", "BLOCK"],
                values=[allowed, blocked],
                hole=0.45,
                marker=dict(colors=["#22c55e", "#ef4444"]),
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(
        title="Allow vs Block",
        paper_bgcolor=_PLOT_PAPER,
        plot_bgcolor=_PLOT_BG,
        font_color=_PLOT_FONT,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_bucket_chart(logs: list[dict]) -> None:
    buckets = {label: 0 for label in _RISK_COLORS.keys()}
    for log in logs:
        try:
            score = float(log.get("risk_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        buckets[_bucket_risk(score)] += 1

    if sum(buckets.values()) == 0:
        st.info("No data yet — send some prompts to populate the chart.")
        return

    fig = go.Figure(
        data=[
            go.Bar(
                x=list(buckets.keys()),
                y=list(buckets.values()),
                marker_color=[_RISK_COLORS[k] for k in buckets.keys()],
            )
        ]
    )
    fig.update_layout(
        title="Requests by Risk Bucket",
        paper_bgcolor=_PLOT_PAPER,
        plot_bgcolor=_PLOT_BG,
        font_color=_PLOT_FONT,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title=None,
        yaxis_title="Count",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_agent_breakdown() -> None:
    breakdown = get_agent_breakdown()
    if not breakdown:
        return  # nothing to show

    st.subheader("Requests by Agent")
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(breakdown.keys()),
                y=list(breakdown.values()),
                marker_color="#00d4ff",
            )
        ]
    )
    fig.update_layout(
        paper_bgcolor=_PLOT_PAPER,
        plot_bgcolor=_PLOT_BG,
        font_color=_PLOT_FONT,
        margin=dict(l=10, r=10, t=10, b=10),
        height=240,
        xaxis_title=None,
        yaxis_title="Requests",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_recent_table(logs: list[dict]) -> pd.DataFrame:
    if not logs:
        st.info("No audit records yet.")
        return pd.DataFrame()

    df = pd.DataFrame(logs)
    columns = [
        "timestamp",
        "agent_id",
        "prompt_preview",
        "intent_label",
        "risk_score",
        "decision",
        "policy_name",
    ]
    cols_present = [c for c in columns if c in df.columns]
    df_view = df[cols_present].copy()

    if "risk_score" in df_view.columns:
        df_view["risk_score"] = df_view["risk_score"].map(
            lambda x: f"{float(x):.2f}" if x is not None else "—"
        )

    styler = df_view.style.map(_style_decision, subset=["decision"]) if "decision" in df_view.columns else df_view
    st.dataframe(styler, use_container_width=True, hide_index=True)
    return df_view


def _do_reset() -> None:
    clear_audit_log()
    st.session_state.messages = []
    st.session_state.last_result = None
    st.session_state.threat_cache = {}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_dashboard_panel() -> None:
    st.subheader("Security Audit Dashboard")
    st.caption("Operational view of every request the gateway has seen.")

    stats = get_stats()
    _render_metrics(stats)

    st.divider()

    logs = get_recent_logs(limit=500)

    left, right = st.columns(2)
    with left:
        _render_pie_chart(stats)
    with right:
        _render_risk_bucket_chart(logs)

    _render_agent_breakdown()

    st.divider()
    st.subheader("Recent Audit Records")
    df_view = _render_recent_table(logs)

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if not df_view.empty:
            csv_bytes = df_view.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export CSV",
                data=csv_bytes,
                file_name="sentinelgate_audit.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with c2:
        if st.button("Reset demo", key="dashboard_reset_demo", use_container_width=True):
            _do_reset()
            st.rerun()
