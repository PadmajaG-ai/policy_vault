"""Web app endpoints (Gemini faked) and project hygiene: answer key isolation, no secrets, data check."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(local_records, offline_search, monkeypatch):
    import main
    offline_search.fail = True

    def fake(contents, schema):
        if "question" in schema["properties"]:
            return {"question": "Was it related to TKT-1135?", "cited_tickets": ["TKT-1135"]}
        return {"what": "w", "why": "ERP overflow", "decided_by": "r.kumar", "decided_on": "2021-09-06",
                "confirmed_tickets": ["TKT-1135"], "risk_if_removed": "high", "risk_note": "n", "confidence": "high"}

    import gemini
    monkeypatch.setattr(gemini, "generate_json", fake)
    return main.app.test_client()


def test_home_page_shows_the_handover_ticket(client):
    r = client.get("/")
    assert r.status_code == 200 and b"TKT-1202" in r.data


def test_full_interview_flow(client):
    assert [g["rule_id"] for g in client.get("/api/gaps").json] == ["R-012", "R-013", "R-014", "R-003"]
    q = client.post("/api/interview/question", json={"rule_id": "R-014"}).json
    answer = client.get("/api/interview/expert_answer/R-014").json["answer"]
    assert "ERP" in answer
    draft = client.post("/api/interview/draft", json={"rule_id": "R-014", "question": q["question"],
                                                       "cited_tickets": q["cited_tickets"], "answer": answer}).json
    assert draft["verified_by_expert"] is False
    saved = client.post("/api/records", json=draft).json
    assert saved["verified_by_expert"] is True and saved["record_id"] == "DR-0001"
    gap = next(g for g in client.get("/api/gaps").json if g["rule_id"] == "R-014")
    assert gap["recorded"] is True
    # a second judge can still run the interview: re-interviewing keeps the same record id
    again = client.post("/api/records", json=dict(draft)).json
    assert again["record_id"] == "DR-0001"
    client.delete("/api/records")
    assert client.get("/api/records").json["records"] == []


def test_scan_falls_back_to_saved_report(client, monkeypatch):
    import main
    monkeypatch.setattr(main.drift, "scan", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Gemini down")))
    r = client.post("/api/scan")
    assert r.status_code == 200 and r.json["mode"] == "saved" and r.json["summary"]["drifts"] == 4


def test_gaps_need_a_scan(client, monkeypatch):
    import main
    monkeypatch.setitem(main.PACKS["expense"], "report", None)
    assert client.get("/api/gaps").status_code == 400


def test_ask_errors_are_reported_not_crashed(client, monkeypatch):
    import main
    monkeypatch.setattr(main, "ask_why", lambda q, r: (_ for _ in ()).throw(RuntimeError("quota")))
    r = client.post("/api/ask", json={"question": "q"})
    assert r.status_code == 500 and "quota" in r.json["error"]


def test_health_endpoint(client):
    assert client.get("/health").status_code == 200


def test_recorded_gaps_can_be_interviewed_again():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "Interview again" in html


def test_requirements_are_pinned():
    lines = [l for l in (ROOT / "requirements.txt").read_text().splitlines() if l and not l.startswith("#")]
    assert lines and all("==" in l for l in lines)


def test_page_escapes_html():
    """Model output is inserted with esc(); make sure no raw innerHTML of model text slipped in."""
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "${d.root_cause}" not in html and "${q.question}" not in html and "${r.answer}" not in html


# ---- hygiene ----

def test_answer_key_is_never_read_by_the_app():
    app_files = [p for p in ROOT.glob("*.py")] + list((ROOT / "templates").glob("*"))
    offenders = [p.name for p in app_files if "ground_truth" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_search_corpus_excludes_answer_key_and_expert():
    corpus = ROOT / "output" / "corpus"
    if corpus.exists():
        names = {p.name for p in corpus.iterdir()}
        assert not any("ground_truth" in n or "expert" in n for n in names)


def test_no_secrets_tracked_in_git():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert ".env" not in tracked
    assert not [f for f in tracked if f.endswith(("-key.json", ".key")) or "service-account" in f]


def test_synthetic_data_is_consistent():
    r = subprocess.run([sys.executable, "tools/check_data.py"], cwd=ROOT, capture_output=True, text=True)
    assert "ALL CHECKS PASSED" in r.stdout, r.stdout
