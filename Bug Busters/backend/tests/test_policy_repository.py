import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock
from models import StoredPolicy
import policy_repository


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(policy_repository, "storage", mock)
    return mock


def test_create_policy(mock_storage):
    policy = StoredPolicy(
        company_name="Acme",
        policy_type="WFH",
        tone="Professional",
        requirements=["test"],
        content="Sample content",
    )
    result = policy_repository.create_policy("org1", policy)
    assert result.id == policy.id
    mock_storage.save_json.assert_called_once()


def test_update_policy_creates_version_snapshot(mock_storage):
    existing = StoredPolicy(
        company_name="Acme",
        policy_type="WFH",
        tone="Professional",
        requirements=["test"],
        content="Original content",
    )
    mock_storage.load_json.return_value = existing.model_dump()

    result = policy_repository.update_policy(
        "org1", existing.id, {"content": "New content"}, edited_by="hr-user"
    )

    assert result.content == "New content"
    assert result.version == 2
    assert mock_storage.save_json.call_count == 2

    version_path, version_data = mock_storage.save_json.call_args_list[0].args
    assert version_path == f"org1/{existing.id}/versions/1.json"
    assert version_data["content"] == "Original content"
    assert version_data["edited_by"] == "hr-user"


def test_update_policy_not_found(mock_storage):
    mock_storage.load_json.return_value = None

    result = policy_repository.update_policy("org1", "missing", {"content": "New content"})

    assert result is None
    mock_storage.save_json.assert_not_called()


def test_get_policy_history_returns_sorted_versions(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/policy-1/versions/2.json",
        "org1/policy-1/versions/1.json",
    ]
    mock_storage.load_json.side_effect = [
        {"policy_id": "policy-1", "version": 2, "content": "v2", "tone": "Professional"},
        {"policy_id": "policy-1", "version": 1, "content": "v1", "tone": "Professional"},
    ]

    result = policy_repository.get_policy_history("org1", "policy-1")

    assert [v.version for v in result] == [1, 2]


def test_list_policies_skips_version_blobs(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/policy-1.json",
        "org1/policy-1/versions/1.json",
    ]
    mock_storage.load_json.return_value = {
        "id": "policy-1",
        "company_name": "Acme",
        "policy_type": "WFH",
        "tone": "Professional",
        "requirements": ["test"],
        "content": "Sample content",
    }

    result = policy_repository.list_policies("org1")

    assert len(result) == 1


def test_list_policies_skips_per_user_blobs(mock_storage):
    # Regression test: assignment/adherence records live under
    # {org_id}/users/... and don't parse as StoredPolicy — this used to
    # 500 GET /policies/{org_id} for any org with an assignment record.
    mock_storage.list_blobs.return_value = [
        "org1/policy-1.json",
        "org1/users/intern-1/assignments/policy-1.json",
        "org1/users/intern-1/adherence.json",
    ]
    mock_storage.load_json.return_value = {
        "id": "policy-1",
        "company_name": "Acme",
        "policy_type": "WFH",
        "tone": "Professional",
        "requirements": ["test"],
        "content": "Sample content",
    }

    result = policy_repository.list_policies("org1")

    assert len(result) == 1
    mock_storage.load_json.assert_called_once_with("org1/policy-1.json")
    mock_storage.load_json.assert_called_once_with("org1/policy-1.json")