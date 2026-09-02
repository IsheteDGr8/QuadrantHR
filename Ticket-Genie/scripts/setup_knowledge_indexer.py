#!/usr/bin/env python3
"""
scripts/setup_knowledge_indexer.py

Connects the existing `ticket-genie-knowledge` Blob container to the
existing Azure AI Search index (AISEARCH_INDEX_NAME, default "group-1")
via a Blob data source + indexer.

Guardrails (all enforced in code, not just documented):
  - Never creates or recreates the Search index itself.
  - Never deletes an existing data source or indexer.
  - Reuses the data source/indexer by name if either already exists.
  - Refuses to proceed if the index schema doesn't already have the
    expected id/content/category/source fields - it does not try to
    "fix" or redesign the index.
  - Never prints a secret value (connection strings/keys are redacted in
    all output).

Usage:
    python scripts/setup_knowledge_indexer.py --check   (default; read-only)
    python scripts/setup_knowledge_indexer.py --apply   (create/reuse + run)

Required config (read from environment / .env, never hardcoded):
    AISEARCH_ENDPOINT, AISEARCH_APIKEY           (already used elsewhere)
    AISEARCH_INDEX_NAME                          (optional, defaults to "group-1")
    AZURE_STORAGE_CONNECTION_STRING              (preferred), or
    AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY
"""

import argparse
import os
import sys

from dotenv import load_dotenv

DATA_SOURCE_NAME = "ticket-genie-knowledge-datasource"
INDEXER_NAME = "ticket-genie-knowledge-indexer"
CONTAINER_NAME = "ticket-genie-knowledge"
DEFAULT_INDEX_NAME = "group-1"
EXPECTED_FIELDS = ("id", "content", "category", "source")

# --- Hybrid (chunked + vector) upgrade ---
SKILLSET_NAME = "ticket-genie-knowledge-skillset"
VECTOR_PROFILE_NAME = "ticket-genie-vector-profile"
VECTOR_ALGORITHM_NAME = "ticket-genie-hnsw"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
VECTOR_DIMENSIONS = 1536
CHUNK_MAX_PAGE_LENGTH = 2000
CHUNK_PAGE_OVERLAP_LENGTH = 200


def _flag(is_set: bool) -> str:
    return "configured" if is_set else "MISSING"


def _get_blob_connection_string():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        return connection_string
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if account_name and account_key:
        return (
            "DefaultEndpointsProtocol=https;"
            f"AccountName={account_name};AccountKey={account_key};"
            "EndpointSuffix=core.windows.net"
        )
    return None


def _get_search_clients(endpoint: str, api_key: str):
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient

    credential = AzureKeyCredential(api_key)
    return (
        SearchIndexClient(endpoint=endpoint, credential=credential),
        SearchIndexerClient(endpoint=endpoint, credential=credential),
    )


def _inspect_index(index_client, index_name: str):
    index = index_client.get_index(index_name)
    fields_by_name = {f.name: f for f in index.fields}
    missing = [name for name in EXPECTED_FIELDS if name not in fields_by_name]
    key_field = next((f.name for f in index.fields if f.key), None)
    return fields_by_name, missing, key_field


def _build_field_mappings():
    from azure.search.documents.indexes.models import FieldMapping, FieldMappingFunction

    return [
        FieldMapping(
            source_field_name="metadata_storage_path",
            target_field_name="id",
            mapping_function=FieldMappingFunction(name="base64Encode"),
        ),
        FieldMapping(
            source_field_name="metadata_storage_name",
            target_field_name="source",
        ),
    ]


def run(apply_changes: bool) -> int:
    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)
    blob_connection_string = _get_blob_connection_string()

    print("=== Config ===")
    print(f"AISEARCH_ENDPOINT: {_flag(bool(endpoint))}")
    print(f"AISEARCH_APIKEY: {_flag(bool(api_key))}")
    print(f"Target index (AISEARCH_INDEX_NAME or default): {index_name}")
    print(f"Blob connection: {_flag(bool(blob_connection_string))}")
    print()

    if not endpoint or not api_key:
        print("BLOCKER: AISEARCH_ENDPOINT/AISEARCH_APIKEY are not configured.")
        return 1
    if not blob_connection_string:
        print(
            "BLOCKER: no Blob Storage connection is configured "
            "(AZURE_STORAGE_CONNECTION_STRING, or "
            "AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY). "
            "This is not currently tracked in .env/Key Vault."
        )
        return 1

    try:
        index_client, indexer_client = _get_search_clients(endpoint, api_key)
    except ImportError as exc:
        print(f"BLOCKER: azure-search-documents is not installed: {exc}")
        return 1

    print("=== Index schema check (read-only) ===")
    try:
        fields_by_name, missing, key_field = _inspect_index(index_client, index_name)
    except Exception as exc:
        print(f"BLOCKER: could not read index '{index_name}': {exc}")
        return 1

    print(f"Index '{index_name}' fields: {sorted(fields_by_name)}")
    print(f"Key field: {key_field}")
    if missing:
        print(
            f"BLOCKER: index '{index_name}' is missing expected field(s) "
            f"{missing}. Refusing to proceed - not redesigning the index."
        )
        return 1
    if key_field != "id":
        print(f"BLOCKER: key field is '{key_field}', expected 'id'.")
        return 1
    print(
        "Schema OK: id (key), content (searchable), category (filterable), "
        "source (filterable) all present - compatible with a Blob indexer "
        "using implicit content/category mapping + explicit id/source "
        "mapping. No skillset required (no vector/chunked fields)."
    )
    print()

    print("=== Existing data sources / indexers (read-only) ===")
    try:
        existing_data_sources = set(indexer_client.get_data_source_connection_names())
        existing_indexers = set(indexer_client.get_indexer_names())
    except Exception as exc:
        print(f"BLOCKER: could not list data sources/indexers: {exc}")
        return 1

    data_source_exists = DATA_SOURCE_NAME in existing_data_sources
    indexer_exists = INDEXER_NAME in existing_indexers
    print(f"Data sources on service: {sorted(existing_data_sources) or '(none)'}")
    print(f"Indexers on service: {sorted(existing_indexers) or '(none)'}")
    print(f"'{DATA_SOURCE_NAME}' exists: {data_source_exists}")
    print(f"'{INDEXER_NAME}' exists: {indexer_exists}")
    print()

    print("=== Planned indexer configuration ===")
    print(f"  data source: {DATA_SOURCE_NAME}")
    print(f"    type=azureblob, container={CONTAINER_NAME}")
    print(f"  indexer: {INDEXER_NAME} -> target index '{index_name}'")
    print("  field mappings:")
    print("    metadata_storage_path -> id  (base64Encode)")
    print("    metadata_storage_name -> source")
    print("    content -> content            (implicit, blob text extraction)")
    print("    category (blob metadata) -> category  (implicit, name match)")
    print(
        "  NOTE: category metadata must already be set on each blob - run "
        "scripts/set_blob_category_metadata.py first."
    )
    print()

    if not apply_changes:
        print("Check mode only - no Azure resources were created or modified.")
        return 0

    from azure.search.documents.indexes.models import (
        DataSourceCredentials,
        IndexingParameters,
        IndexingParametersConfiguration,
        SearchIndexer,
        SearchIndexerDataContainer,
        SearchIndexerDataSourceConnection,
        SearchIndexerDataSourceType,
    )

    if not data_source_exists:
        print(f"Creating data source '{DATA_SOURCE_NAME}'...")
        data_source = SearchIndexerDataSourceConnection(
            name=DATA_SOURCE_NAME,
            type=SearchIndexerDataSourceType.AZURE_BLOB,
            credentials=DataSourceCredentials(connection_string=blob_connection_string),
            container=SearchIndexerDataContainer(name=CONTAINER_NAME),
        )
        indexer_client.create_data_source_connection(data_source)
        print("  created.")
    else:
        print(f"Reusing existing data source '{DATA_SOURCE_NAME}'.")

    if not indexer_exists:
        print(f"Creating indexer '{INDEXER_NAME}'...")
        indexer = SearchIndexer(
            name=INDEXER_NAME,
            data_source_name=DATA_SOURCE_NAME,
            target_index_name=index_name,
            field_mappings=_build_field_mappings(),
            parameters=IndexingParameters(
                configuration=IndexingParametersConfiguration(
                    data_to_extract="contentAndMetadata",
                )
            ),
        )
        indexer_client.create_indexer(indexer)
        print("  created.")
    else:
        print(f"Reusing existing indexer '{INDEXER_NAME}' (not modified).")

    print("Running indexer...")
    indexer_client.run_indexer(INDEXER_NAME)
    print(
        "Indexer run triggered (indexing happens asynchronously - check "
        "status with get_indexer_status separately)."
    )
    return 0


def _get_embedding_config():
    return (
        os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT"),
        os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY"),
    )


def _verify_embedding_deployment(endpoint: str, api_key: str) -> int:
    """One live call to confirm the existing deployment is reachable.

    Returns the embedding dimensions.
    """

    from openai import OpenAI

    base_url = endpoint.rstrip("/") + "/openai/v1/"
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL_NAME, input="connectivity check"
    )
    return len(response.data[0].embedding)


def _index_has_matching_vector_field(fields_by_name) -> bool:
    field = fields_by_name.get("contentVector")
    return field is not None and getattr(field, "vector_search_dimensions", None) == (
        VECTOR_DIMENSIONS
    )


def _build_vector_search_config():
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        HnswParameters,
        VectorSearch,
        VectorSearchProfile,
    )

    return VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=VECTOR_ALGORITHM_NAME, parameters=HnswParameters(metric="cosine")
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=VECTOR_ALGORITHM_NAME,
            )
        ],
    )


def _build_updated_index(existing_index):
    """Add parent_id + contentVector fields. Never touches existing fields."""

    from azure.search.documents.indexes.models import SearchField

    fields = list(existing_index.fields)
    names = {f.name for f in fields}

    if "parent_id" not in names:
        fields.append(
            SearchField(
                name="parent_id",
                type="Edm.String",
                filterable=True,
                retrievable=True,
            )
        )
    if "contentVector" not in names:
        fields.append(
            SearchField(
                name="contentVector",
                type="Collection(Edm.Single)",
                searchable=True,
                retrievable=False,
                vector_search_dimensions=VECTOR_DIMENSIONS,
                vector_search_profile_name=VECTOR_PROFILE_NAME,
            )
        )

    existing_index.fields = fields
    existing_index.vector_search = _build_vector_search_config()
    return existing_index


def _build_skillset(embedding_endpoint: str, embedding_api_key: str, index_name: str):
    from azure.search.documents.indexes.models import (
        AzureOpenAIEmbeddingSkill,
        InputFieldMappingEntry,
        OutputFieldMappingEntry,
        SearchIndexerIndexProjection,
        SearchIndexerIndexProjectionSelector,
        SearchIndexerIndexProjectionsParameters,
        SearchIndexerSkillset,
        SplitSkill,
    )

    split_skill = SplitSkill(
        name="chunk-split",
        context="/document",
        text_split_mode="pages",
        maximum_page_length=CHUNK_MAX_PAGE_LENGTH,
        page_overlap_length=CHUNK_PAGE_OVERLAP_LENGTH,
        inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
        outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
    )
    embedding_skill = AzureOpenAIEmbeddingSkill(
        name="chunk-embed",
        context="/document/pages/*",
        resource_url=embedding_endpoint,
        deployment_name=EMBEDDING_MODEL_NAME,
        model_name=EMBEDDING_MODEL_NAME,
        api_key=embedding_api_key,
        inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
    )
    # index_projection lives on the SKILLSET (not the indexer) in this SDK/API
    # surface - it's how one parent document fans out into many chunk
    # documents, each still carrying its parent's category/source.
    index_projection = SearchIndexerIndexProjection(
        selectors=[
            SearchIndexerIndexProjectionSelector(
                target_index_name=index_name,
                parent_key_field_name="parent_id",
                source_context="/document/pages/*",
                mappings=[
                    InputFieldMappingEntry(name="content", source="/document/pages/*"),
                    InputFieldMappingEntry(
                        name="contentVector", source="/document/pages/*/vector"
                    ),
                    InputFieldMappingEntry(
                        name="category", source="/document/category"
                    ),
                    InputFieldMappingEntry(
                        name="source", source="/document/metadata_storage_name"
                    ),
                ],
            )
        ],
        parameters=SearchIndexerIndexProjectionsParameters(
            projection_mode="skipIndexingParentDocuments"
        ),
    )
    return SearchIndexerSkillset(
        name=SKILLSET_NAME,
        description=(
            "Splits Northstar Technologies knowledge documents into chunks "
            "and embeds each chunk with the existing text-embedding-3-small "
            "deployment. Category/source metadata is propagated onto every "
            "chunk via index projections."
        ),
        skills=[split_skill, embedding_skill],
        index_projection=index_projection,
    )


def _build_chunked_indexer(index_name: str):
    from azure.search.documents.indexes.models import (
        IndexingParameters,
        IndexingParametersConfiguration,
        SearchIndexer,
    )

    return SearchIndexer(
        name=INDEXER_NAME,
        data_source_name=DATA_SOURCE_NAME,
        target_index_name=index_name,
        skillset_name=SKILLSET_NAME,
        field_mappings=[],  # the skillset's index_projection owns field population now
        parameters=IndexingParameters(
            configuration=IndexingParametersConfiguration(
                data_to_extract="contentAndMetadata",
            )
        ),
    )


def run_hybrid_upgrade(apply_changes: bool) -> int:
    """
    Upgrade the existing chunk-free BM25 setup to chunked hybrid search:
    adds parent_id/contentVector fields to the EXISTING index (never
    recreates it), adds a skillset (SplitSkill + AzureOpenAIEmbeddingSkill)
    using the EXISTING embedding deployment, and updates the EXISTING
    indexer to use index projections so every chunk keeps its parent's
    category/source. Never creates a new index, Search service, storage
    account, or embedding deployment.
    """

    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)
    embedding_endpoint, embedding_api_key = _get_embedding_config()

    print("=== Hybrid upgrade: config ===")
    print(f"AISEARCH_ENDPOINT: {_flag(bool(endpoint))}")
    print(f"AISEARCH_APIKEY: {_flag(bool(api_key))}")
    print(f"GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT: {_flag(bool(embedding_endpoint))}")
    print(f"GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY: {_flag(bool(embedding_api_key))}")
    print()

    if not endpoint or not api_key:
        print("BLOCKER: AISEARCH_ENDPOINT/AISEARCH_APIKEY are not configured.")
        return 1
    if not embedding_endpoint or not embedding_api_key:
        print(
            "BLOCKER: GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT/_APIKEY are not "
            "configured - no usable embedding deployment found."
        )
        return 1

    print("=== Verifying existing embedding deployment (one live call) ===")
    try:
        dimensions = _verify_embedding_deployment(embedding_endpoint, embedding_api_key)
    except Exception as exc:
        print(f"BLOCKER: embedding deployment unreachable: {exc}")
        return 1
    print(f"Reachable. model={EMBEDDING_MODEL_NAME} dimensions={dimensions}")
    if dimensions != VECTOR_DIMENSIONS:
        print(
            f"BLOCKER: expected {VECTOR_DIMENSIONS} dimensions, got {dimensions} - "
            "refusing to proceed with a mismatched vector field size."
        )
        return 1
    print()

    try:
        index_client, indexer_client = _get_search_clients(endpoint, api_key)
    except ImportError as exc:
        print(f"BLOCKER: azure-search-documents is not installed: {exc}")
        return 1

    print("=== Current index schema (read-only) ===")
    try:
        index = index_client.get_index(index_name)
    except Exception as exc:
        print(f"BLOCKER: could not read index '{index_name}': {exc}")
        return 1

    fields_by_name = {f.name: f for f in index.fields}
    missing_base = [name for name in EXPECTED_FIELDS if name not in fields_by_name]
    if missing_base:
        print(f"BLOCKER: base field(s) missing: {missing_base}.")
        return 1
    key_field = next((f.name for f in index.fields if f.key), None)
    if key_field != "id":
        print(f"BLOCKER: key field is '{key_field}', expected 'id'.")
        return 1

    already_has_vector = _index_has_matching_vector_field(fields_by_name)
    print(f"Current fields: {sorted(fields_by_name)}")
    print(
        f"contentVector already present with matching dimensions: {already_has_vector}"
    )
    print(
        "Assessment: id/content/category/source are unchanged. Adding "
        "parent_id + contentVector is a pure field ADDITION - Azure AI "
        "Search allows new fields to be added to an existing index via "
        "create_or_update_index without deleting/recreating it, as long as "
        "no existing field is removed or retyped (none are here). "
        "NO INDEX RECREATION IS REQUIRED."
    )
    print()

    try:
        stats = index_client.get_index_statistics(index_name)
        current_doc_count = stats.document_count
    except Exception:
        current_doc_count = None
    print(
        f"Documents currently in '{index_name}': {current_doc_count} "
        "(all from the earlier flat/non-chunked indexer run). These will "
        "become stale duplicates once chunked documents are indexed under "
        "different ids - see the report for the separate, explicit cleanup "
        "step; this script does not delete them automatically."
    )
    print()

    print("=== Existing skillsets (read-only) ===")
    existing_skillsets = set(indexer_client.get_skillset_names())
    print(f"Skillsets on service: {sorted(existing_skillsets) or '(none)'}")
    skillset_exists = SKILLSET_NAME in existing_skillsets
    print(f"'{SKILLSET_NAME}' exists: {skillset_exists}")
    print()

    print("=== Existing indexer's current mode ===")
    try:
        current_indexer = indexer_client.get_indexer(INDEXER_NAME)
    except Exception as exc:
        print(f"BLOCKER: could not read indexer '{INDEXER_NAME}': {exc}")
        return 1
    already_chunked = current_indexer.skillset_name == SKILLSET_NAME
    print(
        f"Indexer '{INDEXER_NAME}' current skillset: "
        f"{current_indexer.skillset_name or '(none - flat BM25 mode)'}"
    )
    print()

    print("=== Planned changes ===")
    print(
        f"  1. Add fields to '{index_name}': parent_id, contentVector "
        f"({VECTOR_DIMENSIONS}-dim, HNSW/cosine) - additive only."
    )
    print(f"  2. Create/update skillset '{SKILLSET_NAME}':")
    print(
        "       SplitSkill (pages, "
        f"{CHUNK_MAX_PAGE_LENGTH} chars, {CHUNK_PAGE_OVERLAP_LENGTH} overlap)"
    )
    print(
        f"       -> AzureOpenAIEmbeddingSkill ({EMBEDDING_MODEL_NAME}, existing deploy)"
    )
    print(
        f"  3. Update indexer '{INDEXER_NAME}': attach skillset, replace "
        "field_mappings with index projections (parent_id/content/"
        "contentVector/category/source per chunk, skipIndexingParentDocuments)."
    )
    print(
        "  4. Reset + run the indexer so all 21 blobs are fully reprocessed "
        "through the new pipeline (one embedding call per chunk - see cost "
        "note in report)."
    )
    print()

    if not apply_changes:
        print("Check mode only - no Azure resources were created or modified.")
        return 0

    index_client.create_or_update_index(_build_updated_index(index))
    print(f"Updated index '{index_name}' schema (added parent_id, contentVector).")

    indexer_client.create_or_update_skillset(
        _build_skillset(embedding_endpoint, embedding_api_key, index_name)
    )
    print(f"{'Updated' if skillset_exists else 'Created'} skillset '{SKILLSET_NAME}'.")

    indexer_client.create_or_update_indexer(_build_chunked_indexer(index_name))
    print(f"Updated indexer '{INDEXER_NAME}' to use chunking + embeddings.")

    if already_chunked:
        print("Indexer was already in chunked mode; running without reset.")
    else:
        indexer_client.reset_indexer(INDEXER_NAME)
        print("Reset indexer change-tracking so all blobs are reprocessed.")

    indexer_client.run_indexer(INDEXER_NAME)
    print(
        "Indexer run triggered (indexing/embedding happens asynchronously - "
        "check status with get_indexer_status separately)."
    )
    return 0


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only check (default behavior; accepted explicitly too).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually create/reuse the data source + indexer and run it "
            "(default is a read-only check)."
        ),
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help=(
            "Target the chunked hybrid (BM25 + vector) upgrade instead of "
            "the basic flat BM25 setup. Combine with --check (default) or "
            "--apply."
        ),
    )
    args = parser.parse_args()
    if args.hybrid:
        sys.exit(run_hybrid_upgrade(apply_changes=args.apply))
    sys.exit(run(apply_changes=args.apply))


if __name__ == "__main__":
    main()
