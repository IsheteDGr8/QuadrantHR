from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from settings import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX
from logger import get_logger

logger = get_logger(__name__)

_client: SearchClient | None = None
_client_initialized = False


def _get_client() -> SearchClient | None:
    global _client, _client_initialized

    if not _client_initialized:
        _client_initialized = True

        if AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY and AZURE_SEARCH_INDEX:
            _client = SearchClient(
                endpoint=AZURE_SEARCH_ENDPOINT,
                index_name=AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(AZURE_SEARCH_KEY),
            )
        else:
            logger.warning(
                "Azure AI Search is not configured (AZURE_SEARCH_ENDPOINT / "
                "AZURE_SEARCH_KEY / AZURE_SEARCH_INDEX). Reference links will "
                "be unavailable."
            )

    return _client


def _escape_odata_literal(value: str) -> str:
    # OData string literals delimit with single quotes; a literal quote in
    # the value must be doubled, or it breaks out of the filter expression.
    return value.replace("'", "''")


def get_reference_links(policy_type: str, query_text: str = "", top: int = 3) -> list[dict]:
    client = _get_client()

    if client is None:
        return []

    try:
        results = client.search(
            search_text=query_text.strip() or "*",
            filter=f"policy_type eq '{_escape_odata_literal(policy_type)}'",
            top=top,
        )

        return [
            {
                "title": result.get("title"),
                "url": result.get("url"),
                "source": result.get("source"),
                "description": result.get("description"),
            }
            for result in results
        ]

    except Exception as exc:
        logger.error(f"Reference link search failed: {exc}")
        return []
