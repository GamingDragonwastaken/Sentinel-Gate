"""SQLite-backed audit log for every prompt that passes through SentinelGate.

Every request — allowed or blocked — produces a row capturing the risk score,
intent classification, policy outcome, and timing. The schema is intentionally
flat to make ad-hoc analysis (Pandas / SQL) trivial.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sentinelgate.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    session_id TEXT,
    prompt_hash TEXT,
    prompt_preview TEXT,
    risk_score REAL,
    intent_label TEXT,
    intent_description TEXT,
    flags TEXT,
    decision TEXT,
    policy_violated INTEGER,
    policy_name TEXT,
    policy_explanation TEXT,
    response_preview TEXT,
    processing_time_ms INTEGER
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the audit_log table if it does not already exist."""
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def log_request(data: dict) -> str:
    """Insert a single audit row and return its generated id.

    `data` may contain any subset of the column names; missing fields default
    to None / 0. The `flags` field, if provided as a list, is JSON-encoded.
    """
    row_id = str(uuid.uuid4())
    flags = data.get("flags", [])
    if isinstance(flags, (list, dict)):
        flags = json.dumps(flags)

    payload = (
        row_id,
        data.get("timestamp", datetime.utcnow().isoformat()),
        data.get("session_id"),
        data.get("prompt_hash"),
        data.get("prompt_preview"),
        data.get("risk_score"),
        data.get("intent_label"),
        data.get("intent_description"),
        flags,
        data.get("decision"),
        int(data.get("policy_violated", 0)),
        data.get("policy_name"),
        data.get("policy_explanation"),
        data.get("response_preview"),
        data.get("processing_time_ms"),
    )

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                id, timestamp, session_id, prompt_hash, prompt_preview,
                risk_score, intent_label, intent_description, flags,
                decision, policy_violated, policy_name, policy_explanation,
                response_preview, processing_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        conn.commit()

    return row_id


def get_recent_logs(limit: int = 50) -> list[dict]:
    """Return the most recent audit rows as a list of dicts (newest first)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

    results = []
    for row in rows:
        record = dict(row)
        if record.get("flags"):
            try:
                record["flags"] = json.loads(record["flags"])
            except (ValueError, TypeError):
                pass
        results.append(record)
    return results


def get_stats() -> dict:
    """Aggregate counts and average risk across the full audit log."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN decision = 'ALLOW' THEN 1 ELSE 0 END) AS allowed,
                SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END) AS blocked,
                AVG(risk_score) AS avg_risk_score
            FROM audit_log
            """
        ).fetchone()

    return {
        "total": row["total"] or 0,
        "allowed": row["allowed"] or 0,
        "blocked": row["blocked"] or 0,
        "avg_risk_score": row["avg_risk_score"] or 0.0,
    }


init_db()
