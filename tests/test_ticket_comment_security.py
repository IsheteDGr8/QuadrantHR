"""Security and behavior checks for the shared employee/HR ticket thread."""

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
TICKETS_API = (ROOT / "backend" / "api" / "tickets.py").read_text(encoding="utf-8")


def test_comment_sender_uses_verified_current_user():
    post = TICKETS_API[TICKETS_API.index("def post_comment_to_ticket") :]
    assert 'sender_id = current_user.get("oid")' in post
    assert "req.sender_id" not in post
    assert 'sender_role = "HR Support"' in post


def test_private_notes_require_admin_and_are_hidden_from_employees():
    assert 'detail="Private notes require admin access"' in TICKETS_API
    assert 'c.get("sender_role") != "Private"' in TICKETS_API


def test_comment_endpoints_reject_unknown_tickets():
    assert TICKETS_API.count('detail="Ticket not found"') >= 4


def test_employee_comment_view_excludes_private_hr_notes():
    from api.tickets import list_comments_for_ticket

    comments = [
        {"id": "public", "sender_role": "HR Support", "message": "Hello"},
        {"id": "private", "sender_role": "Private", "message": "Internal"},
    ]
    with (
        patch("api.tickets.get_ticket_by_id", return_value={"id": "HD-1"}),
        patch("database.crud.get_ticket_comments", return_value=comments),
    ):
        result = list_comments_for_ticket(
            "HD-1",
            db=MagicMock(),
            current_user={"oid": "employee-1", "role": "Employee"},
        )

    assert [comment["id"] for comment in result] == ["public"]


def test_hr_reply_identity_is_derived_from_verified_user():
    from api.tickets import CommentCreateRequest, post_comment_to_ticket

    with (
        patch("api.tickets.get_ticket_by_id", return_value={"id": "HD-1"}),
        patch("database.crud.add_ticket_comment") as add_comment,
    ):
        add_comment.return_value = {"sender_role": "HR Support", "message": "Reply"}
        post_comment_to_ticket(
            "HD-1",
            CommentCreateRequest(
                message="Reply",
                sender_id="forged-user",
                sender_role="Forged HR Role",
            ),
            db=MagicMock(),
            current_user={
                "oid": "verified-hr-oid",
                "role": "Admin",
                "department": "HR Team",
            },
        )

    add_comment.assert_called_once_with(
        ticket_id="HD-1",
        message="Reply",
        sender_id="verified-hr-oid",
        sender_role="HR Support",
        db=ANY,
    )


def test_employee_cannot_create_private_note():
    from api.tickets import CommentCreateRequest, post_comment_to_ticket

    with patch("api.tickets.get_ticket_by_id", return_value={"id": "HD-1"}):
        with pytest.raises(HTTPException) as exc:
            post_comment_to_ticket(
                "HD-1",
                CommentCreateRequest(message="Secret", sender_role="Private"),
                db=MagicMock(),
                current_user={"oid": "employee-1", "role": "Employee"},
            )

    assert exc.value.status_code == 403
