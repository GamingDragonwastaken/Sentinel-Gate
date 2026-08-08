"""Thin wrapper around Google's Gemini Flash model.

Exposes three helpers:
- `call_gemini` for free-text completion (native Gemini SDK)
- `call_gemini_json` for structured (JSON-mode) responses used by the
  inspector / risk-scorer / policy engine
- `call_gemini_via_lobster` for completion routed through the Lobster Trap
  proxy so traffic gets DPI'd both ways
"""

import json
import os
import re
import time

from google import genai
from google.genai import types

# Rate-limit retry policy. One retry (= 2 total attempts), 2-second pause.
_RATE_LIMIT_MAX_RETRIES = 1
_RATE_LIMIT_DELAY_S = 2.0
_RATE_LIMIT_SENTINEL = "[rate_limited] Request could not be processed"

MODEL_NAME = "gemini-2.5-flash"
LOBSTER_PORT = int(os.getenv("LOBSTER_PORT", "8765"))
LOBSTER_BASE_URL = f"http://localhost:{LOBSTER_PORT}/v1"


def _api_key() -> str | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            None
        )
    return api_key


def _client():
    api_key = _api_key()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _missing_key_message() -> str:
    return (
        "[gemini_error] Missing API key. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
        "in your environment/.env and retry."
    )


def _format_exception(exc: Exception) -> str:
    text = str(exc)
    if "SERVICE_DISABLED" in text or "has not been used in project" in text:
        return (
            "[gemini_error] Gemini API is disabled for this key's Google project. "
            "Enable generativelanguage.googleapis.com for that project, then retry."
        )
    if "API_KEY_SERVICE_BLOCKED" in text:
        return (
            "[gemini_error] This API key is blocked from Gemini API. "
            "Update API-key restrictions or use a Gemini-enabled key."
        )
    if "API key not valid" in text or "API_KEY_INVALID" in text:
        return (
            "[gemini_error] Invalid Gemini API key. Replace GEMINI_API_KEY with "
            "a valid key and retry."
        )
    return f"[gemini_error] {type(exc).__name__}: {exc}"


def _is_rate_limit_error(exc: Exception) -> bool:
    """True when the exception text looks like a Google rate-limit / quota error."""
    msg = str(exc).lower()
    return (
        "429" in msg
        or "quota" in msg
        or "rate limit" in msg
        or "resourceexhausted" in msg
    )


def call_gemini(
    prompt: str,
    system_prompt: str | None = None,
    *,
    json_mode: bool = False,
) -> str:
    """Send `prompt` to Gemini Flash and return the response text.

    On a 429 / quota error, sleeps `_RATE_LIMIT_DELAY_S` and retries once.
    After two failed rate-limit attempts, returns the `_RATE_LIMIT_SENTINEL`
    string so the caller can distinguish quota exhaustion from other
    failures. Any other exception (auth, network, safety block) is caught
    and returned as a `[gemini_error] ...` string. Never raises.
    """
    client = _client()
    if client is None:
        return _missing_key_message()

    config_kwargs = {}
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    last_exc: Exception | None = None
    for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )
            return getattr(response, "text", "") or ""
        except Exception as exc:  # pragma: no cover - network-dependent
            last_exc = exc
            if attempt < _RATE_LIMIT_MAX_RETRIES and _is_rate_limit_error(exc):
                time.sleep(_RATE_LIMIT_DELAY_S)
                continue
            break

    if last_exc is not None and _is_rate_limit_error(last_exc):
        return _RATE_LIMIT_SENTINEL
    if last_exc is not None:
        return _format_exception(last_exc)
    return "[gemini_error] Unknown failure"


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction — strips ```json fences if present."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return json.loads(cleaned)


def call_gemini_json(prompt: str, system_prompt: str | None = None) -> dict:
    """Call Gemini Flash and parse the response as JSON.

    Returns one of:
      - the parsed dict on success
      - `{"error": "api_failed", "raw": <text>}` if the SDK / API never
        produced model output (auth, quota, network, safety block)
      - `{"error": "parse_failed", "raw": <text>}` if the model replied
        but the reply wasn't valid JSON

    Callers should treat both error types the same for *security*
    decisions (fail-closed) but can use the distinction for logging,
    metrics, and retry strategy.
    """
    raw = call_gemini(prompt, system_prompt=system_prompt, json_mode=True)
    if raw.startswith("[gemini_error]"):
        return {"error": "api_failed", "raw": raw}
    if raw.startswith("[rate_limited]"):
        return {"error": "api_failed", "raw": raw}
    try:
        return _extract_json(raw)
    except (ValueError, TypeError):
        return {"error": "parse_failed", "raw": raw}


_EXPLAIN_THREAT_PROMPT = (
    "You are an enterprise AI security analyst. A prompt was blocked by the "
    "gateway. Produce a forensic report for the security team.\n"
    "Return ONLY JSON: {"
    '"attack_type": "<short label, e.g. Prompt Injection, Data Exfiltration>",'
    '"confidence": <integer 0-100>,'
    '"severity": "<Low|Medium|High|Critical>",'
    '"explanation": "<one-paragraph plain-English summary>",'
    '"technique": "<one sentence on the attack technique>",'
    '"remediation": "<actionable next-step for the security team>",'
    '"compliance_impact": "<one sentence on regulatory/compliance implications>"'
    "}"
)


def explain_threat(prompt: str, intent_label: str) -> dict:
    """Produce a forensic threat report for a blocked prompt.

    Returns a dict with the seven fields the chat panel expects. If Gemini
    is unavailable (quota / network) or returns unparseable output, returns
    a placeholder dict labelled with the supplied intent so the UI still
    renders cleanly.
    """
    user_prompt = (
        f"BLOCKED PROMPT:\n{prompt}\n\nDETECTED INTENT: {intent_label}"
    )
    verdict = call_gemini_json(user_prompt, system_prompt=_EXPLAIN_THREAT_PROMPT)

    if "error" in verdict:
        kind = verdict.get("error")
        return {
            "attack_type": (intent_label or "unknown").replace("_", " ").title(),
            "confidence": 0,
            "severity": "Unknown",
            "explanation": f"Threat intelligence unavailable ({kind}).",
            "technique": "Analysis pending — Gemini API did not respond.",
            "remediation": "Retry when API quota / network is available.",
            "compliance_impact": "Unknown — analysis incomplete.",
        }

    try:
        confidence = int(verdict.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0

    return {
        "attack_type": str(verdict.get("attack_type") or "Unknown"),
        "confidence": max(0, min(100, confidence)),
        "severity": str(verdict.get("severity") or "Unknown"),
        "explanation": str(verdict.get("explanation") or ""),
        "technique": str(verdict.get("technique") or ""),
        "remediation": str(verdict.get("remediation") or ""),
        "compliance_impact": str(verdict.get("compliance_impact") or ""),
    }


def call_gemini_via_lobster(
    prompt: str,
    system_prompt: str | None = None,
) -> str:
    """Route a Gemini call through the Lobster Trap proxy.

    Uses the OpenAI client pointed at the local Lobster Trap listener;
    Lobster proxies upstream to Gemini's OpenAI-compatible endpoint and
    performs ingress/egress DPI on the traffic in both directions.

    Falls back to `call_gemini()` if Lobster Trap isn't reachable
    (connection refused / not running) so the gateway stays usable.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            "[gemini_error] Missing API key. Set GEMINI_API_KEY (or "
            "GOOGLE_API_KEY) in your environment/.env and retry."
        )

    try:
        from openai import OpenAI
    except ImportError:
        return call_gemini(prompt, system_prompt=system_prompt)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        client = OpenAI(base_url=LOBSTER_BASE_URL, api_key=api_key, timeout=15.0)
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        choice = completion.choices[0]
        return (choice.message.content or "").strip()
    except Exception as exc:
        text = str(exc)
        if any(s in text.lower() for s in ("connection refused", "connect call failed", "max retries")):
            return call_gemini(prompt, system_prompt=system_prompt)
        return _format_exception(exc)
