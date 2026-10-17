"""Re-import the search corpus from Cloud Storage into the Vertex AI Search data store.

Same as console > AI Applications > data store > Import data > Cloud Storage, without the console.
Existing documents (same file paths) are updated in place.

Run:  gcloud storage cp output/corpus/* gs://policy-vault-510216-corpus/corpus/
      python tools/reimport_search.py
"""
import sys
from pathlib import Path

from google.cloud import discoveryengine_v1 as de

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from search_index import BRANCH, PROJECT  # noqa: E402

source = f"gs://{PROJECT}-corpus/corpus/*"
print(f"Importing {source}\n  into {BRANCH}")

operation = de.DocumentServiceClient().import_documents(
    request=de.ImportDocumentsRequest(
        parent=BRANCH,
        gcs_source=de.GcsSource(input_uris=[source], data_schema="content"),
        reconciliation_mode=de.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )
)
print("Import started; waiting (usually 1-5 minutes)...")
result = operation.result(timeout=900)
errors = list(result.error_samples)
print("Done." if not errors else f"Finished with {len(errors)} errors:")
for e in errors[:5]:
    print("  ", e.message)
print("Indexing can take a few more minutes. Then check: python tools/test_search.py")
