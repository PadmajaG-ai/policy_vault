# Policy Vault

Captures the reasons behind enterprise system configuration before experts leave, and detects where written policy and live configuration have drifted apart.

## Folder layout

```
policy-vault/
├── DEMO_SCRIPT.md            ← the 3-minute demo; build only what it needs
├── data/expense/             ← domain pack #1 (synthetic, fictional company)
│   ├── policy.pdf / .md      ← Travel & Expense Policy v3.2 (the "written truth")
│   ├── config_rules.csv      ← configuration export in the generic rule shape
│   ├── tickets.json          ← 13 tickets: 5 explain rules, 8 are noise or vague
│   ├── expert_answers.json   ← simulated retired expert for the interview demo
│   └── ground_truth.json     ← ANSWER KEY — never give this to the agents
└── tools/check_data.py       ← verifies the answer key matches the data
```

## Generic rule shape (keep this — it is what makes new domain packs possible)

`rule_id, domain, entity, attribute, condition, value, unit, config_location, last_changed, changed_by`

The inventory pack later uses the same columns with `domain=inventory`.

## What is planted in the data

- 4 drifts between policy and configuration (D1–D4), 3 with a root cause hidden in tickets, 1 with none
- 8 aligned rules (for proving zero false alarms)
- 3 undocumented rules (U1–U3); U3 has a vague related incident (TKT-1135) the agent should connect
- 2 rules documented only in tickets (for the ask-why feature)
