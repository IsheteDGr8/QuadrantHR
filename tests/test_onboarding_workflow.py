"""Onboarding templates, authorization, real-ticket linking, and progress."""

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.onboarding import require_onboarding_admin
from database.models_db import Base, TicketDB
from services.onboarding_service import get_onboarding_case, start_onboarding_case
from services.onboarding_template_service import generate_onboarding_suggestions

ROOT = Path(__file__).resolve().parents[1]
ONBOARDING_VIEW = (
    ROOT / "frontend" / "src" / "views" / "OnboardingView.svelte"
).read_text(encoding="utf-8")
FRONTEND_API = (ROOT / "frontend" / "src" / "lib" / "api.js").read_text(
    encoding="utf-8"
)


@pytest.fixture()
def onboarding_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_data_analyst_template_adds_role_specific_tickets():
    suggestions = generate_onboarding_suggestions("Senior Data Analyst", "2026-09-08")
    titles = {item["title"] for item in suggestions}

    assert "Provision company laptop" in titles
    assert "Grant Power BI workspace access" in titles
    assert "Provision SQL and data access" in titles
    assert all(item["selected"] is True for item in suggestions)


def test_onboarding_management_is_admin_only():
    assert require_onboarding_admin({"role": "Admin"})["role"] == "Admin"

    with pytest.raises(HTTPException) as exc:
        require_onboarding_admin({"role": "Employee"})

    assert exc.value.status_code == 403


def test_start_onboarding_links_real_tickets_and_calculates_progress(
    onboarding_db, monkeypatch
):
    counter = iter(["HD-9001", "HD-9002"])

    def fake_process(ticket, db):
        ticket_id = next(counter)
        now = date.today().isoformat()
        db_ticket = TicketDB(
            id=ticket_id,
            title=ticket.title,
            category=ticket.category,
            priority=ticket.priority,
            status="Open",
            department=ticket.department_override,
            description=ticket.description,
            date=now,
            createdAt=now,
            requester_id=ticket.requester_id,
        )
        db.add(db_ticket)
        db.commit()
        return db_ticket.to_dict()

    monkeypatch.setattr("services.onboarding_service.process_new_ticket", fake_process)
    start_date = (date.today() + timedelta(days=2)).isoformat()
    items = [
        SimpleNamespace(
            title="Provision laptop",
            description="Prepare the standard company laptop.",
            department="IT Team",
            category="Laptop Requests",
            priority="High",
            due_date=start_date,
        ),
        SimpleNamespace(
            title="Complete HR documentation",
            description="Complete all required onboarding forms.",
            department="HR Team",
            category="Onboarding and Offboarding",
            priority="Medium",
            due_date=start_date,
        ),
    ]
    request = SimpleNamespace(
        employee_name="Priya Shah",
        employee_email="priya@example.com",
        job_title="Data Analyst",
        employee_department="Analytics",
        manager="Alex Manager",
        location="Remote",
        visa_status=None,
        start_date=date.fromisoformat(start_date),
        tickets=items,
    )

    created = start_onboarding_case(
        request,
        {"oid": "super-admin-oid", "role": "Super Admin"},
        onboarding_db,
    )

    assert created["id"].startswith("ONB-")
    assert created["total_tickets"] == 2
    assert created["health"] == "At Risk"
    assert {ticket["id"] for ticket in created["tickets"]} == {
        "HD-9001",
        "HD-9002",
    }
    assert all(
        ticket["onboarding_id"] == created["id"] for ticket in created["tickets"]
    )

    first_ticket = onboarding_db.query(TicketDB).filter(TicketDB.id == "HD-9001").one()
    first_ticket.status = "Resolved"
    onboarding_db.commit()
    refreshed = get_onboarding_case(created["id"], onboarding_db)
    assert refreshed["progress_percentage"] == 50
    assert refreshed["department_progress"]["IT Team"]["completed"] == 1


def test_existing_super_admin_view_uses_review_before_creation_workflow():
    assert "Create New Onboarding" in ONBOARDING_VIEW
    assert "Generate Onboarding Plan" in ONBOARDING_VIEW
    assert "Nothing becomes a ticket until" in ONBOARDING_VIEW
    assert "Add Custom Ticket" in ONBOARDING_VIEW
    assert "Start Onboarding" in ONBOARDING_VIEW
    assert "apiStartOnboarding" in FRONTEND_API
    assert "/suggest" in FRONTEND_API
    assert "/tickets" in FRONTEND_API
