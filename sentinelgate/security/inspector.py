"""Prompt/response inspection backed by Veea's Lobster Trap proxy.

This module manages the Lobster Trap subprocess and exposes the inspection
API used by the rest of the gateway. The concrete request/response wiring
is pending the CLI/config discovery performed by `test_lobster.py`.
"""

from dataclasses import dataclass, field
import subprocess
import time
import requests
import os


@dataclass
class InspectionResult:
    risk_score: float
    intent_label: str
    intent_description: str
    flags: list
    response_flagged: bool
    raw_output: dict


LOBSTER_PORT = int(os.getenv("LOBSTER_PORT", "8765"))
LOBSTER_URL = f"http://localhost:{LOBSTER_PORT}"
_lobster_process = None


def start_lobster_trap(config_path: str = "configs/default_policy.yaml") -> bool:
    global _lobster_process
    binary = "bin/lobstertrap"
    if not os.path.exists(binary):
        return False
    try:
        _lobster_process = subprocess.Popen(
            [
                binary, "serve",
                "--policy", config_path,
                "--listen", f":{LOBSTER_PORT}",
                "--backend", "https://generativelanguage.googleapis.com/v1beta/openai/v1",
                "--audit-log", "audit.json",
                "--no-dashboard",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(1.5)
        return _lobster_process.poll() is None
    except Exception as e:
        print(f"Lobster Trap startup failed: {e}")
        return False


def inspect_prompt(prompt: str) -> InspectionResult:
    return InspectionResult(
        risk_score=0.5, intent_label="pending_integration",
        intent_description="Lobster Trap integration pending config discovery",
        flags=[], response_flagged=False, raw_output={}
    )


def inspect_response(response_text: str) -> InspectionResult:
    return InspectionResult(
        risk_score=0.0, intent_label="normal",
        intent_description="Response inspection pending integration",
        flags=[], response_flagged=False, raw_output={}
    )
