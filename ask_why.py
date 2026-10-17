"""Ask Why: Gemini answers "why is this rule configured this way?" with provable sources.

Grounded on the Vertex AI Search data store (policy + tickets) plus verified Decision Records.
"""

import json

from google.genai import types

from gemini import generate_with_retry
from search_index import DATA_STORE

search_tool = types.Tool(retrieval=types.Retrieval(
    vertex_ai_search=types.VertexAISearch(datastore=DATA_STORE)))

SYSTEM = (
    "You explain why an enterprise system (expense, inventory, procurement) is configured the way it is.\n"
    "Evidence you may use: the verified decision records in the prompt, and the documents "
    "returned by search (policy and tickets). Use nothing else.\n"
    "Rules:\n"
    "- Start by naming the configuration rule ID (e.g. R-014, INV-003) the question is about.\n"
    "- Cite ticket IDs (TKT-...) and record IDs (DR-...) you actually relied on.\n"
    "- If no evidence explains WHY something is the way it is, say exactly: "
    "'No recorded rationale found.' Then state what the evidence does show, and stop.\n"
    "- Never guess a reason. Never describe your search process.\n"
    "- Do not comment on which decision records are missing.\n"
    "- Keep the answer under 200 words."
    
)

NO_RATIONALE = "No recorded rationale found."


def looks_degenerate(text: str) -> bool:
    """Detect runaway output: the same lines repeated over and over."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) > 6 and len(set(lines)) < len(lines) / 2


NO_ANSWER = "The Vault could not produce a reliable answer this time. Please ask again."


def _diagnose(resp):
    """One log line explaining an empty or broken answer (finish reason, token use)."""
    try:
        c, u = resp.candidates[0], resp.usage_metadata
        return (f"finish={c.finish_reason} output_tokens={u.candidates_token_count} "
                f"thinking_tokens={getattr(u, 'thoughts_token_count', None)}")
    except Exception:
        return "no candidates"


def ask_why(question: str, decision_records: list[dict]) -> dict:
    prompt = (f"Verified decision records:\n{json.dumps(decision_records, indent=1)}\n\n"
              f"Question: {question}")
    # Thinking tokens count against max_output_tokens: 1024 left nothing for the answer
    # on hard questions. 4096 leaves room; the repetition guard below still stops loops.
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM, tools=[search_tool],
        temperature=0.2, max_output_tokens=4096)

    for attempt in range(2):  # one retry when the model returns nothing usable
        resp = generate_with_retry(contents=prompt, config=config)
        text = resp.text or ""
        if text.strip() and not looks_degenerate(text):
            break
        print(f"Ask Why guardrail (attempt {attempt + 1}): {_diagnose(resp)}")
    else:
        # Guardrail: never show a broken answer, and never claim "no rationale" we did not find
        return {"answer": NO_ANSWER, "sources": [], "guardrail": True}

    meta = resp.candidates[0].grounding_metadata
    doc_sources = [c.retrieved_context.uri for c in (meta.grounding_chunks or [])] if meta else []
    # Count a record as a source only if the answer names it AND its rule
    record_sources = [r["record_id"] for r in decision_records
                      if r["record_id"] in text and r["rule_id"] in text]
    return {"answer": text, "sources": sorted(set(doc_sources + record_sources)),
            "guardrail": False}
