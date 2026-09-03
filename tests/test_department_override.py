"""
department_override tests.

Leave Management is the one request type that must route deterministically
to Upper Management and never go through AI classification - see
services/ticket_draft_service.LEAVE_DEPARTMENT and this module's
services/ticket_service.process_new_ticket. These tests exercise the real
POST /api/tickets endpoint end-to-end (matching this codebase's existing
integration-test convention, see tests/test_ticket_ai_integration.py)
rather than mocking the DB, and prove classify_ticket() is never even
called when a valid department_override is supplied.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from services import ticket_service

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MOCK_AI", "true")


def _boom(*args, **kwargs):
    raise AssertionError(
        "classify_ticket must not be called when department_override is set"
    )


def test_department_override_routes_to_upper_management_without_classification(
    monkeypatch,
):
    monkeypatch.setattr(ticket_service, "classify_ticket", _boom)
    response = client.post(
        "/api/tickets",
        json={
            "title": "Medical leave request",
            "description": "Requesting medical leave from August 20 to August 28.",
            "category": "Medical Leave",
            "department_override": "Upper Management",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["department"] == "Upper Management"
    assert ticket["category"] == "Medical Leave"
    assert ticket["classification_reason"]
    assert ticket["needs_human_review"] is False


def test_user_selected_department_override_is_authoritative(monkeypatch):
    monkeypatch.setattr(ticket_service, "classify_ticket", _boom)
    response = client.post(
        "/api/tickets",
        json={
            "title": "Laptop request mentioning payroll access",
            "description": "The requester explicitly selected IT despite mixed wording.",
            "category": "IT Support",
            "priority": "Medium",
            "department_override": "IT Team",
        },
    )

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["department"] == "IT Team"
    assert ticket["classification_reason"] == (
        "User-selected department override; AI routing and classification were skipped."
    )
    assert ticket["classification_confidence"] == 1.0


def test_department_override_absent_still_uses_normal_classification():
    # No override supplied - the normal AI classification path must still
    # run exactly as before this change (regression safety).
    response = client.post(
        "/api/tickets",
        json={
            "title": "Login issue",
            "description": "My account is locked and I cannot log in.",
        },
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["department"] == "IT Team"


def test_department_override_rejects_invalid_value():
    response = client.post(
        "/api/tickets",
        json={
            "title": "Some request",
            "description": "This should fail validation.",
            "department_override": "Not A Real Department",
        },
    )
    assert response.status_code == 422


def test_department_override_never_produces_general_department(monkeypatch):
    monkeypatch.setattr(ticket_service, "classify_ticket", _boom)
    response = client.post(
        "/api/tickets",
        json={
            "title": "PTO request",
            "description": "Requesting PTO next week for a family trip.",
            "category": "Paid Time Off (PTO)",
            "department_override": "Upper Management",
        },
    )
    assert response.status_code == 201
    assert response.json()["department"] != "General"
