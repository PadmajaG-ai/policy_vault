# Policy Vault

**Captures the reasons behind enterprise system configuration before experts leave, and detects where written policy and live configuration have drifted apart.**

Other tools search what was written down. Policy Vault captures what was never written, and checks the policy against what the system actually does.

Live demo: https://policy-vault-240640518337.asia-south1.run.app  
Demo video (3:50): https://drive.google.com/file/d/19nF2-_emvN84OQLu0H5qE1JFzui3Pq-3/view?usp=sharing

## The problem

Expense, procurement and finance systems are configured over years by a few experts. When they leave:
- nobody knows **why** a rule, approval step or hidden field exists, so teams are afraid to change anything;
- the **written policy and the live configuration quietly disagree**, which leaks money and breaks controls that auditors were told exist.

## What it does

| Step | What happens | Who does what |
|---|---|---|
| **1. Drift detection** | Reads the policy PDF, compares every rule with the configuration export, and finds the root cause of each mismatch in the ticket history | Gemini reads the policy · **Python compares the values** · Gemini links tickets |
| **2. Gap finder + expert interview** | Finds rules nobody can explain, then interviews the expert with evidence ("The field was hidden 3 days after TKT-1135 reported ERP posting failures. Related?") | Code finds gaps and date clues · Vertex AI Search finds related tickets · Gemini asks and structures the answer |
| **3. Decision Records** | The expert's answer becomes a verified record: what, why, who, when, sources, risk if removed | Human verifies · Firestore stores · Vertex AI Search indexes |
| **4. Ask why** | "Can I re-enable this field?" is answered with citations to tickets, policy and Decision Records | Gemini grounded on Vertex AI Search |

## Results on the demo data (measured against a hidden answer key)

| Metric | Expense pack | Inventory pack (same engine) |
|---|---|---|
| Planted drifts detected | **4 / 4** | **2 / 2** |
| False alarms | **0** (8 / 8 aligned confirmed) | **0** (7 / 7 aligned confirmed) |
| Root causes found in tickets | **4 / 4** (3 tickets, 1 correctly "no record, ask the expert") | **2 / 2** (1 ticket, 1 "ask the expert") |
| Retrieval (Vertex AI Search) | 3 / 3 expected tickets ranked first | |
| Interview clue | R-014 linked to TKT-1135 | INV-010 linked to TKT-2058 |
| Ask Why | correct on all test questions, including a trap question with no evidence | answers the MAT-7730 question before any interview |

Measured with gemini-3.5-flash. Each pack's answer key (`data/<pack>/ground_truth.json`) is read only by `tools/evaluate.py` and the tests, and never reaches a prompt.

## Architecture

```
Browser ──► Cloud Run (Flask, one service)
              ├─ extract.py   Gemini reads policy.pdf → rules in the generic rule shape
              ├─ drift.py     deterministic comparison + Gemini root cause from tickets
              ├─ gaps.py      gap finder, interview question, Decision Record draft
              ├─ records.py   Decision Records
              └─ ask_why.py   grounded answers with sources
                    │
     ┌──────────────┼───────────────────┬──────────────────┐
  Gemini on      Vertex AI Search     Firestore          Cloud Storage
  Vertex AI      (policy, tickets,    (Decision          (search corpus)
                  Decision Records)    Records)
```

## Design decisions

1. **AI reads, code compares.** Gemini turns policy text into structured rules; plain Python compares values (including Indian digit grouping like `1,00,000` and unit checks). An LLM can mis-compare numbers; code can't, and an auditor can read an `if` statement.
2. **No anchoring.** Gemini sees the configuration's rule *slots* but never its *values*, so the policy value it extracts can only come from the policy.
3. **The model can only cite what exists.** Rule IDs and ticket IDs are enums in the JSON schema, and every answer is validated again in code. Ask Why sources come from grounding metadata, not from the model's text.
4. **"I don't know" is a valid answer.** Every step has an explicit no-evidence path ("No record found, ask the expert"), and tests include trap questions.
5. **Generic rule shape.** `rule_id, domain, entity, attribute, condition, value, unit, config_location, last_changed, changed_by`. Nothing expense-specific is hardcoded, so a new domain (inventory, procurement) is a new data pack.
6. **Demo never breaks.** Search has a timeout, the interview falls back to date-based clues, records fall back to a local file, and a failed live scan shows the last saved scan.

## Run it locally

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
gcloud auth application-default login
copy .env.example .env          # set project, model and data store ID
python main.py                  # http://localhost:8080
```

Tests:

```bash
pytest                 # 83 offline tests: comparison logic, guard-rails, both packs, app flow, hygiene (no cloud calls)
pytest -m live -v      # 13 live end-to-end checks against Gemini + Vertex AI Search (proves the demo claims)
```

Command-line tools:

```bash
python drift.py data/expense    # full scan → output/drift_report.json
python tools/evaluate.py        # score against the answer key
python tools/test_search.py     # retrieval check
python tools/test_ask_why.py    # Ask Why checks, including a trap question
```

## Data

All data is synthetic. Kestrel Components Pvt Ltd and every person in it are fictional.

```
data/expense/
├── policy.pdf / policy.md   Travel & Expense Policy v3.2
├── config_rules.csv         configuration export (17 rules)
├── tickets.json             13 tickets: some explain rules, most are noise
├── expert_answers.json      the simulated retired expert (a human role in the demo)
└── ground_truth.json        answer key, evaluation only

data/inventory/              domain pack #2, same files: Inventory Policy v2.1, 12 rules, 9 tickets
```

The demo video is built by `demo/` (Playwright drives the app, Google Cloud Text-to-Speech narrates); see `demo/README.md`.

## Beyond the hackathon

- More domain packs: procurement (Ariba-style), finance, sales discounts (inventory already runs on the same engine)
- Real connectors: SAP Concur, SAP Ariba, S/4HANA configuration APIs; ServiceNow/Jira tickets
- Continuous monitoring: re-scan on every policy or configuration change
- Change impact check: warn which Decision Records a planned change touches
- An SAP BTP version (AI Core / Generative AI Hub, Joule) as a knowledge-retention layer for S/4HANA migrations
