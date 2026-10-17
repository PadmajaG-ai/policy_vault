"""Score the drift report against the answer key. The ONLY place ground_truth.json is read.

Run after drift.py:  python tools/evaluate.py [pack]     (pack defaults to expense)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = sys.argv[1] if len(sys.argv) > 1 else "expense"
truth = json.loads((ROOT / "data" / PACK / "ground_truth.json").read_text(encoding="utf-8"))
report = json.loads((ROOT / "output" / PACK / "drift_report.json").read_text(encoding="utf-8"))

expected = {d["rule_id"]: d for d in truth["drifts"]}
found = {f["rule_id"]: f for f in report["findings"] if f["status"] == "drift"}
aligned_ok = {f["rule_id"] for f in report["findings"] if f["status"] == "aligned"}

caught = expected.keys() & found.keys()
missed = expected.keys() - found.keys()
false_alarms = found.keys() - expected.keys()
aligned_missing = set(truth["aligned_rules"]) - aligned_ok

# A root cause is correct if the cited tickets match the key ("no ticket" drifts must cite none).
root_ok = []
for rid in caught:
    key_tickets = {w.strip("(),.'") for w in expected[rid]["root_cause"].split() if w.strip("(),.'").startswith("TKT-")}
    if set(found[rid]["root_cause_sources"]) == key_tickets:
        root_ok.append(rid)

print(f"Drifts caught:      {len(caught)}/{len(expected)}   missed: {sorted(missed) or 'none'}")
print(f"False alarms:       {len(false_alarms)}   {sorted(false_alarms) or ''}")
print(f"Aligned confirmed:  {len(truth['aligned_rules']) - len(aligned_missing)}/{len(truth['aligned_rules'])}   not confirmed: {sorted(aligned_missing) or 'none'}")
print(f"Root causes right:  {len(root_ok)}/{len(caught)}   wrong: {sorted(caught - set(root_ok)) or 'none'}")
