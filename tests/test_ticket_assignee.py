from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


def test_ticket_assignee_workflow(monkeypatch) -> None:
    def fake_classify_ticket(title: str, description: str):
        from agents.orchestrator import TicketClassification

        return TicketClassification(
            department="IT Team",
            category="Laptop Requests",
            priority="Medium",
            confidence=0.9,
            reason="Hardware replacement needed.",
            needs_human_review=False,
        )

    monkeypatch.setattr(
        "services.ticket_service.classify_ticket",
        fake_classify_ticket,
    )

    # 1. Create a ticket
    create_payload = {
        "title": "Need new laptop charger",
        "description": "My laptop charger is fraying and stopped working today.",
        "category": "Laptop Requests",
        "priority": "Medium",
    }
    res = client.post("/api/tickets", json=create_payload)
    assert res.status_code == 201
    ticket_data = res.json()
    ticket_id = ticket_data["id"]
    assert "assigned_to" in ticket_data
    assert ticket_data["assigned_to"] is None

    # 2. Assign ticket to self (Alex Vance)
    update_payload = {"assigned_to": "Alex Vance"}
    update_res = client.put(f"/api/tickets/{ticket_id}", json=update_payload)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["assigned_to"] == "Alex Vance"

    # 3. Check system comment generated for assignment
    comments_res = client.get(f"/api/tickets/{ticket_id}/comments")
    assert comments_res.status_code == 200
    comments = comments_res.json()
    system_comments = [
        c
        for c in comments
        if "[System] Ticket assigned to Alex Vance." in c.get("message", "")
    ]
    assert len(system_comments) > 0

    # 4. Test listing with assignee filter = "Alex Vance"
    list_res = client.get("/api/tickets?admin_view=true&assigned_to=Alex Vance")
    assert list_res.status_code == 200
    tickets = list_res.json()
    matching = [t for t in tickets if t["id"] == ticket_id]
    assert len(matching) == 1
    assert matching[0]["assigned_to"] == "Alex Vance"

    # 5. Test listing with assignee filter = "unassigned" (should not include ticket_id)
    unassigned_res = client.get("/api/tickets?admin_view=true&assigned_to=unassigned")
    assert unassigned_res.status_code == 200
    unassigned_tickets = unassigned_res.json()
    matching_unassigned = [t for t in unassigned_tickets if t["id"] == ticket_id]
    assert len(matching_unassigned) == 0

    # 6. Unassign ticket
    unassign_payload = {"assigned_to": ""}
    unassign_res = client.put(f"/api/tickets/{ticket_id}", json=unassign_payload)
    assert unassign_res.status_code == 200
    unassigned_data = unassign_res.json()
    assert unassigned_data["assigned_to"] is None

    # 7. Check unassigned ticket appears in unassigned filter
    unassigned_res2 = client.get("/api/tickets?admin_view=true&assigned_to=unassigned")
    assert unassigned_res2.status_code == 200
    unassigned_tickets2 = unassigned_res2.json()
    matching_unassigned2 = [t for t in unassigned_tickets2 if t["id"] == ticket_id]
    assert len(matching_unassigned2) == 1
