"""Domain pack #2 (inventory): the same engine, no code changes, must hit its own answer key."""

import csv
import json
from pathlib import Path

import pytest

import drift
import gaps

PACK = Path(__file__).resolve().parent.parent / "data" / "inventory"


@pytest.fixture
def inv_rows():
    with open(PACK / "config_rules.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def inv_rules(inv_rows):
    return {r["rule_id"]: r for r in inv_rows}


@pytest.fixture
def inv_tickets():
    return json.loads((PACK / "tickets.json").read_text(encoding="utf-8"))


@pytest.fixture
def inv_truth():
    return json.loads((PACK / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture
def inv_report(inv_truth, inv_rules, inv_rows):
    """Report from a perfect extraction + the key's root causes (what a correct live scan returns)."""
    policy_values = {d["rule_id"]: str(d["policy_value"]) for d in inv_truth["drifts"]}
    rules = [{"matched_rule_id": rid, "value": policy_values.get(rid, inv_rules[rid]["value"]),
              "unit": inv_rules[rid]["unit"], "policy_source": "x", "quote": "q", "topic": rid, "match_confidence": "high"}
             for rid in list(policy_values) + inv_truth["aligned_rules"]]
    findings, policy_only = drift.detect(rules, inv_rows)
    for f in findings:
        if f["status"] == drift.DRIFT:
            f["root_cause_found"] = f["rule_id"] == "INV-001"
            f["root_cause_sources"] = ["TKT-2031"] if f["root_cause_found"] else []
    return drift.build_report(findings, policy_only)


def test_comparison_matches_inventory_answer_key(inv_report, inv_truth):
    drifts = {f["rule_id"] for f in inv_report["findings"] if f["status"] == drift.DRIFT}
    aligned = {f["rule_id"] for f in inv_report["findings"] if f["status"] == drift.ALIGNED}
    assert drifts == {d["rule_id"] for d in inv_truth["drifts"]}
    assert aligned == set(inv_truth["aligned_rules"])


def test_indian_grouping_write_off_threshold_is_aligned(inv_report):
    """Policy says INR 1,00,000; config says 100000. Must not be a false alarm."""
    f = next(f for f in inv_report["findings"] if f["rule_id"] == "INV-005")
    assert f["status"] == drift.ALIGNED


def test_inventory_gaps(inv_report, inv_rows, inv_tickets, inv_truth):
    found = {g["rule_id"] for g in gaps.find_gaps(inv_report, inv_rows, inv_tickets)}
    undocumented = {u["rule_id"] for u in inv_truth["undocumented_rules"]}
    unexplained = {d["rule_id"] for d in inv_truth["drifts"] if "No ticket" in d["root_cause"]}
    assert found == undocumented | unexplained


def test_date_clue_connects_inv010_to_tkt2058(inv_rules, inv_tickets, offline_search):
    offline_search.fail = True
    clues = gaps.find_clues(inv_rules["INV-010"], inv_tickets)
    assert [c["ticket_id"] for c in clues] == ["TKT-2058"] and "4 days" in clues[0]["clue"]


def test_no_false_clues_for_other_inventory_gaps(inv_rules, inv_tickets, offline_search):
    offline_search.fail = True
    for rid in ("INV-003", "INV-011"):
        assert gaps.find_clues(inv_rules[rid], inv_tickets) == [], rid


def test_inventory_coverage(inv_report, inv_rows, inv_tickets):
    c = gaps.coverage(inv_report, inv_rows, inv_tickets, [])
    assert c["by_source"] == {"policy": 7, "ticket": 2, "decision_record": 0, "unexplained": 3}


def test_extraction_prompt_hides_inventory_config_values():
    import re
    import extract
    keys = extract.load_config_keys(PACK / "config_rules.csv")
    prompt = extract.build_prompt(keys)
    numbers = set(re.findall(r"\d[\d,]*", prompt.replace(",", "")))
    with open(PACK / "config_rules.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["value"].isdigit() and r["value"] not in r["condition"] and r["value"] not in r["rule_id"]:
                assert r["value"] not in numbers, f"{r['rule_id']} value {r['value']} in prompt"


def test_app_switches_to_inventory(local_records, offline_search):
    import main
    c = main.app.test_client()
    page = c.get("/?pack=inventory").data.decode()
    assert "Deepa M." in page and "TKT-2110" in page and 'class="packs"' in page
    assert c.get("/api/interview/expert_answer/INV-010?pack=inventory").json["answer"].startswith("Yes")
    # expense records never leak into the inventory pack
    assert c.get("/api/records?pack=inventory").json["records"] == []
