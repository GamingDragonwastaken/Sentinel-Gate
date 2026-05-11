"""Policy Engine — evaluates a prompt against natural-language policies.

Policies are loaded from `demo/sample_policies.json` (or user-supplied via the
Policy Manager UI). Each policy has a `name` and a `natural_language`
description; the engine asks Gemini to judge whether the prompt violates any
of them and returns a structured decision.

TODO(learning): implement `evaluate_policies`.

Suggested return shape:
    {
        "violated": bool,
        "policy_name": str | None,
        "explanation": str,
    }

Implementation hints:
  - Compose a single Gemini call that lists all policies and asks for the
    first one violated (if any) — cheaper than one call per policy.
  - Use `llm.gemini_client.call_gemini_json` and instruct the model to
    return exactly the shape above.
"""

from __future__ import annotations


def evaluate_policies(prompt: str, policies: list[dict]) -> dict:
    """Check `prompt` against the supplied policies; return a verdict dict.

    TODO: implement.
    """
    raise NotImplementedError("evaluate_policies is not yet implemented")
