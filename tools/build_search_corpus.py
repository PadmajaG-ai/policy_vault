"""Build the document set for the Vertex AI Search data store, for every pack given.

One text file per ticket (so search results cite a single ticket), plus each pack's policy PDF
(expense keeps the name policy.pdf; other packs get policy_<pack>.pdf).
Decision Records are added later by the app as they are created.

Never include ground_truth.json (answer key) or expert_answers.json (that knowledge
only exists in the retired expert's head until the interview captures it).

Run:  python tools/build_search_corpus.py data/expense data/inventory
Then: gcloud storage cp output/corpus/* gs://<bucket>/corpus/
      python tools/reimport_search.py
"""
import json
import shutil
import sys
from pathlib import Path

out = Path("output") / "corpus"
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)

for pack in map(Path, sys.argv[1:]):
    policy_name = "policy.pdf" if pack.name == "expense" else f"policy_{pack.name}.pdf"
    shutil.copy(pack / "policy.pdf", out / policy_name)

    tickets = json.loads((pack / "tickets.json").read_text(encoding="utf-8"))
    for t in tickets:
        text = (
            f"Ticket {t['ticket_id']} ({t['type']}), created {t['created']} by {t['raised_by']}\n"
            f"Title: {t['title']}\n\n"
            f"Description: {t['description']}\n\n"
            f"Resolution: {t['resolution']}\n"
        )
        if t["related_rules"]:
            text += f"Related configuration rules: {', '.join(t['related_rules'])}\n"
        (out / f"ticket_{t['ticket_id']}.txt").write_text(text, encoding="utf-8")
    print(f"[{pack.name}] {policy_name} + {len(tickets)} ticket files")

print(f"Corpus written to {out}")
