"""Consistency check for every synthetic data pack in data/.

Run:  python tools/check_data.py
It confirms each answer key (ground_truth.json) matches its data files, so accuracy numbers
("4 of 4 drifts caught") are measured against a correct key.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# A drift's old config value may legitimately appear in a policy's version history
VERSION_HISTORY_OK = {("expense", "D3")}


def check(pack):
    rules = {r["rule_id"]: r for r in csv.DictReader(open(pack / "config_rules.csv", encoding="utf-8"))}
    truth = json.load(open(pack / "ground_truth.json", encoding="utf-8"))
    tickets = json.load(open(pack / "tickets.json", encoding="utf-8"))
    experts = {a["ref"]: a for a in json.load(open(pack / "expert_answers.json", encoding="utf-8"))["answers"]}
    policy = (pack / "policy.md").read_text(encoding="utf-8").replace(",", "")

    ticket_ids = {t["ticket_id"] for t in tickets}
    linked = {r for t in tickets for r in t["related_rules"]}
    errors = []

    if not (pack / "policy.pdf").exists():
        errors.append("policy.pdf missing (python tools/make_policy_pdf.py <pack>)")
    if {r["domain"] for r in rules.values()} != {rules[next(iter(rules))]["domain"]}:
        errors.append("config rules mix several domains")

    for d in truth["drifts"]:
        r = rules[d["rule_id"]]
        if float(r["value"]) != d["config_value"]:
            errors.append(f"{d['id']}: config value {r['value']} != key {d['config_value']}")
        if not re.search(rf"\b{d['policy_value']}\b", policy):
            errors.append(f"{d['id']}: policy value {d['policy_value']} not found in policy text")
        if str(d["config_value"]) in re.findall(r"\d+", policy) and (pack.name, d["id"]) not in VERSION_HISTORY_OK:
            errors.append(f"{d['id']}: config value also appears in policy text (ambiguous)")

    for rid in truth["aligned_rules"]:
        if rid not in rules:
            errors.append(f"aligned rule {rid} missing from config")

    for rid, tid in truth["documented_by_ticket_only"].items():
        if tid not in ticket_ids or rid not in linked:
            errors.append(f"{rid}: expected ticket {tid} to reference it")

    for u in truth["undocumented_rules"]:
        if u["rule_id"] in linked:
            errors.append(f"{u['id']}: rule {u['rule_id']} is linked in a ticket, so it is not undocumented")
        if u["expert_answer_ref"] not in experts:
            errors.append(f"{u['id']}: missing expert answer")

    checkable = set(truth["aligned_rules"]) | {d["rule_id"] for d in truth["drifts"]}
    print(f"[{pack.name}] config rules: {len(rules)} | policy-checkable: {len(checkable)} "
          f"({len(truth['drifts'])} drifts, {len(truth['aligned_rules'])} aligned) | "
          f"undocumented: {len(truth['undocumented_rules'])} | tickets: {len(tickets)}")
    return errors, set(rules), ticket_ids


all_errors, seen_rules, seen_tickets = [], set(), set()
for pack in sorted(p for p in (ROOT / "data").iterdir() if (p / "config_rules.csv").exists()):
    errors, rule_ids, ticket_ids = check(pack)
    # IDs must be unique across packs: Decision Records and search documents are keyed by them
    errors += [f"rule id {r} also used in another pack" for r in rule_ids & seen_rules]
    errors += [f"ticket id {t} also used in another pack" for t in ticket_ids & seen_tickets]
    seen_rules |= rule_ids
    seen_tickets |= ticket_ids
    all_errors += [f"{pack.name}: {e}" for e in errors]

print("ALL CHECKS PASSED" if not all_errors else "\n".join(["FAILED:"] + all_errors))
