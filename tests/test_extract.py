"""Extraction guard-rails: no anchoring on config values, only real rule IDs, validated output."""

import re

import extract


def test_config_values_never_reach_gemini(rules):
    keys = extract.load_config_keys("data/expense/config_rules.csv")
    assert all("value" not in k and "changed_by" not in k for k in keys)
    prompt = extract.build_prompt(keys)
    numbers_in_prompt = set(re.findall(r"\d[\d,]*", prompt.replace(",", "")))
    for rid, rule in rules.items():
        if rule["value"].isdigit() and rule["value"] not in rule["condition"]:
            assert rule["value"] not in numbers_in_prompt, f"{rid} config value {rule['value']} appears in the prompt"


def test_schema_only_allows_real_rule_ids():
    ids = ["R-001", "R-002"]
    enum = extract.build_schema(ids)["properties"]["policy_rules"]["items"]["properties"]["matched_rule_id"]["enum"]
    assert enum == ["R-001", "R-002", extract.NO_MATCH]


def test_schema_requires_evidence():
    required = extract.build_schema(["R-001"])["properties"]["policy_rules"]["items"]["required"]
    assert {"quote", "policy_source", "matched_rule_id", "value", "unit"} <= set(required)


def test_validate_rejects_unknown_and_duplicate_ids():
    raw = {"policy_rules": [
        {"matched_rule_id": "R-001", "policy_source": "5.1"},
        {"matched_rule_id": "R-001", "policy_source": "5.2"},   # second claim on the same slot
        {"matched_rule_id": "R-999", "policy_source": "9.9"},   # invented id
        {"matched_rule_id": "none", "policy_source": "6.3"},
        {"matched_rule_id": "none", "policy_source": "7.1"},    # several policy-only rules are fine
    ]}
    rules, problems = extract.validate(raw, ["R-001"])
    assert [r["policy_source"] for r in rules] == ["5.1", "6.3", "7.1"]
    assert len(problems) == 2
    assert all(r["source_type"] == "policy" for r in rules)


def test_validate_handles_empty_output():
    assert extract.validate({}, ["R-001"]) == ([], [])
