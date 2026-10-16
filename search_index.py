"""Vertex AI Search: the searchable index of company knowledge (policy, tickets, Decision Records).

The data store was created in the console (Layout parser with chunking). This module adds
documents to it directly with the API, e.g. each new Decision Record after an interview.
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


def upsert_document(doc_id, data, mime_type="text/plain"):
    """Add or replace one document. doc_id: letters, digits, '-' and '_' only."""
    de.DocumentServiceClient().update_document(
        request=de.UpdateDocumentRequest(
            document=de.Document(
                name=f"{BRANCH}/documents/{doc_id}",
                id=doc_id,
                content=de.Document.Content(raw_bytes=data, mime_type=mime_type),
            ),
            allow_missing=True,
        )
    )


def search(query, page_size=5):
    """Return the source links of the most relevant documents for a question."""
    response = de.SearchServiceClient().search(
        de.SearchRequest(serving_config=SERVING_CONFIG, query=query, page_size=page_size),
        timeout=10,
    )
    return [r.document.derived_struct_data.get("link", r.document.id) for r in response.results]
