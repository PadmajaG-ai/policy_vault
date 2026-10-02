"""Consistency check for the synthetic data pack.

Run:  python tools/check_data.py
It confirms the answer key (ground_truth.json) matches the data files, so your
later accuracy numbers ("4 of 4 drifts caught") are measured against a correct key.
Reuse this pattern later as your evaluation harness for the agents.
"""
import csv
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "expense"

rules = {r["rule_id"]: r for r in csv.DictReader(open(DATA / "config_rules.csv"))}
truth = json.load(open(DATA / "ground_truth.json"))
tickets = json.load(open(DATA / "tickets.json"))
experts = {a["ref"]: a for a in json.load(open(DATA / "expert_answers.json"))["answers"]}
policy = (DATA / "policy.md").read_text().replace(",", "")

ticket_ids = {t["ticket_id"] for t in tickets}
linked = {r for t in tickets for r in t["related_rules"]}
errors = []

for d in truth["drifts"]:
    r = rules[d["rule_id"]]
    if float(r["value"]) != d["config_value"]:
        errors.append(f"{d['id']}: config value {r['value']} != key {d['config_value']}")
    if not re.search(rf"\b{d['policy_value']}\b", policy):
        errors.append(f"{d['id']}: policy value {d['policy_value']} not found in policy text")
    if str(d["config_value"]) in re.findall(r"\d+", policy) and d["id"] != "D3":
        # D3's old value (10000) legitimately appears in the version history
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
print(f"Config rules: {len(rules)} | policy-checkable: {len(checkable)} "
      f"({len(truth['drifts'])} drifts, {len(truth['aligned_rules'])} aligned) | "
      f"undocumented: {len(truth['undocumented_rules'])} | tickets: {len(tickets)}")
print("ALL CHECKS PASSED" if not errors else "\n".join(["FAILED:"] + errors))
