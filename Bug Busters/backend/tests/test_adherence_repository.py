import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock

import adherence_repository


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(adherence_repository, "storage", mock)
    return mock


def test_acknowledge_saves_record(mock_storage):
    result = adherence_repository.acknowledge("org1", "intern-1")

    assert result.org_id == "org1"
    assert result.user_id == "intern-1"

    path, data = mock_storage.save_json.call_args.args
    assert path == "org1/users/intern-1/adherence.json"
    assert data["user_id"] == "intern-1"


def test_get_acknowledgment_returns_none_when_absent(mock_storage):
    mock_storage.load_json.return_value = None

    result = adherence_repository.get_acknowledgment("org1", "intern-1")

    assert result is None


def test_get_acknowledgment_returns_record_when_present(mock_storage):
    mock_storage.load_json.return_value = {
        "org_id": "org1",
        "user_id": "intern-1",
    }

    result = adherence_repository.get_acknowledgment("org1", "intern-1")

    assert result is not None
    assert result.user_id == "intern-1"
