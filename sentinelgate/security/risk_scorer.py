"""Risk Scorer — converts an inspection result into a numeric risk score [0, 1].

Consumes the dict produced by `inspector.inspect_prompt` and returns a float
where 0.0 is benign and 1.0 is maximum risk. The threshold lives in the env
var `RISK_THRESHOLD` and is read by the orchestrator that calls this.

TODO(learning): implement `score_risk`.

Design questions worth thinking through:
  - Weight LLM-judged risk vs. rule-based flags?
  - Should certain flags (e.g. `override_attempt`) saturate the score to 1.0?
  - Calibrate so the demo scenarios in `demo/scenarios.py` land in the expected
    risk buckets (normal <0.3, injection >0.8, exfil >0.7, financial ~0.7).
"""

from __future__ import annotations


def score_risk(inspection: dict) -> float:
    """Return a risk score in the closed interval [0.0, 1.0].

    TODO: implement.
    """
    raise NotImplementedError("score_risk is not yet implemented")
