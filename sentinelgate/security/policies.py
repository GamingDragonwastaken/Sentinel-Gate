"""Natural-language policy engine.

Policies are written in plain English by operators. Two LLM calls back the
engine:

1. At *creation* time, Gemini extracts a short keyword list and a severity
   label from the policy's natural-language description. This gives us
   cheap pre-filtering and operator-visible metadata.
2. At *check* time, all active policies are passed to Gemini alongside the
   user prompt; the model returns a single verdict (violated / not, and
   which policy).

Persistence is delegated to `database.audit_db`, which owns the schema.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from llm.gemini_client import call_gemini_json
from database.audit_db import (
    insert_policy_row,
    fetch_policies_rows,
    update_policy_active,
    delete_policy_row,
    count_policies,
)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    name: str
    natural_language: str
    enforcement_keywords: list = field(default_factory=list)
    severity: str = "medium"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    active: bool = True


@dataclass
class PolicyCheckResult:
    violated: bool
    policy_id: str = ""
    policy_name: str = ""
    explanation: str = ""


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

_KEYWORD_EXTRACTION_PROMPT = (
    "You are a security policy interpreter. Extract from this policy: "
    "(1) 5-10 keywords/phrases that indicate a violation, "
    "(2) severity: low/medium/high/critical. "
    'Return ONLY JSON: {"keywords": [...], "severity": "..."}'
)

_POLICY_CHECK_INSTRUCTIONS = (
    "Check if this prompt violates any policy. "
    "Return ONLY JSON: "
    '{"violated": bool, "policy_id": str, "policy_name": str, "explanation": str}'
)

_ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_policy(row: dict) -> Policy:
    return Policy(
        id=row["id"],
        name=row.get("name") or "",
        natural_language=row.get("natural_language") or "",
        enforcement_keywords=list(row.get("enforcement_keywords") or []),
        severity=(row.get("severity") or "medium"),
        created_at=row.get("created_at") or datetime.utcnow().isoformat(),
        active=bool(row.get("active", True)),
    )


def _policy_to_row(policy: Policy) -> dict:
    return {
        "id": policy.id,
        "name": policy.name,
        "natural_language": policy.natural_language,
        "enforcement_keywords": policy.enforcement_keywords,
        "severity": policy.severity,
        "created_at": policy.created_at,
        "active": 1 if policy.active else 0,
    }


def _extract_keywords_and_severity(natural_language: str) -> tuple[list[str], str]:
    """Ask Gemini for the keywords + severity; degrade gracefully on failure."""
    verdict = call_gemini_json(
        f"POLICY:\n{natural_language}",
        system_prompt=_KEYWORD_EXTRACTION_PROMPT,
    )
    if not isinstance(verdict, dict) or "error" in verdict:
        return [], "medium"

    raw_keywords = verdict.get("keywords") or []
    keywords = [str(k).strip() for k in raw_keywords if isinstance(k, str) and k.strip()]
    keywords = keywords[:10]

    severity = str(verdict.get("severity") or "medium").strip().lower()
    if severity not in _ALLOWED_SEVERITIES:
        severity = "medium"

    return keywords, severity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_policy(name: str, natural_language: str) -> Policy:
    """Create + persist a Policy. Gemini fills in keywords/severity."""
    keywords, severity = _extract_keywords_and_severity(natural_language)
    policy = Policy(
        name=name.strip(),
        natural_language=natural_language.strip(),
        enforcement_keywords=keywords,
        severity=severity,
    )
    insert_policy_row(_policy_to_row(policy))
    return policy


def get_active_policies() -> list[Policy]:
    return [_row_to_policy(r) for r in fetch_policies_rows(active_only=True)]


def get_all_policies() -> list[Policy]:
    return [_row_to_policy(r) for r in fetch_policies_rows(active_only=False)]


def check_prompt_against_policies(
    prompt: str,
    policies: list[Policy],
) -> PolicyCheckResult:
    """Ask Gemini whether `prompt` violates any of the supplied policies."""
    if not policies:
        return PolicyCheckResult(
            violated=False,
            policy_id="",
            policy_name="",
            explanation="No policies active",
        )

    policy_lines = []
    for p in policies:
        keywords_str = ", ".join(p.enforcement_keywords) if p.enforcement_keywords else "(none)"
        policy_lines.append(
            f"- id={p.id} | Name: {p.name}. Rule: {p.natural_language}. Keywords: {keywords_str}"
        )

    user_prompt = (
        f"USER PROMPT:\n{prompt}\n\n"
        f"POLICIES:\n" + "\n".join(policy_lines)
    )

    verdict = call_gemini_json(user_prompt, system_prompt=_POLICY_CHECK_INSTRUCTIONS)

    if not isinstance(verdict, dict) or "error" in verdict:
        return PolicyCheckResult(
            violated=False,
            policy_id="",
            policy_name="",
            explanation="check_failed",
        )

    violated = bool(verdict.get("violated", False))
    policy_id = str(verdict.get("policy_id") or "")
    policy_name = str(verdict.get("policy_name") or "")
    explanation = str(verdict.get("explanation") or "")

    # Defend against Gemini hallucinating a policy_id not in our set.
    valid_ids = {p.id for p in policies}
    valid_names = {p.name: p.id for p in policies}
    if violated:
        if policy_id not in valid_ids:
            # Try to recover from a name match before giving up.
            if policy_name in valid_names:
                policy_id = valid_names[policy_name]
            else:
                return PolicyCheckResult(
                    violated=False,
                    policy_id="",
                    policy_name="",
                    explanation=f"check_unmatched: {explanation}"[:300],
                )

    return PolicyCheckResult(
        violated=violated,
        policy_id=policy_id,
        policy_name=policy_name,
        explanation=explanation,
    )


def toggle_policy(policy_id: str, active: bool) -> bool:
    return update_policy_active(policy_id, active)


def delete_policy(policy_id: str) -> bool:
    return delete_policy_row(policy_id)


def load_sample_policies() -> None:
    """Seed the policies table from demo/sample_policies.json (once)."""
    if count_policies() > 0:
        return

    sample_path = Path(__file__).resolve().parent.parent / "demo" / "sample_policies.json"
    if not sample_path.exists():
        return

    try:
        samples = json.loads(sample_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return

    for entry in samples:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        text = entry.get("natural_language")
        if name and text:
            create_policy(name, text)
