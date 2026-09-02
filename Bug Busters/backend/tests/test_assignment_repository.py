import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock

import assignment_repository


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(assignment_repository, "storage", mock)
    return mock


def test_assign_policy_saves_under_the_recipient(mock_storage):
    assignment = assignment_repository.assign_policy(
        "org1",
        "policy-1",
        policy_name="Code of Conduct",
        assigned_to_user_id="intern-abc",
        assigned_by_user_id="hr-xyz",
    )

    assert assignment.policy_id == "policy-1"
    assert assignment.assigned_to_user_id == "intern-abc"

    path, data = mock_storage.save_json.call_args.args
    assert path == "org1/users/intern-abc/assignments/policy-1.json"
    assert data["policy_name"] == "Code of Conduct"
    assert data["assigned_by_user_id"] == "hr-xyz"


def test_list_user_assignments_uses_correct_prefix(mock_storage):
    mock_storage.list_blobs.return_value = []

    assignment_repository.list_user_assignments("org1", "intern-abc")

    mock_storage.list_blobs.assert_called_once_with(
        prefix="org1/users/intern-abc/assignments/"
    )


def test_list_user_assignments_returns_sorted_by_assigned_at(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/users/intern-abc/assignments/policy-2.json",
        "org1/users/intern-abc/assignments/policy-1.json",
    ]
    mock_storage.load_json.side_effect = [
        {
            "policy_id": "policy-2",
            "policy_name": "Security Policy",
            "assigned_to_user_id": "intern-abc",
            "assigned_by_user_id": "hr-xyz",
            "assigned_at": "2026-01-02T00:00:00Z",
        },
        {
            "policy_id": "policy-1",
            "policy_name": "Code of Conduct",
            "assigned_to_user_id": "intern-abc",
            "assigned_by_user_id": "hr-xyz",
            "assigned_at": "2026-01-01T00:00:00Z",
        },
    ]

    result = assignment_repository.list_user_assignments("org1", "intern-abc")

    assert [a.policy_id for a in result] == ["policy-1", "policy-2"]
