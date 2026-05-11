"""Smoke test — verifies Gemini connectivity and the audit-log roundtrip.

Run from the `sentinelgate/` directory after creating a `.env` file based on
`.env.example` and filling in a real `GEMINI_API_KEY`.
"""

import hashlib
import time
import uuid

from dotenv import load_dotenv

load_dotenv()

from llm.gemini_client import call_gemini
from database.audit_db import init_db, log_request, get_recent_logs


def main() -> None:
    print("=" * 60)
    print("SentinelGate smoke test")
    print("=" * 60)

    print("\n[1/3] Calling Gemini Flash...")
    prompt = "Hello! Please respond with exactly: 'Gemini Flash is working correctly.'"
    response = call_gemini(prompt)
    print(f"  prompt:   {prompt}")
    print(f"  response: {response}")
    if response.startswith("[gemini_error]"):
        raise RuntimeError("Gemini connectivity failed; see error above.")

    print("\n[2/3] Initializing audit DB and logging a sample entry...")
    init_db()
    sample = {
        "session_id": str(uuid.uuid4()),
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_preview": prompt[:80],
        "risk_score": 0.12,
        "intent_label": "benign_test",
        "intent_description": "Connectivity smoke test prompt.",
        "flags": ["smoke_test"],
        "decision": "ALLOW",
        "policy_violated": 0,
        "policy_name": None,
        "policy_explanation": None,
        "response_preview": (response or "")[:80],
        "processing_time_ms": 42,
    }
    row_id = log_request(sample)
    print(f"  inserted row id: {row_id}")

    print("\n[3/3] Reading recent logs...")
    recent = get_recent_logs(limit=5)
    print(f"  returned {len(recent)} row(s):")
    for row in recent:
        print(
            f"    - {row['timestamp']} | {row['decision']} "
            f"| risk={row['risk_score']} | {row['intent_label']}"
        )

    print("\nAll tests passed!")


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"\n(completed in {time.time() - start:.2f}s)")
