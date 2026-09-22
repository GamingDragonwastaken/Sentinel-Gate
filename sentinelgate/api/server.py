import os
import uuid
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sentinelgate.security.risk_scorer import process_prompt, GatewayResult
from sentinelgate.database.audit_db import (
    get_recent_logs,
    get_stats,
    clear_audit_log,
    count_blocked_today,
    get_agent_breakdown,
    fetch_policies_rows,
    update_policy_active,
    delete_policy_row,
)
from sentinelgate.security.policies import create_policy
from sentinelgate.security.inspector import is_lobster_running

_log = logging.getLogger("sentinelgate.api")

app = FastAPI(title="SentinelGate API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---
class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    agent_id: Optional[str] = "default-agent"

class PolicyCreateRequest(BaseModel):
    natural_language: str

class PolicyUpdateActiveRequest(BaseModel):
    active: bool


# --- Endpoints ---

@app.get("/api/status")
def get_status():
    _has_gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    _demo_mode = os.getenv("SENTINELGATE_DEMO_MODE", "1" if not _has_gemini_key else "0").lower() in {
        "1", "true", "yes", "on"
    }

    try:
        lobster_up = is_lobster_running()
    except Exception:
        lobster_up = False

    return {
        "demo_mode": _demo_mode,
        "lobster_running": lobster_up,
        "has_gemini_key": _has_gemini_key
    }

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result: GatewayResult = process_prompt(
            prompt=req.prompt,
            session_id=session_id,
            agent_id=req.agent_id
        )
        # Convert dataclass to dict for serialization
        return {
            "decision": result.decision,
            "risk_score": result.risk_score,
            "intent_label": result.intent_label,
            "intent_description": result.intent_description,
            "flags": result.flags,
            "policy_violated": result.policy_violated,
            "policy_name": result.policy_name,
            "policy_explanation": result.policy_explanation,
            "policy_status": result.policy_status,
            "response": result.response,
            "response_flagged": result.response_flagged,
            "block_reason": result.block_reason,
            "processing_time_ms": result.processing_time_ms,
            "inspection_ms": result.inspection_ms,
            "audit_id": result.audit_id,
            "compliance_citation": result.compliance_citation,
            "agent_id": result.agent_id,
        }
    except Exception as e:
        _log.error(f"Error processing prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def stats_endpoint():
    try:
        stats = get_stats()
        blocked_today = count_blocked_today()
        policies = fetch_policies_rows(active_only=True)
        return {
            "stats": stats,
            "blocked_today": blocked_today,
            "active_policies": len(policies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
def logs_endpoint(limit: int = 50):
    try:
        logs = get_recent_logs(limit)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs/clear")
def clear_logs_endpoint():
    try:
        cleared = clear_audit_log()
        return {"cleared": cleared}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Policy Management ---

@app.get("/api/policies")
def get_policies(active_only: bool = False):
    try:
        return fetch_policies_rows(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/policies")
def add_policy(req: PolicyCreateRequest):
    try:
        policy = create_policy(req.natural_language)
        return policy
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/policies/{policy_id}")
def update_policy(policy_id: str, req: PolicyUpdateActiveRequest):
    try:
        success = update_policy_active(policy_id, req.active)
        if not success:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"success": True}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/policies/{policy_id}")
def delete_policy(policy_id: str):
    try:
        success = delete_policy_row(policy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"success": True}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))


# Mount the frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
