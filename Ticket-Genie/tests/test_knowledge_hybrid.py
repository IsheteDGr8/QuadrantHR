"""
Tests for:
  - hybrid (BM25 + vector) knowledge retrieval (knowledge_service.py)
  - the hard rule that "General" is a knowledge access SCOPE only and can
    never be a ticket department/category value
All Azure/embedding calls are mocked - no live network calls.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import setup_knowledge_indexer  # noqa: E402

from services import chatbot_service, role_service, ticket_draft_service  # noqa: E402
from services.knowledge_service import (  # noqa: E402
    AzureSearchKnowledgeRetriever,
    SearchUnavailableError,
)


class FakeSearchClient:
    def __init__(self, documents=None, raise_error=None):
        self.documents = documents or []
        self.raise_error = raise_error
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_error:
            raise self.raise_error
        return self.documents


def _make_retriever(fake_client, embedder=None):
    retriever = AzureSearchKnowledgeRetriever(
        embedder=embedder or (lambda text: [0.1] * 1536)
    )
    retriever._client = fake_client  # bypass the live connection
    return retriever


# --- "General" is a knowledge scope only, never a department ---


def test_general_is_a_valid_knowledge_scope():
    assert "General" in role_service.get_allowed_scopes(
        role="Employee", department=None
    )


def test_general_is_never_in_department_scopes():
    assert "General" not in role_service.DEPARTMENT_SCOPES


def test_general_is_never_a_standard_ticket_category():
    assert "General" not in ticket_draft_service.STANDARD_CATEGORIES


def test_general_is_never_a_leave_type():
    assert "General" not in ticket_draft_service.LEAVE_TYPES


def test_general_category_is_rejected_as_a_ticket_category():
    # validate_category snaps to an exact allow-listed value or rejects -
    # "General" isn't in STANDARD_CATEGORIES, so it must be rejected.
    result = ticket_draft_service.validate_category(
        "General", ticket_draft_service.STANDARD_CATEGORIES
    )
    assert result is None


def test_canonical_department_scope_values_are_exact():
    assert role_service.DEPARTMENT_SCOPES == {
        "HR",
        "Accounting",
        "IT",
        "WorkplaceOperations",
    }
    assert role_service.MANAGEMENT_SCOPE == "UpperManagement"


def test_workplace_operations_canonical_value_grants_scope():
    assert role_service.get_allowed_scopes("Employee", "WorkplaceOperations") == [
        "General",
        "WorkplaceOperations",
    ]


def test_upper_management_canonical_value_via_role():
    # UpperManagement is granted through role_service's existing rule
    # (Management role), not invented here.
    assert role_service.get_allowed_scopes("Management", None) == [
        "General",
        "UpperManagement",
    ]


def test_a_broken_laptop_routes_to_it_never_general():
    category = ticket_draft_service.validate_category(
        "IT & Technology", ticket_draft_service.STANDARD_CATEGORIES
    )
    assert category == "IT & Technology"
    assert category != "General"


# --- Hybrid search: keyword + vector legs, authorization prefilter ---


def test_search_includes_both_keyword_and_vector_legs():
    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client)

    retriever.search("what is the PTO policy", ["General"])

    call = client.calls[0]
    assert call["search_text"] == "what is the PTO policy"
    assert len(call["vector_queries"]) == 1
    assert call["vector_queries"][0].fields == "contentVector"


def test_search_applies_category_authorization_filter_to_the_query():
    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client)

    retriever.search("badge access", ["General", "WorkplaceOperations"])

    call = client.calls[0]
    assert "category eq 'General'" in call["filter"]
    assert "category eq 'WorkplaceOperations'" in call["filter"]
    assert "HR" not in call["filter"]


def test_search_uses_pre_filter_mode_so_the_filter_applies_before_vector_selection():
    from azure.search.documents.models import VectorFilterMode

    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client)

    retriever.search("badge access", ["General"])

    assert client.calls[0]["vector_filter_mode"] == VectorFilterMode.PRE_FILTER


def test_unexpected_out_of_scope_result_is_rejected_before_returning():
    # Defense-in-depth: even if something upstream ever returned a
    # document outside the caller's allowed scopes, the retriever itself
    # must never hand it back.
    client = FakeSearchClient(documents=[])
    client.search = lambda **kwargs: [
        {
            "id": "1",
            "parent_id": "orig-1",
            "content": "general info",
            "category": "General",
            "source": "s",
        },
        {
            "id": "2",
            "parent_id": "orig-2",
            "content": "hr-only info",
            "category": "HR",
            "source": "s",
        },
    ]
    retriever = _make_retriever(client)

    results = retriever.search("anything", ["General"])

    assert [doc.id for doc in results] == ["1"]


def test_original_whole_document_records_are_excluded_from_runtime_retrieval():
    # Defense-in-depth: a result with no parent_id is an original
    # whole-document record (kept only for migration rollback) and must
    # never be surfaced by normal runtime retrieval, even if it matches
    # the category filter.
    client = FakeSearchClient(documents=[])
    client.search = lambda **kwargs: [
        {
            "id": "orig-1",
            "parent_id": None,
            "content": "whole doc",
            "category": "General",
            "source": "s",
        },
        {
            "id": "chunk-1",
            "parent_id": "orig-1",
            "content": "a chunk",
            "category": "General",
            "source": "s",
        },
    ]
    retriever = _make_retriever(client)

    results = retriever.search("anything", ["General"])

    assert [doc.id for doc in results] == ["chunk-1"]


def test_runtime_filter_excludes_originals_and_applies_authorization():
    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client)

    retriever.search("badge access", ["General", "WorkplaceOperations"])

    call = client.calls[0]
    assert "parent_id ne null" in call["filter"]
    assert "category eq 'General'" in call["filter"]
    assert "category eq 'WorkplaceOperations'" in call["filter"]


def test_embedder_is_called_with_the_query_text_not_gpt():
    seen = []

    def embedder(text):
        seen.append(text)
        return [0.0] * 1536

    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client, embedder=embedder)

    retriever.search("badge access", ["General"])

    assert seen == ["badge access"]


def test_embedding_failure_raises_search_unavailable():
    def failing_embedder(text):
        raise RuntimeError("embedding deployment unreachable")

    client = FakeSearchClient(documents=[])
    retriever = _make_retriever(client, embedder=failing_embedder)

    try:
        retriever.search("badge access", ["General"])
        raise AssertionError("expected SearchUnavailableError")
    except SearchUnavailableError:
        pass


def test_search_request_failure_raises_search_unavailable():
    client = FakeSearchClient(raise_error=RuntimeError("boom"))
    retriever = _make_retriever(client)

    try:
        retriever.search("badge access", ["General"])
        raise AssertionError("expected SearchUnavailableError")
    except SearchUnavailableError:
        pass


def test_no_allowed_scopes_returns_empty_without_calling_search():
    client = FakeSearchClient(
        documents=[{"id": "x", "content": "y", "category": "HR", "source": "z"}]
    )
    retriever = _make_retriever(client)

    results = retriever.search("anything", [])

    assert results == []
    assert client.calls == []


# --- Chunk metadata propagation (index projection config) ---


def test_index_projection_propagates_category_and_source_to_every_chunk():
    skillset = setup_knowledge_indexer._build_skillset(
        "https://fake", "fake-key", "group-1"
    )
    selector = skillset.index_projection.selectors[0]
    mapped_targets = {mapping.name for mapping in selector.mappings}

    assert {"content", "contentVector", "category", "source"} <= mapped_targets
    assert selector.parent_key_field_name == "parent_id"
    assert selector.target_index_name == "group-1"


def test_index_projection_never_targets_a_different_index():
    skillset = setup_knowledge_indexer._build_skillset(
        "https://fake", "fake-key", "group-1"
    )
    for selector in skillset.index_projection.selectors:
        assert selector.target_index_name == "group-1"


def test_chunked_indexer_never_creates_a_new_index():
    indexer = setup_knowledge_indexer._build_chunked_indexer("group-1")
    assert indexer.target_index_name == "group-1"
    assert indexer.skillset_name == setup_knowledge_indexer.SKILLSET_NAME


# --- No manual semantic keyword router exists ---


def test_no_manual_intent_classifier_in_chatbot_service():
    assert not hasattr(chatbot_service, "classify_intent")
    assert not hasattr(chatbot_service, "_LEAVE_NOUNS")
