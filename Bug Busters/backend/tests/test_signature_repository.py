import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock

import signature_repository


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(signature_repository, "storage", mock)
    return mock


def test_sign_policy_saves_and_returns_signature(mock_storage):
    signature = signature_repository.sign_policy(
        "org1",
        "policy-1",
        signer_user_id="user-abc",
        signer_roles=["Intern"],
        signed_name="Jane Doe",
    )

    assert signature.policy_id == "policy-1"
    assert signature.signer_user_id == "user-abc"
    assert signature.signed_name == "Jane Doe"

    path, data = mock_storage.save_json.call_args.args
    assert path == "org1/policy-1/signatures/user-abc.json"
    assert data["signed_name"] == "Jane Doe"


def test_get_signature_returns_none_when_not_signed(mock_storage):
    mock_storage.load_json.return_value = None

    result = signature_repository.get_signature("org1", "policy-1", "user-abc")

    assert result is None
    mock_storage.load_json.assert_called_once_with(
        "org1/policy-1/signatures/user-abc.json"
    )


def test_get_signature_returns_signature_when_present(mock_storage):
    mock_storage.load_json.return_value = {
        "policy_id": "policy-1",
        "signer_user_id": "user-abc",
        "signer_roles": ["Intern"],
        "signed_name": "Jane Doe",
    }

    result = signature_repository.get_signature("org1", "policy-1", "user-abc")

    assert result is not None
    assert result.signed_name == "Jane Doe"


def test_list_signatures_returns_sorted_by_signed_at(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/policy-1/signatures/user-b.json",
        "org1/policy-1/signatures/user-a.json",
    ]
    mock_storage.load_json.side_effect = [
        {
            "policy_id": "policy-1",
            "signer_user_id": "user-b",
            "signed_name": "Bob",
            "signed_at": "2026-01-02T00:00:00Z",
        },
        {
            "policy_id": "policy-1",
            "signer_user_id": "user-a",
            "signed_name": "Alice",
            "signed_at": "2026-01-01T00:00:00Z",
        },
    ]

    result = signature_repository.list_signatures("org1", "policy-1")

    assert [s.signed_name for s in result] == ["Alice", "Bob"]


def test_signing_again_overwrites_not_duplicates(mock_storage):
    signature_repository.sign_policy(
        "org1", "policy-1", signer_user_id="user-abc", signer_roles=["Intern"], signed_name="Jane Doe"
    )
    signature_repository.sign_policy(
        "org1", "policy-1", signer_user_id="user-abc", signer_roles=["Intern"], signed_name="Jane D. Doe"
    )

    assert mock_storage.save_json.call_count == 2
    first_path = mock_storage.save_json.call_args_list[0].args[0]
    second_path = mock_storage.save_json.call_args_list[1].args[0]
    assert first_path == second_path
