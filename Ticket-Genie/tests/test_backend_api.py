from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


def test_read_root() -> None:
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "Running"
    assert "message" in data


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "TicketGenie API"


def test_create_and_get_ticket(monkeypatch) -> None:
    """
    Test the ticket API flow without calling the real GPT-5.2 service.

    The AI result is mocked only during this test so CI does not
    require Azure/OpenAI credentials.
    """

    def fake_classify_ticket(title: str, description: str):
        from agents.orchestrator import TicketClassification

        return TicketClassification(
            department="IT Team",
            category="Identity and Access Management",
            priority="High",
            confidence=0.95,
            reason="VPN access issue.",
            needs_human_review=False,
        )

    monkeypatch.setattr(
        "services.ticket_service.classify_ticket",
        fake_classify_ticket,
    )

    payload = {
        "title": "VPN Connection Issue",
        "description": (
            "Unable to connect to company VPN network from remote location."
        ),
    }

    response = client.post(
        "/api/tickets",
        json=payload,
    )

    assert response.status_code == 201

    created = response.json()

    ticket_id = created["id"]

    assert ticket_id.startswith("HD-")
    assert created["title"] == payload["title"]
    assert created["status"] == "Open"

    # Verify the mocked AI output was applied correctly.
    assert created["category"] == "Identity and Access Management"
    assert created["priority"] == "High"
    assert created["department"] == "IT Team"

    # Verify GET by ID.
    get_res = client.get(f"/api/tickets/{ticket_id}")

    assert get_res.status_code == 200

    ticket = get_res.json()

    assert ticket["id"] == ticket_id
    assert ticket["category"] == "Identity and Access Management"
    assert ticket["priority"] == "High"

    # Verify creator CANNOT set status to Resolved (403 Forbidden).
    creator_resolve_res = client.put(
        f"/api/tickets/{ticket_id}",
        json={"status": "Resolved"},
    )
    assert creator_resolve_res.status_code == 403
    assert (
        creator_resolve_res.json()["detail"]
        == "You cannot resolve tickets you created."
    )

    # Verify creator CAN update other fields (e.g. status to "In Progress" and priority to "Low").
    update_payload = {
        "status": "In Progress",
        "priority": "Low",
    }

    update_res = client.put(
        f"/api/tickets/{ticket_id}",
        json=update_payload,
    )

    assert update_res.status_code == 200
    updated = update_res.json()

    assert updated["id"] == ticket_id
    assert updated["status"] == "In Progress"
    assert updated["priority"] == "Low"

    # Verify a different user (support agent) CAN resolve the ticket.
    support_token = "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiOTk5OTk5OTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogInN1cHBvcnRAY29tcGFueS5jb20iLCAibmFtZSI6ICJTdXBwb3J0IEFnZW50IiwgInJvbGUiOiAiSVQgQWRtaW4iLCAiZXhwIjogMjUzNDAyMzAwNzk5fQ.mock"
    support_res = client.put(
        f"/api/tickets/{ticket_id}",
        json={"status": "Resolved"},
        headers={"Authorization": support_token},
    )
    assert support_res.status_code == 200
    assert support_res.json()["status"] == "Resolved"


def test_list_tickets() -> None:
    response = client.get("/api/tickets")

    assert response.status_code == 200

    tickets = response.json()

    assert isinstance(tickets, list)


def test_genie_chat() -> None:
    payload = {"message": "How do I check my payroll statement?"}

    response = client.post(
        "/api/genie/chat",
        json=payload,
    )

    assert response.status_code == 200

    reply = response.json()

    assert "reply" in reply
    assert "Payroll" in reply["reply"] or "payroll" in reply["reply"]


def test_get_ticket_not_found() -> None:
    response = client.get("/api/tickets/HD-9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_update_ticket_not_found() -> None:
    update_payload = {"status": "Resolved"}

    response = client.put(
        "/api/tickets/HD-9999",
        json=update_payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_azure_login_admin_check() -> None:
    from database.connection import SessionLocal
    from database.models_db import DepartmentUserDB

    test_oid = "test-admin-oid-1111-2222"
    with SessionLocal() as db:
        existing = (
            db.query(DepartmentUserDB).filter_by(azure_object_id=test_oid).first()
        )
        if not existing:
            db.add(
                DepartmentUserDB(
                    id="uobj-test-1111",
                    department_name="IT Team",
                    azure_object_id=test_oid,
                    role="Super Admin",
                    user_email="admin@company.com",
                    createdAt="2026-08-16T12:00:00",
                )
            )
            db.commit()

    payload = {
        "azure_object_id": test_oid,
        "email": "admin@company.com",
        "name": "Admin User",
    }

    response = client.post("/api/users/azure-login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["azure_object_id"] == test_oid
    assert data["is_admin"] is True
    assert data["role"] in ["Admin", "Super Admin"]


def test_prevent_duplicate_ticket_double_posting(monkeypatch) -> None:
    def fake_classify_ticket(title: str, description: str):
        from agents.orchestrator import TicketClassification

        return TicketClassification(
            department="IT Team",
            category="Identity and Access Management",
            priority="Medium",
            confidence=0.9,
            reason="Duplicate post test",
            needs_human_review=False,
        )

    monkeypatch.setattr(
        "services.ticket_service.classify_ticket",
        fake_classify_ticket,
    )

    payload = {
        "title": "Duplicate Submission Protection Test Ticket",
        "description": "Testing that rapid double posting returns the same ticket rather than creating duplicates.",
    }

    resp1 = client.post("/api/tickets", json=payload)
    assert resp1.status_code == 201
    t1 = resp1.json()

    resp2 = client.post("/api/tickets", json=payload)
    assert resp2.status_code == 201
    t2 = resp2.json()

    # The second POST should return the exact same ticket ID
    assert t1["id"] == t2["id"]
