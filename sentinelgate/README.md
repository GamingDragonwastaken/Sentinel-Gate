# 🛡️ SentinelGate — Enterprise AI Security Gateway

> *"Secure by design. Not by accident."*

SentinelGate is a real-time AI security gateway that inspects every LLM prompt
using Veea's Lobster Trap, enforces plain-English security policies via Gemini
Flash, and logs a tamper-evident audit trail — zero code changes required by
the protected application.

---

## The Problem

Enterprises wiring LLMs into customer support, internal copilots, and agentic
workflows are shipping a new attack surface without a defense. Prompt injection
turns helpful agents into data leakers; a single careless prompt can exfiltrate
PII, financial figures, or credentials. There's no standardized defense layer
between the application and the model — every team builds ad-hoc filtering, or
nothing at all.

## The Solution

SentinelGate sits between your app and the LLM as a transparent inspection
proxy. Every inbound prompt is scanned for adversarial patterns and policy
violations; every outbound response is scanned for accidental disclosure;
every decision is logged with the compliance citation that triggered it.
Protected applications keep their existing OpenAI-compatible client — they
just point its base URL at the gateway.

---

## Key Features

- 🔍 **Real-time prompt inspection** — Veea Lobster Trap (Go, MIT) for sub-millisecond scanning
- 🏛️ **Pre-built compliance packs** — HIPAA, SOC 2, and Enterprise baseline rules
- 🤖 **Natural language policy authoring** — write rules in plain English; Gemini Flash extracts the enforcement keywords
- 🧠 **Gemini threat intelligence** — every blocked request gets a forensic explanation, technique label, and remediation guidance
- 📋 **Full audit trail** — every decision logged to SQLite with compliance citations, agent attribution, and processing-time metrics
- 👥 **Multi-agent monitoring** — track requests per agent (billing, support, research) to isolate compromised endpoints
- 🛡️ **Fail-closed posture** — if the analyzer can't certify a prompt, the gateway blocks rather than passes through

---

## Tech Stack

| Tool | Purpose | Cost |
|---|---|---|
| [Veea Lobster Trap](https://github.com/veeainc/lobstertrap) | Prompt inspection proxy | Free (MIT) |
| [Gemini Flash](https://ai.google.dev/) | Policy engine + threat intelligence | Free tier available |
| [Streamlit](https://streamlit.io/) | Web UI | Free |
| [SQLite](https://www.sqlite.org/) | Audit database | Free (built-in) |
| Python 3.10+ | Everything | Free |

---

## Quick Start

```bash
git clone https://github.com/YOURUSERNAME/sentinelgate.git
cd sentinelgate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add your GEMINI_API_KEY from https://aistudio.google.com/
streamlit run app.py
```

The app launches at `http://localhost:8501`. The first run auto-seeds three
sample policies and activates the Standard Enterprise compliance pack. Open
the **Chat & Inspect** tab and try the *Load Attack Scenario* dropdown to see
the gateway block injection, exfiltration, and policy-violation prompts.

---

## Architecture

```
       ┌────────────────────────────────────────────────────────────┐
       │                       SentinelGate                          │
       │                                                             │
prompt ─┼─► Lobster Trap (DPI)  ─►  Compliance check  ─►            │
       │      │                       │                 │           │
       │      └─► (if available)      └─► NL Policy ────┤           │
       │                                  engine        │           │
       │                                                ▼           │
       │                                          Decision gate     │
       │                                          │           │     │
       │                                       BLOCK        ALLOW   │
       │                                          │           │     │
       │                                          │           ▼     │
       │                                          │       Gemini    │
       │                                          │       (via      │
       │                                          │       Lobster)  │
       │                                          │           │     │
       │                                          ▼           ▼     │
       │                                       Audit log (SQLite)   │
       └────────────────────────────────────────────────────────────┘
```

1. **Prompt arrives** — gateway intercepts before reaching the LLM
2. **Inspect** — Lobster Trap performs DPI; falls back to Gemini-as-judge if absent
3. **Compliance check** — active packs scan for HIPAA / SOC 2 / enterprise rule hits
4. **Policy check** — natural-language operator policies evaluated via Gemini
5. **Decision** — BLOCK on any failure, ALLOW only when all stages pass
6. **Route to LLM (if ALLOW)** — through Lobster Trap, with egress DPI on the response
7. **Audit** — every decision persisted with prompt hash, risk score, citation, timing

---

## Live Demo

🔗 [SentinelGate Live Demo](https://sentinel-ga-xprp5cobtornlij8o9yawu.streamlit.app/)

---

## Hackathon

Built for the [Transforming Enterprise Through AI Hackathon](https://lablab.ai)
(lablab.ai, May 2026). Track 1: Agent Security & AI Governance (Veea).

---

## License

MIT — see [LICENSE](LICENSE).
