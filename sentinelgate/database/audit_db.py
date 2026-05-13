"""SQLite-backed audit log for every prompt that passes through SentinelGate.

Every request — allowed or blocked — produces a row capturing the risk score,
intent classification, policy outcome, and timing. The schema is intentionally
flat to make ad-hoc analysis (Pandas / SQL) trivial.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sentinelgate.db"

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    session_id TEXT,
    agent_id TEXT,
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

_POLICIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    name TEXT,
    natural_language TEXT,
    enforcement_keywords TEXT,
    severity TEXT,
    created_at TEXT,
    active INTEGER
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the audit_log and policies tables if they do not already exist.

    Also performs an idempotent ALTER for older DB files that predate the
    `agent_id` column.
    """
    with _connect() as conn:
        conn.execute(_AUDIT_SCHEMA)
        conn.execute(_POLICIES_SCHEMA)
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
        if "agent_id" not in existing_cols:
            conn.execute("ALTER TABLE audit_log ADD COLUMN agent_id TEXT")
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
        data.get("agent_id"),
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
                id, timestamp, session_id, agent_id, prompt_hash, prompt_preview,
                risk_score, intent_label, intent_description, flags,
                decision, policy_violated, policy_name, policy_explanation,
                response_preview, processing_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


# ---------------------------------------------------------------------------
# Policies table — low-level row I/O. Business logic lives in security/policies.py.
# ---------------------------------------------------------------------------

def insert_policy_row(row: dict) -> None:
    """Insert a single policy row. `enforcement_keywords` may be a list (auto-JSON)."""
    keywords = row.get("enforcement_keywords", [])
    if isinstance(keywords, (list, dict)):
        keywords = json.dumps(keywords)

    payload = (
        row["id"],
        row.get("name"),
        row.get("natural_language"),
        keywords,
        row.get("severity"),
        row.get("created_at", datetime.utcnow().isoformat()),
        int(row.get("active", 1)),
    )
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO policies
                (id, name, natural_language, enforcement_keywords,
                 severity, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        conn.commit()


def fetch_policies_rows(active_only: bool = True) -> list[dict]:
    """Return policy rows as dicts; `enforcement_keywords` is JSON-decoded."""
    sql = "SELECT * FROM policies"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY created_at ASC"

    with _connect() as conn:
        rows = conn.execute(sql).fetchall()

    results = []
    for row in rows:
        record = dict(row)
        if record.get("enforcement_keywords"):
            try:
                record["enforcement_keywords"] = json.loads(record["enforcement_keywords"])
            except (ValueError, TypeError):
                record["enforcement_keywords"] = []
        else:
            record["enforcement_keywords"] = []
        record["active"] = bool(record.get("active", 0))
        results.append(record)
    return results


def update_policy_active(policy_id: str, active: bool) -> bool:
    """Flip a policy's active flag; returns True if a row was updated."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE policies SET active = ? WHERE id = ?",
            (1 if active else 0, policy_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_policy_row(policy_id: str) -> bool:
    """Delete a policy by id; returns True if a row was removed."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
        conn.commit()
        return cur.rowcount > 0


def clear_audit_log() -> int:
    """Delete every row from audit_log. Returns the number of rows removed."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM audit_log")
        conn.commit()
        return cur.rowcount


def count_today() -> int:
    """Count audit rows in the last 24 hours (UTC, timezone-agnostic)."""
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with _connect() as conn:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE timestamp >= ?",
            (cutoff,),
        ).fetchone()
        return int(n)


def count_blocked_today() -> int:
    """Count BLOCK decisions in the last 24 hours."""
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with _connect() as conn:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE timestamp >= ? AND decision = 'BLOCK'",
            (cutoff,),
        ).fetchone()
        return int(n)


def get_agent_breakdown() -> dict:
    """Return {agent_id: count} from audit_log, excluding NULL agents."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT agent_id, COUNT(*) AS n
            FROM audit_log
            WHERE agent_id IS NOT NULL AND agent_id != ''
            GROUP BY agent_id
            ORDER BY n DESC
            """
        ).fetchall()
    return {r["agent_id"]: int(r["n"]) for r in rows}


def count_policies() -> int:
    with _connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM policies").fetchone()
        return int(n)


init_db()
