"""Thin wrapper around Google's Gemini Flash model.

Exposes two helpers:
- `call_gemini` for free-text completion
- `call_gemini_json` for structured (JSON-mode) responses used by the
  inspector / risk-scorer / policy engine.
"""

import json
import os
import re

import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash"


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
