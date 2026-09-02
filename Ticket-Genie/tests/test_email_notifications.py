"""Test suite for Email Notifications and Notifications API."""

import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from database.crud import add_ticket_comment, create_ticket, update_ticket
from models.ticket import TicketCreate, TicketUpdate
from services.email_service import clear_outbox_log, get_outbox_log

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_outbox():
    clear_outbox_log()
    yield
    clear_outbox_log()


def wait_for_outbox(min_count: int = 1, timeout: float = 2.0):
    start = time.time()
    while time.time() - start < timeout:
        outbox = get_outbox_log()
        if len(outbox) >= min_count:
            return outbox
        time.sleep(0.05)
    return get_outbox_log()


def test_ticket_creation_triggers_email_and_notification():
    """Test that creating a ticket triggers an in-app notification and email outbox entry."""
    ticket_payload = TicketCreate(
        title="Email Test - VPN Connection Drop",
        description="Unable to reach corporate subnet via Cisco AnyConnect.",
        category="IT Support",
        priority="High",
        requester_id="testuser@company.com",
    )

    result = create_ticket(ticket_payload)
    assert result is not None
    assert result["id"].startswith("HD-")

    # Check email outbox log
    outbox = wait_for_outbox(1)
    assert len(outbox) >= 1

    creation_email = next(
        (e for e in outbox if "Ticket Confirmation" in e["subject"]), None
    )
    assert creation_email is not None
    assert creation_email["to"] == "testuser@company.com"
    assert result["id"] in creation_email["body_html"]
    assert "VPN Connection Drop" in creation_email["body_html"]


def test_ticket_status_update_triggers_email_and_notification():
    """Test that updating a ticket status generates a status change email and notification."""
    ticket_payload = TicketCreate(
        title="Email Test - Password Reset Request",
        description="Locked out after password expiration.",
        category="Account Access",
        priority="Medium",
        requester_id="employee_alex@company.com",
    )
    created = create_ticket(ticket_payload)
    ticket_id = created["id"]

    clear_outbox_log()

    # Update ticket status to In Progress
    update_payload = TicketUpdate(status="In Progress")
    updated = update_ticket(ticket_id, update_payload)

    assert updated is not None
    assert updated["status"] == "In Progress"

    outbox = wait_for_outbox(1)
    assert len(outbox) >= 1

    status_email = next((e for e in outbox if "Status Update" in e["subject"]), None)
    assert status_email is not None
    assert status_email["to"] == "employee_alex@company.com"
    assert "In Progress" in status_email["body_html"]


def test_ticket_comment_triggers_email_and_notification():
    """Test that posting a comment generates a comment notification email."""
    ticket_payload = TicketCreate(
        title="Email Test - Software Installation",
        description="Need Docker Desktop installed.",
        category="Software Request",
        priority="Low",
        requester_id="dev_user@company.com",
    )
    created = create_ticket(ticket_payload)
    ticket_id = created["id"]

    clear_outbox_log()

    comment_result = add_ticket_comment(
        ticket_id=ticket_id,
        message="IT Admin has approved your request. Installing software.",
        sender_id="admin_ops@company.com",
        sender_role="IT Specialist",
    )

    assert comment_result is not None
    assert comment_result["ticket_id"] == ticket_id

    outbox = wait_for_outbox(1)
    assert len(outbox) >= 1

    comment_email = next(
        (e for e in outbox if "New Message on Ticket" in e["subject"]), None
    )
    assert comment_email is not None
    assert comment_email["to"] == "dev_user@company.com"
    assert "Installing software" in comment_email["body_html"]
