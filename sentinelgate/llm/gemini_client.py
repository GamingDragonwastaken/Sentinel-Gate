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

import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash"
LOBSTER_PORT = int(os.getenv("LOBSTER_PORT", "8765"))
LOBSTER_BASE_URL = f"http://localhost:{LOBSTER_PORT}/v1"


def _configure() -> str | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            "[gemini_error] Missing API key. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
            "in your environment/.env and retry."
        )
    genai.configure(api_key=api_key)
    return None


def _model(system_prompt: str | None = None):
    kwargs = {}
    if system_prompt:
        kwargs["system_instruction"] = system_prompt
    return genai.GenerativeModel(MODEL_NAME, **kwargs)


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


def call_gemini(prompt: str, system_prompt: str | None = None) -> str:
    """Send `prompt` to Gemini Flash and return the response text.

    Any exception (auth, quota, network) is caught and returned as an
    error string so the caller can surface it without crashing the UI.
    """
    config_error = _configure()
    if config_error:
        return config_error
    try:
        response = _model(system_prompt).generate_content(prompt)
        return getattr(response, "text", "") or ""
    except Exception as exc:  # pragma: no cover - network-dependent
        return _format_exception(exc)


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction — strips ```json fences if present."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return json.loads(cleaned)


def call_gemini_json(prompt: str, system_prompt: str | None = None) -> dict:
    """Call Gemini Flash and parse the response as JSON.

    On any failure (API error or unparseable response), returns
    `{"error": "parse_failed", "raw": <text>}` so callers can decide
    how to degrade.
    """
    raw = call_gemini(prompt, system_prompt=system_prompt)
    try:
        return _extract_json(raw)
    except (ValueError, TypeError):
        return {"error": "parse_failed", "raw": raw}


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
