import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock

import training_repository


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(training_repository, "storage", mock)
    return mock


def test_create_link_resource(mock_storage):
    resource = training_repository.create_link_resource(
        "org1",
        title="Onboarding Video",
        description="Intro to company culture",
        category="Onboarding",
        url="https://example.com/video",
        uploaded_by_user_id="hr-1",
    )

    assert resource.resource_type == "link"
    assert resource.url == "https://example.com/video"
    mock_storage.save_json.assert_called_once()
    mock_storage.save_bytes.assert_not_called()


def test_create_file_resource_saves_bytes_and_metadata(mock_storage):
    resource = training_repository.create_file_resource(
        "org1",
        title="Employee Handbook",
        description="Full handbook",
        category="Handbook",
        original_filename="handbook.pdf",
        file_bytes=b"fake-pdf-bytes",
        uploaded_by_user_id="hr-1",
    )

    assert resource.resource_type == "file"
    assert resource.original_filename == "handbook.pdf"

    bytes_path, bytes_data = mock_storage.save_bytes.call_args.args
    assert bytes_path == f"org1/{resource.id}/file"
    assert bytes_data == b"fake-pdf-bytes"

    json_path, json_data = mock_storage.save_json.call_args.args
    assert json_path == f"org1/{resource.id}.json"
    assert json_data["original_filename"] == "handbook.pdf"


def test_list_resources_skips_raw_file_blobs(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/resource-1.json",
        "org1/resource-1/file",
    ]
    mock_storage.load_json.return_value = {
        "id": "resource-1",
        "org_id": "org1",
        "title": "Handbook",
        "description": "desc",
        "category": "Handbook",
        "resource_type": "file",
        "original_filename": "handbook.pdf",
        "uploaded_by_user_id": "hr-1",
    }

    result = training_repository.list_resources("org1")

    assert len(result) == 1
    mock_storage.load_json.assert_called_once_with("org1/resource-1.json")


def test_get_resource_file_bytes(mock_storage):
    mock_storage.load_bytes.return_value = b"fake-pdf-bytes"

    result = training_repository.get_resource_file_bytes("org1", "resource-1")

    assert result == b"fake-pdf-bytes"
    mock_storage.load_bytes.assert_called_once_with("org1/resource-1/file")


def test_delete_resource_tolerates_missing_file_blob(mock_storage):
    mock_storage.delete_blob.side_effect = [None, Exception("not found")]

    # Should not raise even though the second delete_blob call (the file
    # blob, which link-type resources never had) fails.
    training_repository.delete_resource("org1", "resource-1")

    assert mock_storage.delete_blob.call_count == 2
