"""Policy extraction: Gemini reads the policy PDF and returns rules in the generic rule shape.

Design (see CLAUDE.md section 6, "AI reads, code compares"):
- Gemini gets the config's rule *keys* (entity / attribute / condition / unit), never the
  configured *values*, so it cannot anchor on what the system currently does.
- matched_rule_id is an enum built from the uploaded CSV, plus "none" for policy rules
  the system does not enforce. Nothing domain-specific is hardcoded here.
- Every response is validated in code before anyone uses it.

Usage:  python extract.py data/expense/policy.pdf data/expense/config_rules.csv
"""

import csv
import json
import sys
from pathlib import Path

from google.genai import types

import gemini

NO_MATCH = "none"
CONFIDENCE = ["high", "medium", "low"]


def load_config_keys(csv_path):
    """Read the config export but keep only what describes a rule, not its value."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = [
        {k: r[k] for k in ("rule_id", "domain", "entity", "attribute", "condition", "unit", "config_location")}
        for r in rows
    ]
    return keys


def build_schema(rule_ids):
    rule = {
        "type": "OBJECT",
        "properties": {
            "policy_source": {"type": "STRING", "description": "Policy section number, e.g. '5.1'"},
            "quote": {"type": "STRING", "description": "Exact sentence from the policy that states the rule"},
            "topic": {"type": "STRING", "description": "Short human label, e.g. 'Domestic meal limit'"},
            "matched_rule_id": {"type": "STRING", "enum": rule_ids + [NO_MATCH]},
            "value": {"type": "STRING", "description": "Value in the config's form: plain number without commas or currency, true/false, or a lowercase snake_case word"},
            "unit": {"type": "STRING", "description": "Unit in the config's notation, e.g. 'INR/day'"},
            "match_confidence": {"type": "STRING", "enum": CONFIDENCE},
        },
        "required": ["policy_source", "quote", "topic", "matched_rule_id", "value", "unit", "match_confidence"],
    }
    return {
        "type": "OBJECT",
        "properties": {"policy_rules": {"type": "ARRAY", "items": rule}},
        "required": ["policy_rules"],
    }


def build_prompt(keys):
    key_lines = "\n".join(
        f"{k['rule_id']} | {k['entity']} | {k['attribute']} | {k['condition']} | unit {k['unit']} | {k['config_location']}"
        for k in keys
    )
    return f"""You are reading a company policy document. Extract every rule in it that states a
checkable limit, threshold, rate, approval requirement, deadline or yes/no permission.

The company's system configuration contains these rule slots
(rule_id | entity | attribute | condition | unit | where it is configured):
{key_lines}

For each policy rule:
- Set matched_rule_id to the slot that governs exactly the same thing under the same condition.
- If no slot governs it, use "{NO_MATCH}". Do not force a rule onto a slot that is only similar.
- Take the value ONLY from the policy text. Write it in the slot's form: a plain number
  (1250, not "INR 1,250"; 300000, not "3,00,000"), true/false, or a lowercase snake_case word.
- Write the unit in the slot's notation.
- Quote the policy sentence exactly and give its section number.
- Use match_confidence "low" when you are unsure the slot is the same rule.
"""


def validate(result, rule_ids):
    """Reject anything malformed; return (rules, problems)."""
    allowed = set(rule_ids) | {NO_MATCH}
    rules, problems = [], []
    seen = {}
    for r in result.get("policy_rules", []):
        rid = r.get("matched_rule_id")
        if rid not in allowed:
            problems.append(f"unknown rule_id {rid!r} for section {r.get('policy_source')}")
            continue
        if rid != NO_MATCH and rid in seen:
            problems.append(f"{rid} matched twice (sections {seen[rid]} and {r.get('policy_source')})")
            continue
        if rid != NO_MATCH:
            seen[rid] = r.get("policy_source")
        r["source_type"] = "policy"
        rules.append(r)
    return rules, problems


def extract_policy_rules(policy_pdf, config_csv):
    keys = load_config_keys(config_csv)
    rule_ids = [k["rule_id"] for k in keys]

    result = gemini.generate_json(
        [
            types.Part.from_bytes(data=Path(policy_pdf).read_bytes(), mime_type="application/pdf"),
            build_prompt(keys),
        ],
        build_schema(rule_ids),
    )
    return validate(result, rule_ids)


if __name__ == "__main__":
    pdf, csv_path = sys.argv[1], sys.argv[2]
    rules, problems = extract_policy_rules(pdf, csv_path)

    out = Path("output") / "policy_rules.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")

    matched = [r for r in rules if r["matched_rule_id"] != NO_MATCH]
    print(f"{len(rules)} policy rules extracted: {len(matched)} matched to config, "
          f"{len(rules) - len(matched)} policy-only")
    for r in rules:
        print(f"  {r['policy_source']:>5}  {r['matched_rule_id']:<6} {r['value']:>10} {r['unit']:<12} {r['topic']}")
    for p in problems:
        print("  PROBLEM:", p)
    print(f"Saved to {out}")
