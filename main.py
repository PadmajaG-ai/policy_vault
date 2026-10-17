"""Policy Vault web app: one Cloud Run service serving the UI and a small JSON API.

Every domain pack in data/<name>/ (expense, inventory, ...) runs through the same engine.
API calls take ?pack=<name>; the default is expense.
"""

import json
import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

import drift
import gaps
import records
from ask_why import ask_why

app = Flask(__name__)


def _load_pack(pack_dir):
    config, tickets = drift.load_pack(pack_dir)
    saved = drift.out_dir(pack_dir) / "drift_report.json"
    saved_report = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else None
    meta_file = pack_dir / "pack.json"
    return {
        "name": pack_dir.name,
        "dir": pack_dir,
        "meta": json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {"label": pack_dir.name.title()},
        "config": config,
        "rules": {r["rule_id"]: r for r in config},
        "domain": config[0]["domain"],
        "tickets": tickets,
        # Simulated retired expert (a human role in the demo, never in the agents' prompts)
        "expert": json.loads((pack_dir / "expert_answers.json").read_text(encoding="utf-8")),
        "saved": saved_report,
        "report": saved_report,
        "policy_rules": None,
        "findings": None,
    }


PACKS = {p.name: _load_pack(p) for p in sorted(Path("data").iterdir()) if (p / "config_rules.csv").exists()}
DEFAULT_PACK = "expense" if "expense" in PACKS else next(iter(PACKS))


def current():
    name = request.args.get("pack", DEFAULT_PACK)
    if name not in PACKS:
        abort(404)
    return PACKS[name]


def domain_records(p):
    return [r for r in records.list_records() if r.get("domain") == p["domain"]]


def error(e):
    print("ERROR:", repr(e))
    return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    p = current()
    handover = next((t for t in p["tickets"] if "retir" in t["title"].lower()), None)
    packs = [{"name": k, "label": v["meta"]["label"]} for k, v in PACKS.items()]
    return render_template("index.html", handover=handover, expert=p["expert"]["expert"],
                           pack=p["name"], meta=p["meta"], packs=packs,
                           n_rules=len(p["config"]), n_tickets=len(p["tickets"]))


# ---- scan, one real step per call so the UI shows true progress ----

@app.post("/api/scan/extract")
def scan_extract():
    p = current()
    try:
        p["policy_rules"] = drift.extract_step(p["dir"], cached=request.args.get("cached") == "1")
    except Exception as e:
        return error(e)
    matched = [r for r in p["policy_rules"] if r["matched_rule_id"] != "none"]
    return jsonify({"policy_rules": len(p["policy_rules"]), "matched": len(matched),
                    "policy_only": len(p["policy_rules"]) - len(matched)})


@app.post("/api/scan/compare")
def scan_compare():
    p = current()
    if not p["policy_rules"]:
        return jsonify({"error": "Run the extract step first"}), 400
    p["findings"] = drift.detect(p["policy_rules"], p["config"])
    findings = p["findings"][0]
    return jsonify({"checked": len(findings),
                    "drifts": sum(f["status"] == drift.DRIFT for f in findings),
                    "aligned": sum(f["status"] == drift.ALIGNED for f in findings),
                    "needs_review": sum(f["status"] == drift.REVIEW for f in findings)})


@app.post("/api/scan/explain")
def scan_explain():
    p = current()
    if not p["findings"]:
        return jsonify({"error": "Run the compare step first"}), 400
    findings, policy_only = p["findings"]
    try:
        drift.explain_drifts([f for f in findings if f["status"] == drift.DRIFT], p["tickets"])
    except Exception as e:
        return error(e)
    p["report"] = dict(drift.build_report(findings, policy_only), mode="live")
    return jsonify(p["report"])


@app.get("/api/scan/saved")
def scan_saved():
    p = current()
    if not p["saved"]:
        return jsonify({"error": "No saved scan for this pack"}), 404
    p["report"] = dict(p["saved"], mode="saved")
    return jsonify(p["report"])


@app.post("/api/scan")
def scan():
    """Whole scan in one call (CLI-style); falls back to the last saved scan."""
    p = current()
    try:
        p["report"] = dict(drift.scan(p["dir"], cached=request.args.get("cached") == "1"), mode="live")
    except Exception as e:
        if not p["saved"]:
            return error(e)
        print("Live scan failed, serving last saved scan:", repr(e))
        p["report"] = dict(p["saved"], mode="saved")
    return jsonify(p["report"])


# ---- evidence, gaps, coverage ----

@app.get("/api/tickets")
def tickets():
    return jsonify({t["ticket_id"]: t for t in current()["tickets"]})


@app.get("/api/coverage")
def coverage():
    p = current()
    if not p["report"]:
        return jsonify({"error": "Run a scan first"}), 400
    return jsonify(gaps.coverage(p["report"], p["config"], p["tickets"], domain_records(p)))


@app.get("/api/gaps")
def list_gaps():
    p = current()
    if not p["report"]:
        return jsonify({"error": "Run a scan first"}), 400
    done = {r["rule_id"] for r in domain_records(p)}
    found = gaps.find_gaps(p["report"], p["config"], p["tickets"])
    for g in found:
        g["recorded"] = g["rule_id"] in done
    return jsonify(found)


# ---- interview ----

@app.post("/api/interview/question")
def question():
    p = current()
    rule_id = request.json["rule_id"]
    gap = next(g for g in gaps.find_gaps(p["report"], p["config"], p["tickets"]) if g["rule_id"] == rule_id)
    try:
        return jsonify(gaps.interview_question(p["rules"][rule_id], gap, p["tickets"], p["expert"]["expert"]["name"]))
    except Exception as e:
        return error(e)


@app.get("/api/interview/expert_answer/<rule_id>")
def expert_answer(rule_id):
    """Play back the simulated expert's reply (in a real deployment the expert types it)."""
    a = next((a for a in current()["expert"]["answers"] if a["rule_id"] == rule_id), None)
    return jsonify({"answer": a["answer"] if a else ""})


@app.post("/api/interview/draft")
def draft():
    p, b = current(), request.json
    try:
        return jsonify(gaps.draft_record(p["rules"][b["rule_id"]], b["question"], b["cited_tickets"],
                                         b["answer"], p["expert"]["expert"]["name"], p["domain"]))
    except Exception as e:
        return error(e)


# ---- Decision Records + Ask Why ----

@app.get("/api/records")
def get_records():
    return jsonify({"records": domain_records(current()), "backend": records.backend})


@app.post("/api/records")
def save():
    rec = request.json
    rec["domain"] = current()["domain"]
    rec["verified_by_expert"] = True  # saved only after the human clicks "Verify & save"
    return jsonify(records.save_record(rec))


@app.delete("/api/records")
def reset():
    records.clear_records(current()["domain"])
    return jsonify({"ok": True})


@app.post("/api/ask")
def ask():
    p = current()
    try:
        return jsonify(ask_why(request.json["question"], domain_records(p)))
    except Exception as e:
        return error(e)


@app.get("/healthz")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
