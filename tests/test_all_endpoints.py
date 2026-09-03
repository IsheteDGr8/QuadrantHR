import os
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)

from api.announcements import require_announcement_admin
from main import app

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_tickets_crud():
    # Create ticket
    payload = {
        "title": "Test Laptop Issue",
        "category": "IT Support",
        "description": "My laptop screen is flickering continuously.",
        "priority": "High",
    }
    res = client.post("/api/tickets", json=payload)
    assert res.status_code == 201
    ticket = res.json()
    assert "id" in ticket
    t_id = ticket["id"]

    # Get ticket
    res = client.get(f"/api/tickets/{t_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Test Laptop Issue"

    # Update ticket
    res = client.put(f"/api/tickets/{t_id}", json={"status": "In Progress"})
    assert res.status_code == 200
    assert res.json()["status"] == "In Progress"

    # Comments
    res = client.post(
        f"/api/tickets/{t_id}/comments",
        json={"message": "We are inspecting your laptop.", "sender_role": "IT Staff"},
    )
    assert res.status_code == 201

    res = client.get(f"/api/tickets/{t_id}/comments")
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_announcements_crud():
    res = client.get("/api/announcements")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.post(
        "/api/announcements",
        json={
            "title": "Test Alert",
            "content": "Server reboot tonight.",
            "category": "IT Notice",
        },
    )
    assert res.status_code == 201
    anc = res.json()
    assert anc["title"] == "Test Alert"

    res = client.delete(f"/api/announcements/{anc['id']}")
    assert res.status_code == 200


def test_announcement_creation_role_boundary():
    assert (
        require_announcement_admin({"role": "Admin", "oid": "admin-1"})["oid"]
        == "admin-1"
    )
    assert (
        require_announcement_admin({"role": "Super Admin", "oid": "super-1"})["oid"]
        == "super-1"
    )
    assert (
        require_announcement_admin({"role": "Ticketer", "oid": "ticketer-1"})["oid"]
        == "ticketer-1"
    )

    with pytest.raises(HTTPException) as error:
        require_announcement_admin({"role": "Employee", "oid": "employee-1"})
    assert error.value.status_code == 403


def test_notifications_crud():
    res = client.get("/api/notifications")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.post(
        "/api/notifications",
        json={
            "title": "Test Notif",
            "message": "Notification message body",
            "user_id": "dc3b56e9-9280-40dc-8d73-98bfd81fdd6a",
        },
    )
    assert res.status_code == 201
    notif = res.json()

    res = client.put(f"/api/notifications/{notif['id']}/read")
    assert res.status_code == 200


def test_onboarding_pipeline_endpoints():
    res = client.get("/api/onboarding")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.post(
        "/api/onboarding/suggest",
        json={
            "job_title": "Data Analyst",
            "start_date": "2026-09-08",
        },
    )
    assert res.status_code == 200
    suggestions = res.json()["tickets"]
    assert any(ticket["title"] == "Provision company laptop" for ticket in suggestions)
    assert any("Power BI" in ticket["title"] for ticket in suggestions)


def test_user_profile():
    res = client.get("/api/users/profile")
    assert res.status_code == 200

    res = client.put(
        "/api/users/profile", json={"name": "Nishita M.", "phone": "+1 555-999-0000"}
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Nishita M."


def test_admin_departments():
    res = client.get("/api/admin/departments")
    assert res.status_code == 200

    res = client.get("/api/admin/departments/users")
    assert res.status_code == 200


def test_genie_and_react():
    res = client.post("/api/genie/chat", json={"message": "How do I request PTO?"})
    assert res.status_code == 200
    assert "reply" in res.json()

    res = client.post("/api/genie/react", json={"message": "List open tickets"})
    assert res.status_code == 200
    assert "reply" in res.json()
