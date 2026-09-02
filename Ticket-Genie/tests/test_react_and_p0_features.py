"""Unit and integration tests for ReAct Agent Loop Engine, Text-to-SQL, PDF Export, and Admin APIs."""

import pytest
from fastapi.testclient import TestClient

from agents.react_orchestrator import ReActResult, run_react_agent_loop
from backend.main import app
from services.document_service import generate_ticket_docx, generate_ticket_pdf
from services.sql_context_service import (
    SQLValidationError,
    execute_sql_query,
    validate_and_sanitize_sql,
)

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


def test_react_agent_loop_execution():
    result = run_react_agent_loop("Move ticket HD-1001 to IT Team", role="Super Admin")
    assert isinstance(result, ReActResult)
    assert result.final_response
    assert result.iterations_used >= 1
    assert len(result.steps) >= 1


def test_text_to_sql_execution_and_security():
    # Valid SELECT
    select_res = execute_sql_query(
        "SELECT COUNT(*) as cnt FROM tickets", role="Super Admin"
    )
    assert select_res["success"] is True

    # Forbidden SQL operation
    with pytest.raises(SQLValidationError):
        validate_and_sanitize_sql("DROP TABLE tickets", role="Super Admin")

    with pytest.raises(SQLValidationError):
        validate_and_sanitize_sql("DELETE FROM tickets", role="Super Admin")


def test_document_export_pdf_and_docx():
    pdf_bytes = generate_ticket_pdf("HD-1001")
    assert pdf_bytes and len(pdf_bytes) > 50

    docx_bytes = generate_ticket_docx("HD-1001")
    assert docx_bytes and len(docx_bytes) > 20


def test_admin_api_departments_and_users():
    # Create department
    res = client.post(
        "/api/admin/departments",
        json={"name": "DevOps Engineering", "queue_name": "DevOps Queue"},
    )
    assert res.status_code == 201

    # List departments
    list_res = client.get("/api/admin/departments")
    assert list_res.status_code == 200
    assert any(d["name"] == "DevOps Engineering" for d in list_res.json())

    # Add department user
    user_res = client.post(
        "/api/admin/departments/users",
        json={
            "department_name": "DevOps Engineering",
            "azure_object_id": "obj-12345-devops",
            "role": "Lead",
            "user_email": "devops@company.com",
        },
    )
    assert user_res.status_code == 201


def test_analytics_endpoint():
    # Analytics trends
    res = client.get("/api/analytics/trends")
    assert res.status_code == 200
    data = res.json()
    assert "total_tickets" in data
    assert "auto_resolution_rate_pct" in data


def test_genie_react_endpoint():
    res = client.post("/api/genie/react", json={"message": "Show count of tickets"})
    assert res.status_code == 200
    assert "reply" in res.json()
