"""Gap Finder + interview: the right gaps, the right clues, and no invented evidence."""

import gaps


def test_finds_exactly_the_demo_gaps(saved_report, config_rows, tickets, truth):
    found = gaps.find_gaps(saved_report, config_rows, tickets)
    undocumented = {u["rule_id"] for u in truth["undocumented_rules"]}
    unexplained_drifts = {d["rule_id"] for d in truth["drifts"] if "No ticket" in d["root_cause"]}
    assert {g["rule_id"] for g in found} == undocumented | unexplained_drifts


def test_ticket_documented_rules_are_not_gaps(saved_report, config_rows, tickets, truth):
    found = {g["rule_id"] for g in gaps.find_gaps(saved_report, config_rows, tickets)}
    assert not found & set(truth["documented_by_ticket_only"])


def test_date_clue_connects_r014_to_tkt1135(rules, tickets, offline_search):
    offline_search.fail = True  # must work even when search is down
    clues = gaps.find_clues(rules["R-014"], tickets)
    assert [c["ticket_id"] for c in clues] == ["TKT-1135"]
    assert "3 days" in clues[0]["clue"]


def test_no_false_clues_for_other_gaps(rules, tickets, offline_search):
    offline_search.fail = True
    for rid in ("R-012", "R-013", "R-003"):
        assert gaps.find_clues(rules[rid], tickets) == [], rid


def test_search_clues_are_added_and_unknown_tickets_ignored(rules, tickets, offline_search):
    offline_search.links = ["gs://b/corpus/ticket_TKT-1042.txt", "gs://b/corpus/ticket_TKT-0000.txt", "gs://b/corpus/policy.pdf"]
    ids = {c["ticket_id"] for c in gaps.find_clues(rules["R-014"], tickets)}
    assert ids == {"TKT-1042", "TKT-1135"}


def test_question_cannot_cite_tickets_outside_the_clues(monkeypatch, rules, tickets, offline_search):
    offline_search.fail = True
    monkeypatch.setattr(gaps.gemini, "generate_json",
                        lambda c, s: {"question": "Related to TKT-1135?", "cited_tickets": ["TKT-1135", "TKT-1042"]})
    gap = {"kind": "undocumented", "summary": "s"}
    q = gaps.interview_question(rules["R-014"], gap, tickets, "R. Kumar")
    assert q["cited_tickets"] == ["TKT-1135"]


def test_question_prompt_never_contains_the_expert_answer(monkeypatch, rules, tickets, offline_search):
    offline_search.fail = True
    seen = {}

    def fake(contents, schema):
        seen["prompt"] = contents[0]
        return {"question": "q", "cited_tickets": []}

    monkeypatch.setattr(gaps.gemini, "generate_json", fake)
    gaps.interview_question(rules["R-014"], {"kind": "k", "summary": "s"}, tickets, "R. Kumar")
    assert "10 characters" not in seen["prompt"]  # a phrase only the expert knows


def test_draft_record_shape_and_safety(monkeypatch, rules):
    monkeypatch.setattr(gaps.gemini, "generate_json", lambda c, s: {
        "what": "w", "why": "y", "decided_by": "r.kumar", "decided_on": "2021-09-06",
        "confirmed_tickets": ["TKT-1135", "TKT-9999"], "risk_if_removed": "high",
        "risk_note": "n", "confidence": "high"})
    r = gaps.draft_record(rules["R-014"], "q", ["TKT-1135"], "answer", "R. Kumar", "expense")
    assert r["sources"] == ["TKT-1135", "interview:R. Kumar"]
    assert r["verified_by_expert"] is False  # only a human click verifies it
    assert r["rule_id"] == "R-014" and r["domain"] == "expense"
