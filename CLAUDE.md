# Policy Vault — Project Context

https://policy-vault-240640518337.asia-south1.run.app - deployment url

> This file gives an AI coding assistant (and any teammate) the full context of the project.
> Keep it at the repo root. Update the **Status** section at the end of every working session.

## 1. Who I am and how to work with me

- Solo builder: 10 yrs SAP Ariba, 5 yrs SAP Concur. Comfortable with Python.
- Goals: win the **Hack2skill Google Builder Cup**, build a portfolio for **GenAI / SAP BTP AI** roles, grow toward **Solution Architect**, possibly a PhD in AI/ML later.
- Assistant role: **mentor, not just code generator.** Explain the *why* behind design choices, challenge weak decisions, point out trade-offs, and prefer teaching me to write the code over writing everything for me.
- Keep solutions simple. Every extra service must justify its time cost.

## 2. The problem

In large enterprises, rule-driven systems (expense, procurement, inventory, finance) are configured over years by a few experts. When they leave:
- Nobody knows **why** rules, approval steps, hidden fields or integrations exist. Teams fear changing anything.
- **Written policy and live configuration silently drift apart**, causing compliance gaps and money leakage.

Tools like Confluence, Atlassian Rovo, Glean or Copilot can only **retrieve** what someone wrote down. The most valuable knowledge was never written down.

## 3. The solution

**Policy Vault** captures the reasons behind enterprise system configuration before experts leave, and detects where policy and configuration disagree.

Three core capabilities:
1. **Drift Detection** — extract rules from the policy document, compare against the configuration export, explain each mismatch and find its root cause in old tickets.
2. **Gap Finder + Expert Interview (elicitation)** — find configuration rules with no documented reason, interview the expert (connecting clues such as related incident tickets), and save the answer as a verified Decision Record.
3. **Ask Why** — answer "Why does this rule exist? Can I change it?" with provenance: who decided, when, source, and risk if removed.

**Differentiator in one line:** other tools search existing knowledge; Policy Vault *creates* knowledge that never existed in writing, and checks policy against reality.

## 4. Scope for the hackathon (MVP)

**In scope**
- Domain pack #1: **Expense** (Concur-style), synthetic data in `data/expense/`.
- The 3 capabilities above, a simple web UI, deployed on **Cloud Run** (mandatory).
- Evaluation against `ground_truth.json` (target: 4/4 drifts found, 0 false alarms).

**Stretch (only after the core flow works, 9–11 Oct)**
- Domain pack #2: **Inventory** (safety stock, slow-moving stock review, auto-reorder exclusions).
- Vertex AI Search, Agent Engine.

**Out of scope**
- Real Ariba/Concur/ERP connections, login/multi-tenant, voice, mobile app, real client data (synthetic only, always).

The demo script `DEMO_SCRIPT.md` is the source of truth. Build only what it needs.

## 5. Architecture

```
Web UI ──► Agent backend (one Cloud Run service, Python, ADK + Gemini)
             ├─ Drift Detector      (Gemini extracts → Python compares → Gemini explains)
             ├─ Gap Finder + Interviewer
             └─ Ask-Why (answers with sources)
                 │
     ┌───────────┼──────────────────┐
  Firestore   Cloud Storage     Gemini on Vertex AI
  (rules,     (uploaded policy  (reads PDFs directly;
  decision    PDF, config CSV,   no Document AI needed)
  records)    tickets)
```

### Google Cloud stack

| Service | Purpose |
|---|---|
| Cloud Run | Hosts UI + agents in one service (mandatory for submission) |
| Gemini on Vertex AI | Extraction, reasoning, interviews, explanations |
| ADK (Agent Development Kit) | Agent structure and tools |
| Firestore | Rules and Decision Records |
| Cloud Storage | Uploaded source files |

- Project ID: `policy-vault-510216` · Cloud Run region: `asia-south1` (Mumbai)
- Gemini region is configured separately (use a region where the chosen model is available).
- Local code authenticates with Application Default Credentials (`gcloud auth application-default login`). On Cloud Run the service account is used.

## 6. Key design principles (architect decisions)

1. **"AI reads, code compares."** Gemini extracts policy rules into structured form and explains results. The actual comparison of values is plain, deterministic Python. LLMs can mis-compare numbers; code can't.
2. **The Decision Record is the core asset**, not the AI. Everything captured is stored in one consistent structure.
3. **Generic rule shape** so new domains are plug-in packs with no code changes. Never hardcode expense-specific logic.
4. **Evidence over claims.** Every finding cites its source (policy section, rule ID, ticket ID, interview).
5. **Deploy continuously.** Redeploy to Cloud Run after every working feature; check the live link daily.

## 7. Data model

### Rule (generic shape; matches `config_rules.csv`)
`rule_id, domain, entity, attribute, condition, value, unit, config_location, last_changed, changed_by`

Policy rules extracted by Gemini use the same fields, plus `source` (policy section) and `source_type = "policy"`.

### Decision Record
```json
{
  "record_id": "DR-0001",
  "rule_id": "R-014",
  "domain": "expense",
  "what": "Vehicle registration field hidden on mileage form",
  "why": "Field overflowed a 10-character ERP interface field and broke GL posting",
  "decided_by": "r.kumar with ERP integration team",
  "decided_on": "2021-09-06",
  "sources": ["TKT-1135", "interview:R. Kumar"],
  "risk_if_removed": "high",
  "confidence": "high",
  "verified_by_expert": true,
  "created_at": "..."
}
```

### Drift finding
`rule_id, topic, policy_value, config_value, unit, direction, policy_source, root_cause, root_cause_sources, business_risk`

## 8. Repository layout

```
policy-vault/
├── CLAUDE.md             ← this file
├── DEMO_SCRIPT.md        ← 3-minute demo; source of truth for scope
├── README.md
├── main.py / Dockerfile / requirements.txt   ← Cloud Run app
├── data/expense/         ← synthetic domain pack #1
│   ├── policy.pdf, policy.md
│   ├── config_rules.csv
│   ├── tickets.json
│   ├── expert_answers.json   ← simulated retired expert
│   └── ground_truth.json     ← ANSWER KEY: never pass to agents or prompts
└── tools/check_data.py   ← data consistency check; base for the eval harness
```

### Planted in the expense data
- 4 drifts: D1 meal limit (R-001), D2 receipt threshold (R-003), D3 metro hotel cap (R-004), D4 controller approval threshold (R-008).
- 8 aligned rules (to prove zero false alarms).
- 3 undocumented rules: R-012, R-013, R-014 (R-014 links to vague incident TKT-1135).
- 2 rules documented only by tickets: R-015, R-016.

## 9. Scaling roadmap (beyond the hackathon)

1. **More domain packs:** inventory, procurement (Ariba-style), finance (credit terms, payment terms), sales (discount approvals).
2. **Real connectors:** read configuration via APIs of SAP Concur, SAP Ariba, S/4HANA; tickets from ServiceNow/Jira; decisions from Teams/Slack/email.
3. **Continuous drift monitoring:** re-scan on every policy or configuration change (Pub/Sub events) instead of one-off uploads.
4. **Change impact check:** before a config change is made, warn which Decision Records and risks it touches.
5. **SAP BTP version:** rebuild on SAP BTP with SAP AI Core / Generative AI Hub and Joule integration, positioned as a knowledge-retention layer for S/4HANA migrations. Strong portfolio piece for SAP Business AI roles.
6. **Enterprise hardening:** SSO, role-based access, audit trail of who verified what, data residency.
7. **Research angle:** automatic detection of policy–configuration inconsistency and targeted knowledge elicitation (which question to ask an expert next) are publishable problems.

## 10. Timeline (deadline 18 Oct 2026; submit on 17 Oct)

| Dates | Milestone |
|---|---|
| 30 Sep | Data pack + demo script ✅; hello-world on Cloud Run |
| 1–3 Oct | Policy extraction with Gemini; drift detection; explanation; deploy |
| 4–6 Oct | Decision Records in Firestore; Ask-Why with sources |
| 7–9 Oct | Gap Finder + Interviewer; **full flow deployed (checkpoint)** |
| 10–11 Oct | Evaluation vs ground truth, fixes; optional inventory pack |
| 12 Oct | **Feature freeze** |
| 13–16 Oct | UI polish, demo video, pitch deck, README, architecture diagram |
| 17 Oct | **Submit**, test live link from another device |
| 18 Oct | Emergency buffer only |

Time budget: ~3 hrs weekdays, 5+ hrs weekends. If a milestone slips by a day, cut scope; never cut drift detection.

## 11. Coding conventions

- Python 3.12, Flask (for now), small focused modules: `extract.py`, `drift.py`, `records.py`, `agents/`.
- Model names, project ID and regions come from environment variables, never hardcoded.
- Structured output from Gemini uses a JSON schema; always validate before use.
- Every new feature gets a quick check against `ground_truth.json`.
- Never commit secrets or keys. No real client data anywhere.

## 12. Status (update every session)

- **Last updated:** 17 Oct 2026 (submission day)
- **Done:** extraction, drift + root cause, Vertex AI Search, Ask Why, Gap Finder + interview, Decision Records (Firestore with local fallback), one-page UI, README, test suite.
- **Verified (17 Oct, gemini-3.5-flash):** `pytest` 64/64 offline; `pytest -m live` 9/9: 4/4 drifts, 0 false alarms, 4/4 root causes, search 3/3, R-014 -> TKT-1135 interview, Ask Why cites DR-0001 and admits no rationale on the USD 75 trap.
- **Remaining today:** create Firestore DB + Cloud Run IAM (aiplatform.user, discoveryengine.editor, datastore.user); deploy; warm-up run on live URL; demo video; submit.
- **Cut:** inventory pack, ADK, Agent Engine, file upload.
- **Problems log:** pip/Python SSL errors -> `pip install --use-feature=truststore`. Console bucket import: project Owner needs explicit `roles/storage.objectViewer`. Extraction prompt example used 100000 (= D4 config value), caught by test and fixed. conftest placeholders overrode .env (live tests hit "test-project"), fixed by loading .env first. R-011 `economy_class` vs `economy` handled by unit-word-insensitive compare.
