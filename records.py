"""Decision Records: the core asset. Stored in Firestore, also pushed to Vertex AI Search.

If Firestore is unreachable (not created yet, no permission) the app keeps working with a
local JSON file, so the demo never breaks. The active backend is shown in the UI.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

COLLECTION = "decision_records"
LOCAL_FILE = Path("output") / "decision_records.json"

backend = os.environ.get("RECORDS_BACKEND", "firestore")
_db = None


def _firestore():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
    return _db


def _fallback(error):
    global backend
    print(f"Firestore unavailable, using local file: {error}")
    backend = "local"


def _read_local():
    if LOCAL_FILE.exists():
        return json.loads(LOCAL_FILE.read_text(encoding="utf-8"))
    return []


def _write_local(records):
    LOCAL_FILE.parent.mkdir(exist_ok=True)
    LOCAL_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def list_records():
    if backend == "firestore":
        try:
            docs = _firestore().collection(COLLECTION).stream()
            return sorted((d.to_dict() for d in docs), key=lambda r: r["record_id"])
        except Exception as e:
            _fallback(e)
    return _read_local()


def save_record(record):
    """Assign the next DR-000N id, store it, and index it for search. Returns the record."""
    existing = list_records()
    same_rule = [r for r in existing if r["rule_id"] == record["rule_id"]]
    record["record_id"] = same_rule[0]["record_id"] if same_rule else f"DR-{max((int(r['record_id'][3:]) for r in existing), default=0) + 1:04d}"
    record["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if backend == "firestore":
        try:
            _firestore().collection(COLLECTION).document(record["record_id"]).set(record)
        except Exception as e:
            _fallback(e)
    if backend == "local":
        _write_local([r for r in existing if r["record_id"] != record["record_id"]] + [record])

    _index_for_search(record)
    return record


def clear_records(domain=None):
    """Reset for a fresh demo run: all records, or only one domain's."""
    if backend == "firestore":
        try:
            for d in _firestore().collection(COLLECTION).stream():
                if domain is None or d.to_dict().get("domain") == domain:
                    d.reference.delete()
        except Exception as e:
            _fallback(e)
    _write_local([r for r in _read_local() if domain is not None and r.get("domain") != domain])


def _index_for_search(record):
    """Make the record findable by Ask Why's search grounding. Failure is not fatal."""
    try:
        import search_index
        text = (
            f"Decision Record {record['record_id']} for configuration rule {record['rule_id']}\n"
            f"What: {record['what']}\nWhy: {record['why']}\n"
            f"Decided by: {record['decided_by']} on {record['decided_on']}\n"
            f"Risk if removed: {record['risk_if_removed']}\n"
            f"Sources: {', '.join(record['sources'])}\nVerified by expert: {record['verified_by_expert']}\n"
        )
        search_index.upsert_document(record["record_id"], text.encode("utf-8"))
    except Exception as e:
        print(f"Search indexing skipped: {e}")
