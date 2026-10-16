"""Decision Records storage and Ask Why's guard-rails."""

from types import SimpleNamespace

import ask_why


def _record(rule_id):
    return {"rule_id": rule_id, "domain": "expense", "what": "w", "why": "y", "decided_by": "d",
            "decided_on": "2021", "sources": ["interview:R. Iyer"], "risk_if_removed": "high",
            "risk_note": "n", "confidence": "high", "verified_by_expert": True}


# ---- records ----

def test_ids_are_sequential_and_stable(local_records, offline_search):
    a = local_records.save_record(_record("R-014"))
    b = local_records.save_record(_record("R-013"))
    again = local_records.save_record(_record("R-014"))  # re-interview replaces, doesn't duplicate
    assert (a["record_id"], b["record_id"], again["record_id"]) == ("DR-0001", "DR-0002", "DR-0001")
    assert len(local_records.list_records()) == 2


def test_saved_records_are_indexed_for_search(local_records, offline_search):
    local_records.save_record(_record("R-014"))
    doc_id, text = offline_search.upserts[-1]
    assert doc_id == "DR-0001" and b"R-014" in text


def test_search_failure_does_not_lose_the_record(local_records, monkeypatch):
    import search_index
    monkeypatch.setattr(search_index, "upsert_document", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    local_records.save_record(_record("R-014"))
    assert len(local_records.list_records()) == 1


def test_firestore_failure_falls_back_to_local(local_records, offline_search, monkeypatch):
    monkeypatch.setattr(local_records, "backend", "firestore")
    monkeypatch.setattr(local_records, "_firestore", lambda: (_ for _ in ()).throw(RuntimeError("no database")))
    local_records.save_record(_record("R-012"))
    assert local_records.backend == "local"
    assert [r["rule_id"] for r in local_records.list_records()] == ["R-012"]


def test_clear(local_records, offline_search):
    local_records.save_record(_record("R-014"))
    local_records.clear_records()
    assert local_records.list_records() == []


# ---- ask why (Gemini faked; the guard-rails are real) ----

def _response(text, uris=()):
    chunks = [SimpleNamespace(retrieved_context=SimpleNamespace(uri=u)) for u in uris]
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(grounding_chunks=chunks))])


def test_sources_come_from_grounding_not_model_text(monkeypatch):
    monkeypatch.setattr(ask_why, "generate_with_retry",
                        lambda **k: _response("R-014 was hidden, see TKT-1135 and TKT-4242.", ["gs://b/ticket_TKT-1135.txt"]))
    r = ask_why.ask_why("q", [])
    assert r["sources"] == ["gs://b/ticket_TKT-1135.txt"]  # TKT-4242 is only claimed in text, not grounded


def test_record_counts_only_if_answer_names_record_and_rule(monkeypatch):
    recs = [dict(_record("R-014"), record_id="DR-0001"), dict(_record("R-013"), record_id="DR-0002")]
    monkeypatch.setattr(ask_why, "generate_with_retry",
                        lambda **k: _response("R-014: per DR-0001 the field stays hidden. Records DR-0001 through DR-0002 exist."))
    assert ask_why.ask_why("q", recs)["sources"] == ["DR-0001"]


def test_runaway_output_is_replaced(monkeypatch):
    loop = "\n".join(["I will search the tickets."] * 10)
    monkeypatch.setattr(ask_why, "generate_with_retry", lambda **k: _response(loop))
    r = ask_why.ask_why("q", [])
    assert r["guardrail"] is True and r["answer"].startswith(ask_why.NO_RATIONALE)


def test_empty_output_is_replaced(monkeypatch):
    monkeypatch.setattr(ask_why, "generate_with_retry", lambda **k: _response(None))
    assert ask_why.ask_why("q", [])["guardrail"] is True


def test_normal_answer_is_not_flagged():
    assert not ask_why.looks_degenerate("R-014\nHidden in 2021.\nSee TKT-1135.")
