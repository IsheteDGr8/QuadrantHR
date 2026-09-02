import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import search_service


def _reset_client_cache():
    search_service._client = None
    search_service._client_initialized = False


@patch("search_service.SearchClient")
def test_returns_links_when_configured(mock_client_cls, monkeypatch):
    _reset_client_cache()
    monkeypatch.setattr(search_service, "AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_KEY", "fake-key")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_INDEX", "policy-reference-links")

    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "title": "HIPAA Security Rule",
            "url": "https://www.hhs.gov/hipaa/for-professionals/security/index.html",
            "source": "U.S. Department of Health & Human Services",
            "description": "Federal standards for protecting electronic personal health information.",
        }
    ]
    mock_client_cls.return_value = mock_client

    results = search_service.get_reference_links("Security Policy")

    assert len(results) == 1
    assert results[0]["title"] == "HIPAA Security Rule"

    mock_client.search.assert_called_once_with(
        search_text="*",
        filter="policy_type eq 'Security Policy'",
        top=3,
    )


def test_returns_empty_list_when_not_configured(monkeypatch):
    _reset_client_cache()
    monkeypatch.setattr(search_service, "AZURE_SEARCH_ENDPOINT", None)
    monkeypatch.setattr(search_service, "AZURE_SEARCH_KEY", None)
    monkeypatch.setattr(search_service, "AZURE_SEARCH_INDEX", None)

    results = search_service.get_reference_links("Security Policy")

    assert results == []


@patch("search_service.SearchClient")
def test_returns_empty_list_on_search_error(mock_client_cls, monkeypatch):
    _reset_client_cache()
    monkeypatch.setattr(search_service, "AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_KEY", "fake-key")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_INDEX", "policy-reference-links")

    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("service unavailable")
    mock_client_cls.return_value = mock_client

    results = search_service.get_reference_links("Security Policy")

    assert results == []


@patch("search_service.SearchClient")
def test_escapes_single_quote_in_policy_type(mock_client_cls, monkeypatch):
    _reset_client_cache()
    monkeypatch.setattr(search_service, "AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_KEY", "fake-key")
    monkeypatch.setattr(search_service, "AZURE_SEARCH_INDEX", "policy-reference-links")

    mock_client = MagicMock()
    mock_client.search.return_value = []
    mock_client_cls.return_value = mock_client

    search_service.get_reference_links("Manager's Policy")

    mock_client.search.assert_called_once_with(
        search_text="*",
        filter="policy_type eq 'Manager''s Policy'",
        top=3,
    )
