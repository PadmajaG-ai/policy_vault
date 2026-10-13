"""Evaluation for ask_why: known questions, required content, pass/fail.

Run:  python tools/test_ask_why.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ask_why import ask_why  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data" / "expense"

# Simulate what the interview agent would have saved (Decision Records)
experts = json.load(open(DATA / "expert_answers.json"))["answers"]
records = [
    {"record_id": f"DR-{i + 1:03d}", "rule_id": a["rule_id"], "why": a["answer"],
     "decided_by": a["decided_by"], "decided_on": a["decided_on"],
     "risk_if_removed": a["risk_if_removed"], "verified_by_expert": True,
     "linked_tickets": [a["linked_ticket"]] if a.get("linked_ticket") else []}
    for i, a in enumerate(experts)
]

# question -> (words that must ALL appear, words of which at least ONE must appear)
TESTS = {
    "Why is the domestic meal limit 4000 INR when policy says 2500?":
        (["TKT-1042"], []),
    "Can I re-enable the vehicle registration field on the mileage form?":
        (["R-014", "TKT-1135", "ERP"], []),
    "Why is cost centre CC-4410 excluded from auto-approval?":
        (["R-013", "Internal Audit"], []),
    # Trap: nothing explains WHY USD 75 was chosen. It must admit that.
    "Why was the international meal limit set at USD 75?":
        ([], ["no recorded rationale", "no evidence", "does not explain", "not documented"]),
}

passed = 0
for q, (must_all, must_any) in TESTS.items():
    r = ask_why(q, records)
    text = r["answer"].lower()
    problems = [f"missing '{w}'" for w in must_all if w.lower() not in text]
    if must_any and not any(w in text for w in must_any):
        problems.append(f"needs one of {must_any}")
    if r.get("guardrail"):
        problems.append("guardrail triggered (degenerate output)")
    if len(r["answer"]) > 2500:
        problems.append("answer too long")
    status = "PASS" if not problems else "FAIL: " + "; ".join(problems)
    passed += not problems
    print(f"\n[{status}] {q}\n--- answer ---\n{r['answer']}\n--- sources ---\n{r['sources']}")
    time.sleep(3)

print(f"\n=== {passed}/{len(TESTS)} passed ===")
