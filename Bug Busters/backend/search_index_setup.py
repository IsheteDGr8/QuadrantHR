"""One-time script: creates (or updates the schema of) the Azure AI Search
index used for policy reference links.

Run manually, not part of the app's runtime:

    AZURE_SEARCH_ADMIN_KEY=<admin-key> python search_index_setup.py

Needs the search service's admin key (not the runtime query key in
AZURE_SEARCH_KEY/settings.py) — index management requires write access
that the app itself shouldn't hold day to day.
"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

from settings import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX


def main() -> None:
    admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")

    if not (AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_INDEX and admin_key):
        raise SystemExit(
            "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_INDEX (via .env or "
            "the environment) and AZURE_SEARCH_ADMIN_KEY before running this "
            "script."
        )

    client = SearchIndexClient(AZURE_SEARCH_ENDPOINT, AzureKeyCredential(admin_key))

    index = SearchIndex(
        name=AZURE_SEARCH_INDEX,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(
                name="policy_type",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SimpleField(name="url", type=SearchFieldDataType.String),
            SearchField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SearchableField(name="description", type=SearchFieldDataType.String),
        ],
    )

    client.create_or_update_index(index)
    print(f"Index '{AZURE_SEARCH_INDEX}' created/updated at {AZURE_SEARCH_ENDPOINT}.")


if __name__ == "__main__":
    main()
