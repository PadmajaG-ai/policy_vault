"""Gap Finder + Expert Interview.

find_gaps()          code: config rules nobody can explain (no policy rule, no linked ticket),
                     plus drifts whose root cause was not found.
interview_question() clues = tickets found by Vertex AI Search + tickets raised within 30 days
                     of the config change (code), then Gemini writes one specific question.
draft_record()       Gemini turns the expert's answer into a Decision Record (JSON schema).
                     A human verifies it before it is saved.
"""

import json
import re
from datetime import date

import gemini

CLUE_WINDOW_DAYS = 30
RISK = ["high", "medium", "low", "none"]


def find_gaps(report, config_rows, tickets):
    explained_by_policy = {f["rule_id"] for f in report["findings"]}
    explained_by_ticket = {r for t in tickets for r in t["related_rules"]}
    gaps = []
    for c in config_rows:
        if c["rule_id"] not in explained_by_policy and c["rule_id"] not in explained_by_ticket:
            gaps.append({"rule_id": c["rule_id"], "kind": "undocumented",
                         "summary": f"{c['entity']} / {c['attribute']} ({c['condition']}) = {c['value']} {c['unit']}"})
    for f in report["findings"]:
        if f["status"] == "drift" and not f.get("root_cause_found"):
            gaps.append({"rule_id": f["rule_id"], "kind": "unexplained drift",
                         "summary": f"{f['topic']}: policy {f['policy_value']} vs system {f['config_value']} {f['unit']}"})
    return gaps


def _days_between(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def find_clues(rule, tickets):
    """Candidate tickets: search hits + tickets close in time to the config change."""
    by_id = {t["ticket_id"]: t for t in tickets}
    clues = {}
    try:
        import search_index
        query = " ".join(re.split(r"[_=+]", f"{rule['entity']} {rule['attribute']} {rule['condition']}"))
        for link in search_index.search(query, page_size=3):
            m = re.search(r"TKT-\d+", link)
            if m and m.group() in by_id:
                clues[m.group()] = "found by search"
    except Exception as e:
        print(f"Search unavailable, using date clues only: {e}")
    for t in tickets:
        gap = _days_between(t["created"], rule["last_changed"])
        if gap <= CLUE_WINDOW_DAYS and not t["related_rules"]:
            clues[t["ticket_id"]] = f"raised {gap} days from the config change"
    return [dict(by_id[tid], clue=why) for tid, why in clues.items()]


def interview_question(rule, gap, tickets, expert_name):
    clues = find_clues(rule, tickets)
    schema = {
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING"},
            "cited_tickets": {"type": "ARRAY", "items": {"type": "STRING", "enum": [c["ticket_id"] for c in clues] or ["none"]}},
        },
        "required": ["question", "cited_tickets"],
    }
    prompt = f"""You are interviewing {expert_name}, the retired expert who configured this system.
Nobody can explain this configuration rule:
{json.dumps(rule, indent=1)}
Gap type: {gap['kind']}: {gap['summary']}

Possible clues from the ticket history (may or may not be related):
{json.dumps(clues, indent=1) if clues else "none"}

Write ONE short, specific interview question (max 60 words) that helps the expert remember WHY.
State the concrete facts: what the rule does, when it was changed and by whom.
If a clue ticket plausibly explains it (similar topic, close dates), mention it with its ID and
date and ask whether they are related. Only cite tickets you mention. Do not invent facts."""
    result = gemini.generate_json([prompt], schema)
    cited = [t for t in result.get("cited_tickets", []) if t in {c["ticket_id"] for c in clues}]
    return {"question": result["question"], "cited_tickets": cited, "clues": clues}


def draft_record(rule, question, cited_tickets, answer, expert_name, domain):
    schema = {
        "type": "OBJECT",
        "properties": {
            "what": {"type": "STRING", "description": "What the rule does, one sentence"},
            "why": {"type": "STRING", "description": "Why it exists, from the expert's answer, 1-2 sentences"},
            "decided_by": {"type": "STRING"},
            "decided_on": {"type": "STRING", "description": "YYYY-MM-DD or YYYY-MM"},
            "confirmed_tickets": {"type": "ARRAY", "items": {"type": "STRING", "enum": cited_tickets or ["none"]}},
            "risk_if_removed": {"type": "STRING", "enum": RISK},
            "risk_note": {"type": "STRING", "description": "What breaks or is exposed if the rule is removed"},
            "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
        },
        "required": ["what", "why", "decided_by", "decided_on", "confirmed_tickets", "risk_if_removed", "risk_note", "confidence"],
    }
    prompt = f"""Turn this expert interview into a Decision Record. Use ONLY what the expert said and
the rule facts. If the expert did not say something, write "unknown".
confirmed_tickets: only tickets the expert confirmed are related.

Rule: {json.dumps(rule)}
Question asked: {question}
{expert_name} answered: {answer}"""
    r = gemini.generate_json([prompt], schema)
    tickets = [t for t in r["confirmed_tickets"] if t in cited_tickets]
    return {
        "rule_id": rule["rule_id"],
        "domain": domain,
        "what": r["what"],
        "why": r["why"],
        "decided_by": r["decided_by"],
        "decided_on": r["decided_on"],
        "sources": tickets + [f"interview:{expert_name}"],
        "risk_if_removed": r["risk_if_removed"],
        "risk_note": r["risk_note"],
        "confidence": r["confidence"],
        "verified_by_expert": False,
    }
