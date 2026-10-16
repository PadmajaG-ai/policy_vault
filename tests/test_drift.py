"""Drift detection: the deterministic core. If these fail, the 0-false-alarm claim is not safe."""

import pytest

import drift


@pytest.mark.parametrize("text, expected", [
    ("2500", 2500), ("2,500", 2500), ("INR 2,500", 2500), ("₹4,000", 4000),
    ("1,00,000", 100000),        # Indian digit grouping (D4)
    ("100000", 100000), ("75", 75), ("12.5", 12.5),
    ("economy", None), ("", None), ("false", None), ("line_manager", None),
])
def test_to_number(text, expected):
    assert drift.to_number(text) == expected


def test_text_values_ignore_unit_words():
    assert drift.to_tokens("economy_class", "class") == drift.to_tokens("economy", "class")
    assert drift.to_tokens("Line Manager", "role") == drift.to_tokens("line_manager", "role")


def test_text_values_do_not_over_match():
    # "premium economy" must never be treated as "economy"
    assert drift.to_tokens("premium_economy", "class") != drift.to_tokens("economy", "class")
    assert drift.to_tokens("legal_compliance", "role") != drift.to_tokens("legal", "role")


def P(value, unit, confidence="high"):
    return {"value": value, "unit": unit, "match_confidence": confidence}


def C(value, unit):
    return {"value": value, "unit": unit}


@pytest.mark.parametrize("policy, config, status", [
    (P("2500", "INR/day"), C("4000", "INR/day"), drift.DRIFT),
    (P("5000", "INR/night"), C("5000", "INR/night"), drift.ALIGNED),
    (P("50000", "INR/report"), C("100000", "INR/report"), drift.DRIFT),
    (P("2500", "INR/day"), C("2500", "INR/line"), drift.REVIEW),      # unit mismatch is never a drift
    (P("75", "USD/day"), C("75", "INR/day"), drift.REVIEW),
    (P("2500", "INR / day"), C("2500", "inr/day"), drift.ALIGNED),     # spacing/case in units
    (P("false", "boolean"), C("false", "boolean"), drift.ALIGNED),
    (P("true", "boolean"), C("false", "boolean"), drift.DRIFT),
    (P("economy_class", "class"), C("economy", "class"), drift.ALIGNED),
    (P("business", "class"), C("economy", "class"), drift.DRIFT),
    (P("business", "class", "low"), C("economy", "class"), drift.REVIEW),  # unsure match -> human
])
def test_compare(policy, config, status):
    assert drift.compare(policy, config)[0] == status


def test_drift_direction_is_reported():
    assert "higher" in drift.compare(P("2500", "INR/day"), C("4000", "INR/day"))[1]
    assert "lower" in drift.compare(P("4000", "INR/day"), C("2500", "INR/day"))[1]


def test_detect_matches_answer_key(policy_rules, config_rows, truth):
    """With a correct extraction, the comparison alone must give exactly 4 drifts and 8 aligned."""
    findings, policy_only = drift.detect(policy_rules, config_rows)
    drifts = {f["rule_id"] for f in findings if f["status"] == drift.DRIFT}
    aligned = {f["rule_id"] for f in findings if f["status"] == drift.ALIGNED}
    assert drifts == {d["rule_id"] for d in truth["drifts"]}
    assert aligned == set(truth["aligned_rules"])
    assert len(policy_only) == 1


def test_findings_carry_evidence(policy_rules, config_rows):
    findings, _ = drift.detect(policy_rules, config_rows)
    for f in findings:
        for field in ("policy_source", "policy_quote", "config_location", "last_changed", "changed_by"):
            assert f[field], f"{f['rule_id']} missing {field}"


# ---- root cause step: Gemini is faked, the code's checks are real ----

def _drifts():
    return [{"rule_id": r, "topic": r, "policy_value": "1", "config_value": "2", "unit": "INR",
             "policy_source": "s", "last_changed": "2021-01-01", "changed_by": "x"} for r in ("R-001", "R-003")]


def test_root_cause_rejects_invented_tickets(monkeypatch, tickets):
    monkeypatch.setattr(drift.gemini, "generate_json", lambda c, s: {"explanations": [
        {"rule_id": "R-001", "root_cause_found": True, "root_cause": "offsite", "root_cause_sources": ["TKT-1042", "TKT-9999"], "business_risk": "r"},
        {"rule_id": "R-003", "root_cause_found": True, "root_cause": "made up", "root_cause_sources": ["TKT-9999"], "business_risk": "r"},
    ]})
    ds = _drifts()
    drift.explain_drifts(ds, tickets)
    assert ds[0]["root_cause_sources"] == ["TKT-1042"]
    # A "found" root cause whose only evidence is invented is NOT found
    assert ds[1]["root_cause_found"] is False
    assert ds[1]["root_cause"].startswith("No record found")


def test_root_cause_missing_from_model_output(monkeypatch, tickets):
    monkeypatch.setattr(drift.gemini, "generate_json", lambda c, s: {"explanations": []})
    ds = _drifts()
    drift.explain_drifts(ds, tickets)
    assert all(d["root_cause_found"] is False for d in ds)


def test_root_cause_prompt_contains_no_answer_key(monkeypatch, tickets):
    seen = {}
    monkeypatch.setattr(drift.gemini, "generate_json", lambda c, s: seen.setdefault("prompt", c[0]) and {"explanations": []})
    drift.explain_drifts(_drifts(), tickets)
    assert "ground_truth" not in seen["prompt"] and "root_cause\":" not in seen["prompt"]
