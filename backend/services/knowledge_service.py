"""
Knowledge / RAG retrieval boundary.

Retrieval against Azure AI Search is DETERMINISTIC and happens here - no
GPT call is involved in deciding which documents a user may see. Scope
filtering (role_service.get_allowed_scopes) is applied as a Search filter
BEFORE any chunk leaves this module, so the model is never shown content
outside the caller's authorized scopes. Query vectorization uses the
existing text-embedding-3-small deployment (embedding_service.py) - never
GPT-5.2 - and is used only to represent chunk/query CONTENT, never as an
authorization mechanism.

REAL INDEX ("group-1" on the AISEARCH_ENDPOINT already configured in .env
/ Key Vault): chunk-oriented schema - id (key), parent_id (filterable,
identifies the source document), content (searchable), contentVector
(vector, 1536 dims, text-embedding-3-small), category (filterable),
source (filterable). Every chunk carries its parent document's category
and source via Search index projections at ingestion time (see
scripts/setup_knowledge_indexer.py) - this module never has to re-derive
them. Other indexes exist on the same Search service (decacore-hr-policies,
employees-index, laidbackhr-knowledge-v1, training-chunks) but those
belong to other teams/projects and are intentionally NOT queried here.

The index currently holds both the 21 original whole-document records
(kept only for migration rollback - see scripts/migrate_knowledge_chunks.py)
and their 34 chunk records. Normal runtime retrieval here must only ever
surface CHUNKS: chunk records have parent_id set; originals don't. A
`parent_id ne null` filter enforces that deterministically, combined with
the category authorization filter - GPT never sees or controls either
condition. The migration/integrity scripts intentionally use their own
separate filters (`parent_id eq null` for originals) - they are not this
runtime path and are unaffected by it.
"""

import os
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from services.embedding_service import embedding_service

DEFAULT_INDEX_NAME = "group-1"


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    content: str
    scope: str
    source: str


class KnowledgeRetriever(Protocol):
    def search(
        self, query: str, allowed_scopes: List[str]
    ) -> List[KnowledgeDocument]: ...


class SearchUnavailableError(RuntimeError):
    """Raised when Azure AI Search can't be reached or isn't configured."""


class AzureSearchKnowledgeRetriever:
    """
    Real hybrid (keyword + vector) retrieval against the existing Azure AI
    Search index. Authorization filtering is applied as a native Search
    `filter` on every leg of the query (both the BM25 text search and the
    vector search use the same filter), so unauthorized chunks are never
    candidates in the first place - Azure AI Search enforces this natively,
    it isn't done by filtering results after the fact in Python.
    """

    def __init__(self, index_name: str = None, embedder=None):
        self._index_name = index_name or os.getenv(
            "AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME
        )
        self._embedder = embedder or embedding_service.embed
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        endpoint = os.getenv("AISEARCH_ENDPOINT")
        api_key = os.getenv("AISEARCH_APIKEY")
        if not endpoint or not api_key:
            raise SearchUnavailableError(
                "AISEARCH_ENDPOINT/AISEARCH_APIKEY are not configured."
            )

        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
        except ImportError as exc:
            raise SearchUnavailableError(
                "azure-search-documents is not installed."
            ) from exc

        self._client = SearchClient(
            endpoint=endpoint,
            index_name=self._index_name,
            credential=AzureKeyCredential(api_key),
        )
        return self._client

    def search(self, query: str, allowed_scopes: List[str]) -> List[KnowledgeDocument]:
        if not allowed_scopes:
            return []

        client = self._get_client()
        allowed = set(allowed_scopes)
        escaped_scopes = [scope.replace("'", "''") for scope in allowed_scopes]
        category_filter = " or ".join(
            f"category eq '{scope}'" for scope in escaped_scopes
        )
        # parent_id ne null: chunk records only - the 21 original
        # whole-document records (kept for rollback) have no parent_id and
        # must never be candidates in normal runtime retrieval. Deterministic
        # Python string composition, never GPT-controlled.
        filter_expr = f"parent_id ne null and ({category_filter})"

        try:
            from azure.search.documents.models import VectorFilterMode, VectorizedQuery

            query_vector = self._embedder(query)
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=5,
                fields="contentVector",
            )

            results = client.search(
                search_text=query,  # BM25/keyword leg
                vector_queries=[vector_query],  # vector leg
                filter=filter_expr,  # applied to BOTH legs by Azure AI Search
                vector_filter_mode=VectorFilterMode.PRE_FILTER,
                select=["id", "parent_id", "content", "category", "source"],
                top=5,
            )
            documents = [
                KnowledgeDocument(
                    id=result["id"],
                    content=result["content"],
                    scope=result.get("category", ""),
                    source=result.get("source") or result["id"],
                )
                for result in results
                if result.get("parent_id")  # defense-in-depth: chunks only
            ]
        except SearchUnavailableError:
            raise
        except Exception as exc:
            raise SearchUnavailableError(
                f"Azure AI Search hybrid request failed: {exc}"
            ) from exc

        # Defense-in-depth: the Search filter above is the real
        # authorization boundary, but never hand an unexpected
        # out-of-scope result to the model even if something upstream
        # (a filter bug, a bad manual document edit) ever let one through.
        return [doc for doc in documents if doc.scope in allowed]


default_knowledge_retriever = AzureSearchKnowledgeRetriever()


@dataclass
class KnowledgeAnswerResult:
    answer: str
    action: Optional[Any] = None
    verified: bool = True


def answer_question(
    query: str, allowed_scopes: List[str] = None
) -> KnowledgeAnswerResult:
    """Search knowledge base and return an answer result object."""
    try:
        results = default_knowledge_retriever.search(
            query, allowed_scopes=allowed_scopes or []
        )
        if results:
            content_summary = " ".join([doc.content for doc in results[:2]])
            return KnowledgeAnswerResult(answer=content_summary, verified=True)
    except Exception:
        pass

    return KnowledgeAnswerResult(
        answer=f"For policy questions regarding '{query}', please consult the HR portal or submit a support request.",
        verified=False,
    )


def search_knowledge(query: str, allowed_scopes: List[str] = None) -> List[dict]:
    try:
        results = default_knowledge_retriever.search(
            query, allowed_scopes=allowed_scopes or []
        )
        return [
            {"id": d.id, "content": d.content, "scope": d.scope, "source": d.source}
            for d in results
        ]
    except Exception:
        return []
