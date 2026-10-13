"""Drift detection: code compares policy rules with the config, Gemini explains each drift.

Steps:
1. compare()        plain Python: is the policy value the same as the configured value?
2. explain_drifts() Gemini reads the ticket history and finds why each drift exists.
                    Ticket IDs are an enum, so it can only cite tickets that exist.

Usage:  python drift.py data/expense            (re-extracts the policy with Gemini)
        python drift.py data/expense --cached   (reuses output/policy_rules.json)
"""

import csv
import json
import re
import sys
from pathlib import Path

import gemini
from extract import NO_MATCH, extract_policy_rules

ALIGNED, DRIFT, REVIEW = "aligned", "drift", "needs_review"


# ---------- 1. Deterministic comparison ----------

def to_number(value):
    """'INR 1,00,000' -> 100000.0 ; returns None if the value is not a number."""
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned or not re.search(r"\d", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_tokens(value, unit):
    """'economy_class' with unit 'class' -> {'economy'}. Drops words that only repeat the unit."""
    words = set(re.split(r"[\s_\-/]+", str(value).strip().lower())) - {""}
    unit_words = set(re.split(r"[\s_\-/]+", unit.lower()))
    return (words - unit_words) or words


def same_unit(a, b):
    return re.sub(r"\s", "", a).lower() == re.sub(r"\s", "", b).lower()


def compare(policy_rule, config_row):
    """Return (status, reason). Never calls a drift unless code is sure the values differ."""
    if not same_unit(policy_rule["unit"], config_row["unit"]):
        return REVIEW, f"unit mismatch: policy {policy_rule['unit']} vs config {config_row['unit']}"

    p_num, c_num = to_number(policy_rule["value"]), to_number(config_row["value"])
    if p_num is not None and c_num is not None:
        if p_num == c_num:
            return ALIGNED, "values equal"
        return DRIFT, f"config is {'higher' if c_num > p_num else 'lower'} than policy"

    p_tok, c_tok = to_tokens(policy_rule["value"], config_row["unit"]), to_tokens(config_row["value"], config_row["unit"])
    if p_tok == c_tok:
        return ALIGNED, "values equal"
    if policy_rule.get("match_confidence") == "low":
        return REVIEW, "values differ but the policy-to-config match is uncertain"
    return DRIFT, "values differ"


def detect(policy_rules, config_rows):
    config = {r["rule_id"]: r for r in config_rows}
    findings, policy_only = [], []
    for p in policy_rules:
        rid = p["matched_rule_id"]
        if rid == NO_MATCH:
            policy_only.append(p)
            continue
        c = config[rid]
        status, reason = compare(p, c)
        findings.append({
            "rule_id": rid,
            "topic": p["topic"],
            "status": status,
            "reason": reason,
            "policy_value": p["value"],
            "config_value": c["value"],
            "unit": c["unit"],
            "policy_source": f"Policy section {p['policy_source']}",
            "policy_quote": p["quote"],
            "config_location": c["config_location"],
            "last_changed": c["last_changed"],
            "changed_by": c["changed_by"],
        })
    return findings, policy_only


# ---------- 2. Root cause from tickets (Gemini) ----------

def explain_drifts(drifts, tickets):
    if not drifts:
        return
    ticket_ids = [t["ticket_id"] for t in tickets]
    schema = {
        "type": "OBJECT",
        "properties": {"explanations": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {
                "rule_id": {"type": "STRING", "enum": [d["rule_id"] for d in drifts]},
                "root_cause_found": {"type": "BOOLEAN"},
                "root_cause": {"type": "STRING", "description": "Why the config differs, in one or two sentences. If not found, say so."},
                "root_cause_sources": {"type": "ARRAY", "items": {"type": "STRING", "enum": ticket_ids}},
                "business_risk": {"type": "STRING", "description": "Concrete money or compliance impact, one sentence"},
            },
            "required": ["rule_id", "root_cause_found", "root_cause", "root_cause_sources", "business_risk"],
        }}},
        "required": ["explanations"],
    }
    drift_lines = "\n".join(
        f"- {d['rule_id']} {d['topic']}: policy says {d['policy_value']} {d['unit']} ({d['policy_source']}), "
        f"system is configured to {d['config_value']} {d['unit']}; last changed {d['last_changed']} by {d['changed_by']}"
        for d in drifts
    )
    prompt = f"""The written policy and the live system configuration disagree on these rules:
{drift_lines}

Below is the full ticket history of the system. For each rule, find the ticket(s) that explain
why the configuration differs from the policy. Use dates, people, values and descriptions to
connect them; a ticket may be relevant even if it does not name the rule ID.
Only cite a ticket if it really explains the difference. If no ticket explains it, set
root_cause_found to false and leave root_cause_sources empty. Do not guess.

Tickets:
{json.dumps(tickets, indent=1)}
"""
    result = gemini.generate_json([prompt], schema)
    by_rule = {e["rule_id"]: e for e in result.get("explanations", [])}
    for d in drifts:
        e = by_rule.get(d["rule_id"], {})
        sources = [s for s in e.get("root_cause_sources", []) if s in ticket_ids]
        found = bool(e.get("root_cause_found")) and bool(sources)
        d["root_cause"] = e.get("root_cause", "") if found else "No record found. Ask the expert."
        d["root_cause_sources"] = sources if found else []
        d["root_cause_found"] = found
        d["business_risk"] = e.get("business_risk", "")


# ---------- Full scan ----------

def scan(pack_dir, cached=False):
    pack = Path(pack_dir)
    with open(pack / "config_rules.csv", newline="", encoding="utf-8") as f:
        config_rows = list(csv.DictReader(f))
    tickets = json.loads((pack / "tickets.json").read_text(encoding="utf-8"))

    cache = Path("output") / "policy_rules.json"
    if cached and cache.exists():
        policy_rules = json.loads(cache.read_text(encoding="utf-8"))
    else:
        policy_rules, problems = extract_policy_rules(pack / "policy.pdf", pack / "config_rules.csv")
        for p in problems:
            print("  extraction problem:", p)

    findings, policy_only = detect(policy_rules, config_rows)
    drifts = [f for f in findings if f["status"] == DRIFT]
    explain_drifts(drifts, tickets)

    return {
        "summary": {
            "checked": len(findings),
            "drifts": len(drifts),
            "aligned": sum(f["status"] == ALIGNED for f in findings),
            "needs_review": sum(f["status"] == REVIEW for f in findings),
            "policy_only": len(policy_only),
        },
        "findings": findings,
        "policy_only": policy_only,
    }


if __name__ == "__main__":
    report = scan(sys.argv[1], cached="--cached" in sys.argv)
    out = Path("output") / "drift_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"{s['checked']} policy rules checked: {s['drifts']} drifts, {s['aligned']} aligned, "
          f"{s['needs_review']} need review | {s['policy_only']} policy-only rules")
    for f in report["findings"]:
        if f["status"] != ALIGNED:
            print(f"\n  [{f['status'].upper()}] {f['rule_id']} {f['topic']}: policy {f['policy_value']} vs system {f['config_value']} {f['unit']}")
            if f["status"] == DRIFT:
                print(f"    why:  {f['root_cause']}  {f['root_cause_sources']}")
                print(f"    risk: {f['business_risk']}")
            else:
                print(f"    {f['reason']}")
    print(f"\nSaved to {out}")
