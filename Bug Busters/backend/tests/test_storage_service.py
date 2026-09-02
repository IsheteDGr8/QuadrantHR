import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import storage_service


@patch("storage_service.BlobServiceClient")
def test_uses_connection_string_when_present(mock_client_cls, monkeypatch):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", "fake-conn-str")
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_ACCOUNT_NAME", "fakeaccount")
    mock_client_cls.from_connection_string.return_value = MagicMock()

    service = storage_service.StorageService()

    mock_client_cls.from_connection_string.assert_called_once_with("fake-conn-str")
    mock_client_cls.assert_not_called()
    assert service.container is not None


@patch("storage_service.DefaultAzureCredential")
@patch("storage_service.BlobServiceClient")
def test_uses_managed_identity_when_no_connection_string(
    mock_client_cls, mock_credential_cls, monkeypatch
):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", None)
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_ACCOUNT_NAME", "fakeaccount")
    mock_credential_cls.return_value = MagicMock()
    mock_client_cls.return_value = MagicMock()

    service = storage_service.StorageService()

    mock_client_cls.from_connection_string.assert_not_called()
    mock_client_cls.assert_called_once_with(
        account_url="https://fakeaccount.blob.core.windows.net",
        credential=mock_credential_cls.return_value,
    )
    assert service.container is not None


def test_unavailable_when_neither_configured(monkeypatch):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", None)
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_ACCOUNT_NAME", None)

    service = storage_service.StorageService()

    assert service.client is None
    assert service.container is None


@patch("storage_service.BlobServiceClient")
def test_defaults_to_generated_policies_container(mock_client_cls, monkeypatch):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", "fake-conn-str")
    mock_client = MagicMock()
    mock_client_cls.from_connection_string.return_value = mock_client

    storage_service.StorageService()

    mock_client.get_container_client.assert_called_once_with("generated-policies")


@patch("storage_service.BlobServiceClient")
def test_accepts_custom_container_name(mock_client_cls, monkeypatch):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", "fake-conn-str")
    mock_client = MagicMock()
    mock_client_cls.from_connection_string.return_value = mock_client

    storage_service.StorageService(container_name="source-documents")

    mock_client.get_container_client.assert_called_once_with("source-documents")


@patch("storage_service.BlobServiceClient")
def test_save_and_load_bytes(mock_client_cls, monkeypatch):
    monkeypatch.setattr(storage_service, "AZURE_STORAGE_CONNECTION_STRING", "fake-conn-str")
    mock_client = MagicMock()
    mock_client_cls.from_connection_string.return_value = mock_client
    mock_blob = MagicMock()
    mock_blob.readall.return_value = b"fake-bytes"
    mock_client.get_container_client.return_value.download_blob.return_value = mock_blob

    service = storage_service.StorageService()
    service.save_bytes("some/path", b"fake-bytes")
    result = service.load_bytes("some/path")

    service.container.upload_blob.assert_called_once_with(
        "some/path", b"fake-bytes", overwrite=True
    )
    assert result == b"fake-bytes"
