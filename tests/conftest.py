"""Shared fixtures. Offline tests never touch Google Cloud: Gemini and search are replaced by fakes."""

import csv
import json
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "data" / "expense"

# Real values from .env first (live tests need them); placeholders only if .env is missing.
# Offline tests never call the cloud, so placeholders are enough there.
load_dotenv(ROOT / ".env")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("DATA_STORE_ID", "test-store")
os.chdir(ROOT)  # the app reads data/ and output/ with relative paths
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real Gemini / Vertex AI Search (costs money, needs ADC)")


@pytest.fixture
def config_rows():
    with open(PACK / "config_rules.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def rules(config_rows):
    return {r["rule_id"]: r for r in config_rows}


@pytest.fixture
def tickets():
    return json.loads((PACK / "tickets.json").read_text(encoding="utf-8"))


@pytest.fixture
def truth():
    """Answer key. Allowed ONLY in tests and tools/evaluate.py."""
    return json.loads((PACK / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture
def policy_rules(truth, rules):
    """What a perfect extraction returns: policy values for the 12 checkable rules + 1 policy-only rule."""
    policy_values = {d["rule_id"]: str(d["policy_value"]) for d in truth["drifts"]}
    out = []
    for rid in [d["rule_id"] for d in truth["drifts"]] + truth["aligned_rules"]:
        value = policy_values.get(rid, rules[rid]["value"])
        if rid == "R-011":
            value = "economy_class"  # the real wording Gemini produced on the first run
        out.append({"matched_rule_id": rid, "value": value, "unit": rules[rid]["unit"],
                    "policy_source": "x", "quote": "q", "topic": rid, "match_confidence": "high"})
    out.append({"matched_rule_id": "none", "value": "vice_president", "unit": "role",
                "policy_source": "7.1", "quote": "q", "topic": "Business class approval", "match_confidence": "high"})
    return out


@pytest.fixture
def saved_report():
    return json.loads((ROOT / "output" / "drift_report.json").read_text(encoding="utf-8"))


@pytest.fixture
def offline_search(monkeypatch):
    """Vertex AI Search replaced by a controllable fake. Set .links to choose what it returns."""
    import search_index

    class FakeSearch:
        links = []
        fail = False
        upserts = []

        def search(self, query, page_size=5):
            if self.fail:
                raise RuntimeError("search offline")
            return self.links[:page_size]

        def upsert(self, doc_id, data, mime_type="text/plain"):
            self.upserts.append((doc_id, data))

    fake = FakeSearch()
    monkeypatch.setattr(search_index, "search", fake.search)
    monkeypatch.setattr(search_index, "upsert_document", fake.upsert)
    return fake


@pytest.fixture
def local_records(monkeypatch, tmp_path):
    """Decision Records in a temp file, never Firestore."""
    import records
    monkeypatch.setattr(records, "backend", "local")
    monkeypatch.setattr(records, "LOCAL_FILE", tmp_path / "records.json")
    return records
