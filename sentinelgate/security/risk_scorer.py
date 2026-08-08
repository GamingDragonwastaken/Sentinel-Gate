"""End-to-end gateway pipeline — the public entry point for SentinelGate.

`process_prompt` is the orchestrator. It runs ingress inspection, evaluates
active policies, decides ALLOW/BLOCK, optionally calls the LLM through the
Lobster Trap path, runs egress inspection on the response, and persists a
full audit row. All in one call. Always returns a `GatewayResult` — never
raises.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from database.audit_db import log_request
from llm.gemini_client import call_gemini_via_lobster
from security.inspector import demo_mode_enabled, inspect_prompt, inspect_response
from security.policies import (
    check_prompt_against_policies,
    get_active_policies,
)

# Compliance packs are loaded lazily and *only* used to surface a citation
# alongside an already-made decision. They never independently cause a BLOCK.
try:
    from security.compliance_engine import check_compliance, load_compliance_packs
    _COMPLIANCE_PACKS = load_compliance_packs()
except Exception:  # pragma: no cover - degrades gracefully if engine absent
    _COMPLIANCE_PACKS = []
    def check_compliance(text, packs):  # type: ignore[no-redef]
        from types import SimpleNamespace
        return SimpleNamespace(matched=False, rule_name=None, compliance_refs=[])


_log = logging.getLogger("sentinelgate.gateway")

DEFAULT_RISK_THRESHOLD = 0.7
RESPONSE_RISK_THRESHOLD = 0.7
MAX_PROMPT_CHARS = 8_000


@dataclass
class GatewayResult:
    decision: str
    risk_score: float
    intent_label: str
    intent_description: str
    flags: list = field(default_factory=list)
    policy_violated: bool = False
    policy_name: str = ""
    policy_explanation: str = ""
    policy_status: str = "allowed"
    response: str = ""
    response_flagged: bool = False
    block_reason: str = ""
    processing_time_ms: int = 0
    inspection_ms: float = 0.0
    audit_id: str = ""
    # Informational citation from the compliance pack engine. Populated only
    # when a pack rule matched the prompt; never drives the decision itself.
    compliance_citation: str = ""
    agent_id: str = ""


def _risk_threshold() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("RISK_THRESHOLD", str(DEFAULT_RISK_THRESHOLD)))))
    except (TypeError, ValueError):
        return DEFAULT_RISK_THRESHOLD


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def process_prompt(
    prompt: str,
    session_id: str = "",
    agent_id: str = "default-agent",
) -> GatewayResult:
    """Run the full security pipeline against a single user prompt."""
    started = time.perf_counter()
    if not isinstance(prompt, str):
        prompt = str(prompt or "")
    prompt = prompt.strip()
    threshold = _risk_threshold()

    # Step 1 — ingress inspection
    _t0 = time.perf_counter()
    if not prompt:
        from security.inspector import InspectionResult
        inspection = InspectionResult(
            risk_score=1.0,
            intent_label="invalid_input",
            intent_description="Empty prompts are not eligible for model execution.",
            flags=["invalid_input"],
            response_flagged=True,
        )
    elif len(prompt) > MAX_PROMPT_CHARS:
        from security.inspector import InspectionResult
        inspection = InspectionResult(
            risk_score=1.0,
            intent_label="input_too_large",
            intent_description=f"Prompt exceeds the {MAX_PROMPT_CHARS}-character gateway limit.",
            flags=["input_too_large"],
            response_flagged=True,
        )
    else:
        inspection = inspect_prompt(prompt)

    # Step 2 — policy evaluation
    policies = get_active_policies()
    policy_result = check_prompt_against_policies(prompt, policies)

    # Step 3 — decision gate (fail-closed posture)
    decision = "ALLOW"
    block_reason = ""
    if inspection.intent_label in {"inspection_unavailable", "lobster_unavailable"}:
        decision = "BLOCK"
        block_reason = "Inspection unavailable; failing closed for security"
    elif inspection.risk_score >= threshold:
        decision = "BLOCK"
        block_reason = (
            f"Risk score {inspection.risk_score:.2f} meets or exceeds threshold "
            f"{threshold:.2f} ({inspection.intent_label})"
        )
    elif policy_result.indeterminate:
        decision = "BLOCK"
        block_reason = "Policy evaluation is indeterminate; failing closed for security"
    elif policy_result.violated:
        decision = "BLOCK"
        block_reason = (
            f"Policy violation: {policy_result.policy_name} — "
            f"{policy_result.explanation}"
        )
    _inspection_ms = round((time.perf_counter() - _t0) * 1000, 1)

    # Step 4 — if ALLOW, call the LLM and inspect the response
    response_text = ""
    response_flagged = False
    if decision == "ALLOW":
        if demo_mode_enabled():
            response_text = (
                "Synthetic SentinelGate response: the request passed the local "
                "policy and inspection checks."
            )
        else:
            response_text = call_gemini_via_lobster(prompt) or ""
        response_inspection = inspect_response(response_text)
        response_flagged = response_inspection.intent_label in {"inspection_unavailable", "lobster_unavailable"} or response_inspection.risk_score >= RESPONSE_RISK_THRESHOLD
        if response_flagged:
            decision = "BLOCK"
            block_reason = (
                f"Response flagged: risk {response_inspection.risk_score:.2f} "
                f"({response_inspection.intent_label})"
            )
            response_text = ""  # do not leak a flagged response back to caller

    # Step 4.5 — compliance pack citation (informational, not decisive).
    # We only look up a citation; we never use the match to BLOCK because
    # that would change the decision contract.
    compliance_citation = ""
    try:
        if _COMPLIANCE_PACKS:
            match = check_compliance(prompt, _COMPLIANCE_PACKS)
            if getattr(match, "matched", False):
                refs = [r for r in (getattr(match, "compliance_refs", []) or []) if r]
                framework = ""
                # Find the pack whose rule matched so we can name the framework.
                rule_name = getattr(match, "rule_name", "") or ""
                for pack in _COMPLIANCE_PACKS:
                    if any(getattr(r, "name", "") == rule_name for r in pack.rules):
                        framework = pack.framework
                        break
                if refs and framework:
                    compliance_citation = f"{framework} {refs[0]}"
                elif framework:
                    compliance_citation = framework
                elif refs:
                    compliance_citation = refs[0]
    except Exception as exc:  # pragma: no cover - never crash the gateway
        _log.warning("compliance pack lookup failed: %s", exc)
        compliance_citation = ""

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # Step 5 — audit log
    audit_payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "agent_id": agent_id,
        "prompt_hash": _prompt_hash(prompt),
        "prompt_preview": prompt[:80],
        "risk_score": float(inspection.risk_score),
        "intent_label": inspection.intent_label,
        "intent_description": inspection.intent_description,
        "flags": list(inspection.flags),
        "decision": decision,
        "policy_violated": 1 if policy_result.violated else 0,
        "policy_status": policy_result.status,
        "policy_name": policy_result.policy_name,
        "policy_explanation": policy_result.explanation,
        "response_preview": (response_text or "")[:200],
        "processing_time_ms": elapsed_ms,
    }
    try:
        audit_id = log_request(audit_payload)
    except Exception as exc:
        _log.warning("audit log write failed: %s", exc)
        audit_id = ""

    # Step 6 — assemble result
    return GatewayResult(
        decision=decision,
        risk_score=float(inspection.risk_score),
        intent_label=inspection.intent_label,
        intent_description=inspection.intent_description,
        flags=list(inspection.flags),
        policy_violated=policy_result.violated,
        policy_name=policy_result.policy_name,
        policy_explanation=policy_result.explanation,
        policy_status=policy_result.status,
        response=response_text,
        response_flagged=response_flagged,
        block_reason=block_reason,
        processing_time_ms=elapsed_ms,
        inspection_ms=_inspection_ms,
        audit_id=audit_id,
        compliance_citation=compliance_citation,
        agent_id=agent_id,
    )
