"""Build the document set for the Vertex AI Search data store.

One text file per ticket (so search results cite a single ticket), plus the policy PDF.
Decision Records are added later by the app as they are created.

Never include ground_truth.json (answer key) or expert_answers.json (that knowledge
only exists in the retired expert's head until the interview captures it).

Run:  python tools/build_search_corpus.py data/expense
Then: gcloud storage cp -r output/corpus/* gs://<bucket>/corpus/
"""
import json
import shutil
import sys
from pathlib import Path

pack = Path(sys.argv[1])
out = Path("output") / "corpus"
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)

shutil.copy(pack / "policy.pdf", out / "policy.pdf")

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

print(f"Wrote policy.pdf + {len(tickets)} ticket files to {out}")
