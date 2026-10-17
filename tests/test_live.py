"""LIVE end-to-end checks against real Gemini and Vertex AI Search. These prove the demo claims.

Run:  pytest -m live -v          (needs `gcloud auth application-default login`, costs a few cents)
"""

import json
import re

import pytest

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_report():
    import drift
    return drift.scan("data/expense", cached=False)


def test_extraction_matches_all_checkable_rules(live_report, truth):
    checked = {f["rule_id"] for f in live_report["findings"]}
    assert checked == set(truth["aligned_rules"]) | {d["rule_id"] for d in truth["drifts"]}


def test_all_drifts_found_with_zero_false_alarms(live_report, truth):
    drifts = {f["rule_id"] for f in live_report["findings"] if f["status"] == "drift"}
    expected = {d["rule_id"] for d in truth["drifts"]}
    assert drifts == expected, f"missed {expected - drifts}, false alarms {drifts - expected}"


def test_policy_values_extracted_correctly(live_report, truth):
    import drift
    by_rule = {f["rule_id"]: f for f in live_report["findings"]}
    for d in truth["drifts"]:
        assert drift.to_number(by_rule[d["rule_id"]]["policy_value"]) == d["policy_value"], d["rule_id"]


def test_root_causes_match_answer_key(live_report, truth):
    by_rule = {f["rule_id"]: f for f in live_report["findings"]}
    for d in truth["drifts"]:
        expected = set(re.findall(r"TKT-\d+", d["root_cause"]))
        assert set(by_rule[d["rule_id"]]["root_cause_sources"]) == expected, d["rule_id"]


def test_search_ranks_expected_tickets_first():
    import search_index
    for query, ticket in {"meal limit increase sales offsite": "TKT-1042",
                          "mileage posting failed field length exceeded": "TKT-1135",
                          "metro hotel cap reduced": "TKT-1177"}.items():
        assert ticket in search_index.search(query, page_size=3)[0], query


def test_interview_connects_r014_to_tkt1135(rules, tickets):
    import gaps
    q = gaps.interview_question(rules["R-014"], {"kind": "undocumented", "summary": "vehicle registration hidden"}, tickets, "R. Kumar")
    assert "TKT-1135" in q["cited_tickets"] and "TKT-1135" in q["question"]


def test_expert_answer_becomes_high_risk_record(rules):
    import gaps
    answer = next(a for a in json.load(open("data/expense/expert_answers.json", encoding="utf-8"))["answers"] if a["rule_id"] == "R-014")
    r = gaps.draft_record(rules["R-014"], "Is hiding the field related to TKT-1135?", ["TKT-1135"], answer["answer"], "R. Kumar", "expense")
    assert r["risk_if_removed"] == "high" and "TKT-1135" in r["sources"] and "ERP" in r["why"]


def test_ask_why_uses_the_decision_record():
    from ask_why import ask_why
    record = {"record_id": "DR-0001", "rule_id": "R-014", "what": "Vehicle registration field hidden on mileage form",
              "why": "It overflowed a 10-character ERP interface field and broke GL posting", "decided_by": "r.kumar",
              "decided_on": "2021-09-06", "sources": ["TKT-1135", "interview:R. Kumar"], "risk_if_removed": "high",
              "verified_by_expert": True}
    r = ask_why("Can I show the vehicle registration field again? Fleet management wants it.", [record])
    assert not r["guardrail"] and "ERP" in r["answer"] and "DR-0001" in r["sources"]


def test_ask_why_admits_when_there_is_no_rationale():
    from ask_why import ask_why, NO_RATIONALE
    r = ask_why("Why was the international meal limit set at USD 75?", [])
    assert NO_RATIONALE.lower().rstrip(".") in r["answer"].lower()


# ---- domain pack #2: inventory, same engine ----

@pytest.fixture(scope="module")
def inv_live():
    import drift
    truth = json.load(open("data/inventory/ground_truth.json", encoding="utf-8"))
    return drift.scan("data/inventory", cached=False), truth


def test_inventory_drifts_zero_false_alarms(inv_live):
    report, truth = inv_live
    drifts = {f["rule_id"] for f in report["findings"] if f["status"] == "drift"}
    aligned = {f["rule_id"] for f in report["findings"] if f["status"] == "aligned"}
    assert drifts == {d["rule_id"] for d in truth["drifts"]}
    assert aligned == set(truth["aligned_rules"])


def test_inventory_root_causes(inv_live):
    report, truth = inv_live
    by_rule = {f["rule_id"]: f for f in report["findings"]}
    for d in truth["drifts"]:
        assert set(by_rule[d["rule_id"]]["root_cause_sources"]) == set(re.findall(r"TKT-\d+", d["root_cause"])), d["rule_id"]


def test_inventory_interview_connects_inv010_to_tkt2058():
    import csv
    import gaps
    rules = {r["rule_id"]: r for r in csv.DictReader(open("data/inventory/config_rules.csv", encoding="utf-8"))}
    tickets = json.load(open("data/inventory/tickets.json", encoding="utf-8"))
    q = gaps.interview_question(rules["INV-010"], {"kind": "undocumented", "summary": "MAT-7730 excluded from auto reorder"}, tickets, "Deepa M.")
    assert "TKT-2058" in q["cited_tickets"] and "TKT-2058" in q["question"]
