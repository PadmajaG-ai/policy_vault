"""Vertex AI Search: the searchable index of company knowledge (policy, tickets, Decision Records).

The data store was created in the console (Layout parser with chunking). New documents,
e.g. each Decision Record after an interview, go in through Cloud Storage + import.
"""

import os

from dotenv import load_dotenv
from google.cloud import discoveryengine_v1 as de

load_dotenv()

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
DATA_STORE = (f"projects/{PROJECT}/locations/global/collections/default_collection"
              f"/dataStores/{os.environ['DATA_STORE_ID']}")
BRANCH = f"{DATA_STORE}/branches/default_branch"
SERVING_CONFIG = f"{DATA_STORE}/servingConfigs/default_config"
BUCKET = os.environ.get("CORPUS_BUCKET", f"{PROJECT}-corpus")


def upsert_document(doc_id, data, mime_type="text/plain"):
    """Add or replace one document (e.g. a Decision Record) in the search index.

    The data store uses the layout parser, which rejects raw bytes sent inline
    ('document.data is required'). So the file goes to Cloud Storage and that one file is
    imported, the same route as tools/reimport_search.py. Import runs in the background
    (about a minute); the app does not wait for it.
    """
    from google.cloud import storage
    path = f"records/{doc_id}.txt"
    storage.Client(project=PROJECT).bucket(BUCKET).blob(path).upload_from_string(data, content_type=mime_type)
    de.DocumentServiceClient().import_documents(
        request=de.ImportDocumentsRequest(
            parent=BRANCH,
            gcs_source=de.GcsSource(input_uris=[f"gs://{BUCKET}/{path}"], data_schema="content"),
            reconciliation_mode=de.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )
    )


def search(query, page_size=5):
    """Return the source links of the most relevant documents for a question."""
    response = de.SearchServiceClient().search(
        de.SearchRequest(serving_config=SERVING_CONFIG, query=query, page_size=page_size),
        timeout=10,
    )
    return [r.document.derived_struct_data.get("link", r.document.id) for r in response.results]
