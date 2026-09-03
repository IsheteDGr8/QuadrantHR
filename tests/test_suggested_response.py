"""Suggested HR response agent, authorization, context, and UI wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from agents.response_agent import EmployeeResponse, draft_response

ROOT = Path(__file__).resolve().parents[1]
INBOX = (ROOT / "frontend" / "admin_AV" / "inbox.html").read_text(encoding="utf-8")
API_JS = (ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
TICKET_DETAIL = (
    ROOT / "frontend" / "src" / "views" / "TicketDetailView.svelte"
).read_text(encoding="utf-8")


class FakeAIService:
    def __init__(self):
        self.call = None

    def generate(self, *, system_prompt, user_content, response_model):
        self.call = (system_prompt, user_content, response_model)
        return EmployeeResponse(
            message="Thank you for sharing this. We would like to discuss next steps.",
            suggested_actions=["Confirm a private meeting time"],
            safety_notice_required=True,
        )


def test_response_agent_uses_ticket_and_existing_conversation():
    ai = FakeAIService()
    result = draft_response(
        "Workplace concern",
        "The employee reported a sensitive concern.",
        category="Employee Relationships",
        priority="High",
        queue="HR Team",
        conversation_history="Employee: I am available tomorrow.",
        ai_service=ai,
    )
    assert result.safety_notice_required is True
    assert "I am available tomorrow" in ai.call[1]
    assert "Do not claim an action was completed" in ai.call[0]
    assert "2-4 short, actionable bullet fragments" in ai.call[0]
    assert "12 words or fewer" in ai.call[0]
    assert "Do not include paragraphs" in ai.call[0]


def test_hr_suggestion_endpoint_excludes_private_notes():
    from api.tickets import suggest_response_for_ticket

    ticket = {
        "id": "HD-1",
        "title": "Workplace concern",
        "description": "Sensitive concern",
        "category": "Employee Relationships",
        "priority": "High",
        "department": "HR Team",
    }
    comments = [
        {"createdAt": "now", "sender_role": "Employee", "message": "Public context"},
        {"createdAt": "now", "sender_role": "Private", "message": "Internal note"},
    ]
    expected = EmployeeResponse(message="Suggested response")
    with (
        patch("api.tickets.get_ticket_by_id", return_value=ticket),
        patch("database.crud.get_ticket_comments", return_value=comments),
        patch(
            "agents.response_agent.draft_response", return_value=expected
        ) as generate,
    ):
        result = suggest_response_for_ticket(
            "HD-1",
            db=MagicMock(),
            current_user={"oid": "hr-1", "role": "Admin", "department": "HR Team"},
        )
    assert result == expected
    history = generate.call_args.kwargs["conversation_history"]
    assert "Public context" in history
    assert "Internal note" not in history


def test_employee_cannot_generate_hr_response():
    from api.tickets import suggest_response_for_ticket

    with pytest.raises(HTTPException) as exc:
        suggest_response_for_ticket(
            "HD-1",
            db=MagicMock(),
            current_user={"oid": "employee-1", "role": "Employee"},
        )
    assert exc.value.status_code == 403


def test_ticketer_can_generate_response_for_own_department():
    from api.tickets import suggest_response_for_ticket

    ticket = {
        "id": "HD-2",
        "title": "Laptop issue",
        "description": "The laptop will not start.",
        "category": "IT & Technology",
        "priority": "Medium",
        "department": "IT Team",
    }
    expected = EmployeeResponse(message="Suggested IT response")
    with (
        patch("api.tickets.get_ticket_by_id", return_value=ticket),
        patch("database.crud.get_ticket_comments", return_value=[]),
        patch("agents.response_agent.draft_response", return_value=expected),
    ):
        result = suggest_response_for_ticket(
            "HD-2",
            db=MagicMock(),
            current_user={
                "oid": "ticketer-1",
                "role": "Ticketer",
                "department": "IT Team",
            },
        )
    assert result == expected


def test_ticketer_cannot_generate_response_for_another_department():
    from api.tickets import suggest_response_for_ticket

    with (
        patch(
            "api.tickets.get_ticket_by_id",
            return_value={"id": "HD-3", "department": "HR Team"},
        ),
        pytest.raises(HTTPException) as exc,
    ):
        suggest_response_for_ticket(
            "HD-3",
            db=MagicMock(),
            current_user={
                "oid": "ticketer-1",
                "role": "Ticketer",
                "department": "IT Team",
            },
        )
    assert exc.value.status_code == 403


def test_admin_can_generate_response_across_departments():
    from api.tickets import suggest_response_for_ticket

    ticket = {
        "id": "HD-4",
        "title": "Laptop issue",
        "description": "The laptop will not start.",
        "category": "IT & Technology",
        "priority": "Medium",
        "department": "IT Team",
    }
    expected = EmployeeResponse(message="Suggested admin response")
    with (
        patch("api.tickets.get_ticket_by_id", return_value=ticket),
        patch("database.crud.get_ticket_comments", return_value=[]),
        patch("agents.response_agent.draft_response", return_value=expected),
    ):
        result = suggest_response_for_ticket(
            "HD-4",
            db=MagicMock(),
            current_user={
                "oid": "admin-1",
                "role": "Admin",
                "department": "HR Team",
            },
        )
    assert result == expected


def test_hr_ui_fills_draft_but_never_auto_sends():
    assert "async function apiSuggestTicketResponse" in API_JS
    assert "/suggested-response" in API_JS
    assert "Suggest reply" in INBOX
    assert "async function suggestReply" in INBOX
    suggest_region = INBOX[
        INBOX.index("async function suggestReply") : INBOX.index(
            "async function sendReply"
        )
    ]
    assert "textarea.value = suggestion.message" in suggest_region
    assert "sendReply(" not in suggest_region
    assert "AI-generated draft" in suggest_region
    assert "../js/api.js?v=20260818_4" in INBOX


def test_current_admin_ui_renders_ai_next_steps_and_safety_notice():
    assert "res.suggested_actions" in TICKET_DETAIL
    assert "What to do next" in TICKET_DETAIL
    assert "aiSuggestedActions as action" in TICKET_DETAIL
    assert "res.safety_notice_required" in TICKET_DETAIL
    assert "Sensitive case:" in TICKET_DETAIL
