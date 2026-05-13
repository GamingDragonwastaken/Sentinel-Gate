# 🛡️ SentinelGate — Enterprise AI Security Gateway

> *"Secure by design. Not by accident."*

SentinelGate is a real-time security gateway that sits between your enterprise applications and your AI models. Every prompt is inspected before it reaches the model, every response is checked before it reaches the user, and every interaction is logged to a tamper-evident audit trail — with zero changes to your existing application code.

---

## The Problem

Enterprise teams are deploying powerful AI models directly into their workflows — connected to internal systems, customer data, and sensitive documents — with no security layer in between. A single crafted prompt can extract customer records, bypass access controls, or leak confidential system instructions. Prompt injection is the #1 LLM vulnerability (OWASP LLM Top 10), and 68% of enterprises cite AI security as their #1 blocker to production deployment.

The tools to fix this have historically required weeks of engineering effort and expensive professional services contracts. SentinelGate changes that.

---

## What SentinelGate Does

**Inspect.** Every prompt is scored for risk before it reaches the model. SentinelGate uses Veea's Lobster Trap — an MIT-licensed prompt inspection proxy — to extract intent and generate a risk score in under a millisecond.

**Enforce.** Security policies are written in plain English by your team, interpreted by Gemini Flash, and enforced automatically on every request. No code required. No ML engineers needed.

**Explain.** When a request is blocked, Gemini Flash generates a full threat intelligence report: attack type, technique used, confidence score, remediation steps, and which compliance requirement it violated.

**Audit.** Every interaction — allowed or blocked — is logged with a prompt hash, risk score, decision, compliance citations, and timestamp. Export the full audit log as CSV for your compliance team.

---

## Key Features

- 🔍 **Real-time prompt inspection** via Veea Lobster Trap (sub-millisecond, MIT-licensed)
- 🧠 **Gemini-powered threat intelligence** — every block comes with a full explanation
- 📝 **Natural language policy authoring** — your security team writes rules in plain English
- 🏛️ **Pre-built compliance packs** — activate HIPAA, SOC2 Type II, or Standard Enterprise in one click
  - HIPAA: 37 rules · 45 CFR §§ 160, 162, 164
  - SOC2 Type II: 42 rules · AICPA Trust Services Criteria
  - Standard Enterprise: 24 rules · NIST 800-53 + OWASP LLM Top 10
- 👥 **Multi-agent monitoring** — track requests across billing, support, and research agents
- 📊 **Live audit dashboard** — charts, risk breakdowns, agent activity, CSV export
- 🔄 **Response inspection** — outgoing model responses are scanned too, not just incoming prompts

---

## Tech Stack

| Tool | Purpose | Cost |
|---|---|---|
| [Veea Lobster Trap](https://github.com/veeainc/lobstertrap) | Prompt inspection proxy | Free (MIT) |
| Gemini Flash | Policy engine + threat intelligence | Free tier |
| Streamlit | Web UI and hosting | Free |
| SQLite | Audit log database | Free (built-in) |
| Python | Everything else | Free |

Total infrastructure cost: **$0**

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/GamingDragonwastaken/Sentinel-Gate.git
cd sentinelgate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your environment
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_key_from_aistudio.google.com

# 4. Run the app
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

On first launch, SentinelGate automatically loads three starter policies and activates the Standard Enterprise compliance pack. No setup required.

---

## How It Works

```
User Prompt
    │
    ▼
Lobster Trap Inspection     ← intent extraction, risk scoring (0.0–1.0)
    │
    ▼
Compliance Engine           ← HIPAA / SOC2 / Enterprise regex rules
    │
    ▼
NL Policy Engine            ← Gemini checks against plain-English policies
    │
    ▼
Decision Gate
    ├── BLOCK → Gemini Threat Intelligence Report + Audit Log
    └── ALLOW → Protected LLM → Response Inspection → Audit Log
```

---

## Live Demo

🔗 **[sentinel-gate.streamlit.app](https://sentinel-gate.streamlit.app/)**

The demo loads with three active security policies pre-configured. Use the **"Load Attack Scenario"** dropdown to run pre-scripted attack examples and watch SentinelGate block them in real time.

---

## Deployment

SentinelGate deploys to [Streamlit Community Cloud](https://streamlit.io/cloud) for free. Set `GEMINI_API_KEY` in your Streamlit secrets and connect your GitHub repository.

> **Note:** SQLite data persists within a session but resets on redeployment. For production use, swap SQLite for PostgreSQL or Supabase.

---

## Hackathon Context

Built for the **[Transforming Enterprise Through AI Hackathon](https://lablab.ai)** hosted by lablab.ai (May 2026). Submitted to **Track 1: Agent Security & AI Governance**, sponsored by Veea.

SentinelGate uses Veea's Lobster Trap as its core inspection engine — the exact technology the track was designed to showcase.

---

## License

MIT — see [LICENSE](LICENSE) for details.
