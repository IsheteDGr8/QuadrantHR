import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock

import feedback_repository
from models import TicketStatus, TicketType


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(feedback_repository, "storage", mock)
    return mock


def test_create_ticket_saves_under_org_prefix(mock_storage):
    ticket = feedback_repository.create_ticket(
        "org1",
        type=TicketType.feedback,
        role="security",
        title="Security Policy feedback",
        body="This section is unclear about VPN usage.",
        created_by="manager@example.com",
    )

    assert ticket.type == TicketType.feedback
    assert ticket.status == TicketStatus.open
    assert ticket.resolved_at is None

    path, data = mock_storage.save_json.call_args.args
    assert path == f"org1/tickets/{ticket.id}.json"
    assert data["title"] == "Security Policy feedback"
    assert data["created_by"] == "manager@example.com"
    assert data["role"] == "security"


def test_create_ticket_defaults_role_to_none(mock_storage):
    ticket = feedback_repository.create_ticket(
        "org1",
        type=TicketType.reminder,
        title="Reminder: 2 pending signatures",
        body="Nudge for Alice, Bob.",
        created_by="manager@example.com",
    )

    assert ticket.role is None


def test_list_tickets_uses_correct_prefix(mock_storage):
    mock_storage.list_blobs.return_value = []

    feedback_repository.list_tickets("org1")

    mock_storage.list_blobs.assert_called_once_with(prefix="org1/tickets/")


def test_list_tickets_returns_newest_first(mock_storage):
    mock_storage.list_blobs.return_value = [
        "org1/tickets/ticket_a.json",
        "org1/tickets/ticket_b.json",
    ]
    mock_storage.load_json.side_effect = [
        {
            "id": "ticket_a",
            "type": "feedback",
            "role": None,
            "title": "Older",
            "body": "...",
            "status": "open",
            "created_by": "x@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "resolved_at": None,
        },
        {
            "id": "ticket_b",
            "type": "reminder",
            "role": None,
            "title": "Newer",
            "body": "...",
            "status": "open",
            "created_by": "y@example.com",
            "created_at": "2026-01-02T00:00:00Z",
            "resolved_at": None,
        },
    ]

    tickets = feedback_repository.list_tickets("org1")

    assert [t.id for t in tickets] == ["ticket_b", "ticket_a"]


def test_list_tickets_skips_missing_blobs(mock_storage):
    mock_storage.list_blobs.return_value = ["org1/tickets/ticket_a.json"]
    mock_storage.load_json.return_value = None

    tickets = feedback_repository.list_tickets("org1")

    assert tickets == []


def test_resolve_ticket_marks_resolved_and_stamps_time(mock_storage):
    mock_storage.load_json.return_value = {
        "id": "ticket_a",
        "type": "feedback",
        "role": None,
        "title": "Feedback",
        "body": "...",
        "status": "open",
        "created_by": "x@example.com",
        "created_at": "2026-01-01T00:00:00Z",
        "resolved_at": None,
    }

    ticket = feedback_repository.resolve_ticket("org1", "ticket_a")

    assert ticket.status == TicketStatus.resolved
    assert ticket.resolved_at is not None

    path, data = mock_storage.save_json.call_args.args
    assert path == "org1/tickets/ticket_a.json"
    assert data["status"] == "resolved"


def test_resolve_ticket_returns_none_when_not_found(mock_storage):
    mock_storage.load_json.return_value = None

    result = feedback_repository.resolve_ticket("org1", "missing")

    assert result is None
    mock_storage.save_json.assert_not_called()
