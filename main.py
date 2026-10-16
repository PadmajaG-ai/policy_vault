"""Policy Vault web app: one Cloud Run service serving the UI and a small JSON API."""

import csv
import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import drift
import gaps
import records
from ask_why import ask_why

app = Flask(__name__)

PACK = Path(os.environ.get("DOMAIN_PACK", "data/expense"))
SAVED_REPORT = Path("output") / "drift_report.json"

with open(PACK / "config_rules.csv", newline="", encoding="utf-8") as f:
    CONFIG = list(csv.DictReader(f))
RULES = {r["rule_id"]: r for r in CONFIG}
DOMAIN = CONFIG[0]["domain"]
TICKETS = json.loads((PACK / "tickets.json").read_text(encoding="utf-8"))
# Simulated retired expert (a human role in the demo, never shown to the agents' prompts)
EXPERT = json.loads((PACK / "expert_answers.json").read_text(encoding="utf-8"))
EXPERT_NAME = EXPERT["expert"]["name"]

state = {"report": json.loads(SAVED_REPORT.read_text(encoding="utf-8")) if SAVED_REPORT.exists() else None}


def error(e):
    print("ERROR:", repr(e))
    return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    handover = next((t for t in TICKETS if "retir" in t["title"].lower()), None)
    return render_template("index.html", handover=handover, expert=EXPERT["expert"], domain=DOMAIN)


@app.post("/api/scan")
def scan():
    """Live scan: Gemini extraction + code comparison + Gemini root cause."""
    try:
        state["report"] = drift.scan(PACK, cached=request.args.get("cached") == "1")
        state["report"]["mode"] = "live"
    except Exception as e:
        if not state["report"]:
            return error(e)
        print("Live scan failed, serving last saved scan:", repr(e))
        state["report"]["mode"] = "saved"
    return jsonify(state["report"])


@app.get("/api/gaps")
def list_gaps():
    if not state["report"]:
        return jsonify({"error": "Run a scan first"}), 400
    done = {r["rule_id"] for r in records.list_records()}
    found = gaps.find_gaps(state["report"], CONFIG, TICKETS)
    for g in found:
        g["recorded"] = g["rule_id"] in done
    return jsonify(found)


@app.post("/api/interview/question")
def question():
    rule_id = request.json["rule_id"]
    gap = next(g for g in gaps.find_gaps(state["report"], CONFIG, TICKETS) if g["rule_id"] == rule_id)
    try:
        return jsonify(gaps.interview_question(RULES[rule_id], gap, TICKETS, EXPERT_NAME))
    except Exception as e:
        return error(e)


@app.get("/api/interview/expert_answer/<rule_id>")
def expert_answer(rule_id):
    """Play back the simulated expert's reply (in a real deployment the expert types it)."""
    a = next((a for a in EXPERT["answers"] if a["rule_id"] == rule_id), None)
    return jsonify({"answer": a["answer"] if a else ""})


@app.post("/api/interview/draft")
def draft():
    b = request.json
    try:
        return jsonify(gaps.draft_record(RULES[b["rule_id"]], b["question"], b["cited_tickets"],
                                         b["answer"], EXPERT_NAME, DOMAIN))
    except Exception as e:
        return error(e)


@app.get("/api/records")
def get_records():
    return jsonify({"records": records.list_records(), "backend": records.backend})


@app.post("/api/records")
def save():
    rec = request.json
    rec["verified_by_expert"] = True  # saved only after the human clicks "Verify & save"
    return jsonify(records.save_record(rec))


@app.delete("/api/records")
def reset():
    records.clear_records()
    return jsonify({"ok": True})


@app.post("/api/ask")
def ask():
    try:
        return jsonify(ask_why(request.json["question"], records.list_records()))
    except Exception as e:
        return error(e)


@app.get("/healthz")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
