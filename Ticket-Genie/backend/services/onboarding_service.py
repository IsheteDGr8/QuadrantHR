"""Onboarding orchestration built on TicketGenie's real ticket workflow."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models_db import OnboardingDB, TicketDB
from models.ticket import TicketCreate
from services.ticket_service import process_new_ticket

COMPLETE_STATUSES = {"complete", "completed", "closed", "resolved"}


def _calculate_health(record: OnboardingDB, tickets: list[TicketDB]) -> dict:
    total = len(tickets)
    completed = sum(
        1 for ticket in tickets if (ticket.status or "").lower() in COMPLETE_STATUSES
    )
    blocked = sum(1 for ticket in tickets if (ticket.status or "").lower() == "blocked")
    remaining = total - completed
    progress = round((completed / total) * 100) if total else 0

    try:
        days_until_start = (date.fromisoformat(record.start_date) - date.today()).days
    except (TypeError, ValueError):
        days_until_start = None

    if total and completed == total:
        health = "Complete"
        message = "All onboarding tickets are complete."
    elif blocked:
        health = "Blocked"
        message = (
            f"Onboarding is blocked by {blocked} ticket{'s' if blocked != 1 else ''}."
        )
    elif days_until_start is not None and days_until_start <= 3 and remaining:
        health = "At Risk"
        timing = "today" if days_until_start == 0 else f"in {days_until_start} days"
        if days_until_start < 0:
            timing = f"{abs(days_until_start)} days ago"
        message = f"Employee starts {timing} and {remaining} required tasks remain incomplete."
    else:
        health = "On Track"
        message = f"{remaining} onboarding tasks remain."

    return {
        "health": health,
        "health_message": message,
        "progress_percentage": progress,
        "completed_tickets": completed,
        "total_tickets": total,
        "remaining_tickets": remaining,
    }


def _serialize_case(record: OnboardingDB, tickets: list[TicketDB]) -> dict:
    result = record.to_dict()
    result.update(_calculate_health(record, tickets))
    result["tickets"] = [ticket.to_dict() for ticket in tickets]
    departments: dict[str, dict[str, int]] = {}
    for ticket in tickets:
        department = ticket.department or "Unassigned"
        summary = departments.setdefault(department, {"completed": 0, "total": 0})
        summary["total"] += 1
        if (ticket.status or "").lower() in COMPLETE_STATUSES:
            summary["completed"] += 1
    result["department_progress"] = departments
    return result


def list_onboarding_cases(db: Session) -> list[dict]:
    records = db.query(OnboardingDB).order_by(OnboardingDB.createdAt.desc()).all()
    return [
        _serialize_case(
            record,
            db.query(TicketDB).filter(TicketDB.onboarding_id == record.id).all(),
        )
        for record in records
    ]


def get_onboarding_case(onboarding_id: str, db: Session) -> dict | None:
    record = (
        db.query(OnboardingDB)
        .filter(func.lower(OnboardingDB.id) == onboarding_id.lower())
        .first()
    )
    if not record:
        return None
    tickets = (
        db.query(TicketDB)
        .filter(TicketDB.onboarding_id == record.id)
        .order_by(TicketDB.createdAt.asc())
        .all()
    )
    return _serialize_case(record, tickets)


def _create_linked_ticket(record: OnboardingDB, item, db: Session) -> dict:
    employee_context = "\n".join(
        [
            "Employee being onboarded:",
            f"- Name: {record.employee_name}",
            f"- Email: {record.employee_email}",
            f"- Job title: {record.role}",
            f"- Department: {record.department}",
            f"- Manager: {record.manager or 'Not provided'}",
            f"- Location: {record.location or 'Not provided'}",
            f"- Start date: {record.start_date}",
            f"- Onboarding case: {record.id}",
        ]
    )
    payload = TicketCreate(
        title=item.title,
        description=f"{item.description}\n\n{employee_context}",
        category=item.category,
        priority=item.priority,
        department=item.department,
        department_override=item.department,
        requester_id=record.employee_email,
    )
    created = process_new_ticket(payload, db=db)
    ticket = db.query(TicketDB).filter(TicketDB.id == created["id"]).first()
    ticket.onboarding_id = record.id
    ticket.due_date = item.due_date
    db.commit()
    db.refresh(ticket)
    return ticket.to_dict()


def start_onboarding_case(request, current_user: dict, db: Session) -> dict:
    onboarding_id = f"ONB-{uuid.uuid4().hex[:6].upper()}"
    record = OnboardingDB(
        id=onboarding_id,
        employee_name=request.employee_name,
        employee_email=request.employee_email,
        role=request.job_title,
        department=request.employee_department,
        manager=request.manager,
        location=request.location,
        visa_status=request.visa_status or "Not provided",
        start_date=request.start_date.isoformat(),
        status="In Progress",
        createdAt=datetime.now().isoformat(),
        created_by=current_user.get("oid") or current_user.get("email"),
    )
    db.add(record)
    db.commit()

    try:
        for item in request.tickets:
            _create_linked_ticket(record, item, db)
    except Exception:
        record.status = "Blocked"
        db.commit()
        raise

    return get_onboarding_case(onboarding_id, db)


def add_onboarding_ticket(record: OnboardingDB, item, db: Session) -> dict:
    return _create_linked_ticket(record, item, db)
