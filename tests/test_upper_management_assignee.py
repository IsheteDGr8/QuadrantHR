from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


def test_get_upper_management_users() -> None:
    res = client.get("/api/users/upper-management")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    names = [u.get("name") for u in data]
    assert any(
        "Greg Davis" in n or "Sarah Jenkins" in n or "Alex Vance" in n for n in names
    )
    # Check that each returned user is in Upper Management department and has appropriate management role
    for u in data:
        dept = u.get("department", "")
        role = u.get("role", "")
        assert (
            "upper" in dept.lower()
            or "management" in dept.lower()
            or "operations" in dept.lower()
        )
        assert role != "Employee"


def test_non_upper_management_users_excluded() -> None:
    from database.crud import update_user_profile

    # Create or update non-upper management profiles
    update_user_profile(
        user_id="usr-test-it-emp",
        name="IT Specialist User",
        email="itspecialist@company.com",
        role="IT Specialist",
        department="IT Team",
    )
    update_user_profile(
        user_id="usr-test-general-emp",
        name="General Employee User",
        email="generalemp@company.com",
        role="Employee",
        department="General Staff",
    )

    res = client.get("/api/users/upper-management")
    assert res.status_code == 200
    data = res.json()
    returned_names = [u.get("name") for u in data]
    assert "IT Specialist User" not in returned_names
    assert "General Employee User" not in returned_names


def test_azure_login_defaults_to_general_staff() -> None:
    login_payload = {
        "azure_object_id": "test-oid-employee-999",
        "email": "standardemployee@company.com",
        "name": "Standard Employee",
    }
    res = client.post("/api/users/azure-login", json=login_payload)
    assert res.status_code == 200
    login_data = res.json()
    assert login_data["department"] == "General Staff"
    assert login_data["role"] == "Employee"

    # Verify this new user is NOT in the upper management approvers list
    res_approvers = client.get("/api/users/upper-management")
    approvers = res_approvers.json()
    approver_names = [u.get("name") for u in approvers]
    assert "Standard Employee" not in approver_names


def test_submit_leave_request_with_upper_management_assignee() -> None:
    payload = {
        "title": "Leave Request: Paid Time Off (PTO)",
        "description": "Dates: 2026-09-01 to 2026-09-05. Handover Lead: Jane Doe. Vacation time.",
        "category": "Time Off",
        "priority": "Medium",
        "department": "Upper Management",
        "department_override": "Upper Management",
        "assigned_to": "Greg Davis",
    }
    res = client.post("/api/tickets", json=payload)
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["department"] == "Upper Management"
    assert ticket["assigned_to"] == "Greg Davis"

    # Verify fetching ticket preserves assignee
    ticket_id = ticket["id"]
    get_res = client.get(f"/api/tickets/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["assigned_to"] == "Greg Davis"
