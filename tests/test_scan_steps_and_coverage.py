"""Step-by-step scan, coverage meter, evidence and per-pack isolation (Gemini faked)."""

import pytest


@pytest.fixture
def app(local_records, offline_search, monkeypatch, policy_rules):
    import main
    offline_search.fail = True
    monkeypatch.setattr(main.drift, "extract_step", lambda pack_dir, cached=False: policy_rules)
    monkeypatch.setattr(main.drift.gemini, "generate_json", lambda c, s: {"explanations": [
        {"rule_id": "R-001", "root_cause_found": True, "root_cause": "offsite", "root_cause_sources": ["TKT-1042"], "business_risk": "r"},
        {"rule_id": "R-004", "root_cause_found": True, "root_cause": "v3.2", "root_cause_sources": ["TKT-1177"], "business_risk": "r"},
        {"rule_id": "R-008", "root_cause_found": True, "root_cause": "workload", "root_cause_sources": ["TKT-1098"], "business_risk": "r"},
        {"rule_id": "R-003", "root_cause_found": False, "root_cause": "", "root_cause_sources": [], "business_risk": "r"}]})
    for p in main.PACKS.values():  # fresh per-pack state for every test
        monkeypatch.setitem(p, "report", p["saved"])
        monkeypatch.setitem(p, "policy_rules", None)
        monkeypatch.setitem(p, "findings", None)
    return main.app.test_client()


def test_scan_runs_as_three_real_steps(app):
    e = app.post("/api/scan/extract").json
    assert e["matched"] == 12 and e["policy_only"] == 1
    c = app.post("/api/scan/compare").json
    assert (c["checked"], c["drifts"], c["aligned"]) == (12, 4, 8)
    r = app.post("/api/scan/explain").json
    assert r["mode"] == "live" and r["summary"]["drifts"] == 4
    found = {f["rule_id"] for f in r["findings"] if f.get("root_cause_found")}
    assert found == {"R-001", "R-004", "R-008"}


def test_steps_must_run_in_order(app):
    assert app.post("/api/scan/compare").status_code == 400
    assert app.post("/api/scan/explain").status_code == 400


def test_saved_scan_is_available_as_fallback(app):
    r = app.get("/api/scan/saved").json
    assert r["mode"] == "saved" and r["summary"]["drifts"] == 4


def test_coverage_counts_each_source(app):
    c = app.get("/api/coverage").json
    assert c["total"] == 17 and c["explained"] == 13
    assert c["by_source"] == {"policy": 8, "ticket": 5, "decision_record": 0, "unexplained": 4}
    assert {r for r, src in c["rules"].items() if src == "unexplained"} == {"R-003", "R-012", "R-013", "R-014"}


def test_coverage_rises_when_a_record_is_saved(app):
    rec = {"rule_id": "R-014", "what": "w", "why": "y", "decided_by": "d", "decided_on": "2021",
           "sources": ["TKT-1135"], "risk_if_removed": "high", "risk_note": "n", "confidence": "high"}
    app.post("/api/records", json=rec)
    c = app.get("/api/coverage").json
    assert c["explained"] == 14 and c["rules"]["R-014"] == "decision_record"


def test_tickets_endpoint_serves_evidence(app):
    t = app.get("/api/tickets").json
    assert t["TKT-1135"]["title"] and t["TKT-1042"]["resolution"]


def test_unknown_pack_is_404(app):
    assert app.get("/api/tickets?pack=nope").status_code == 404


def test_saved_records_get_the_pack_domain(app):
    rec = {"rule_id": "R-013", "domain": "spoofed", "what": "w", "why": "y", "decided_by": "d", "decided_on": "2020",
           "sources": [], "risk_if_removed": "low", "risk_note": "n", "confidence": "high"}
    assert app.post("/api/records", json=rec).json["domain"] == "expense"


def test_clearing_one_domain_keeps_others_and_ids_stay_unique(local_records, offline_search):
    base = {"what": "w", "why": "y", "decided_by": "d", "decided_on": "2021", "sources": [],
            "risk_if_removed": "low", "risk_note": "n", "confidence": "high", "verified_by_expert": True}
    local_records.save_record(dict(base, rule_id="R-014", domain="expense"))     # DR-0001
    local_records.save_record(dict(base, rule_id="INV-003", domain="inventory"))  # DR-0002
    local_records.clear_records("expense")
    assert [r["rule_id"] for r in local_records.list_records()] == ["INV-003"]
    new = local_records.save_record(dict(base, rule_id="R-012", domain="expense"))
    assert new["record_id"] == "DR-0003"  # never reuses DR-0002
