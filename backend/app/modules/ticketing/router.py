from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.schemas import LeaveCreate, LeaveOut, TicketCreate, TicketOut
from app.models.ticket import Ticket, TicketCategory, TicketStatus
from app.models.user import User

router = APIRouter(prefix="/ticketing", tags=["ticketing"])


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[Ticket]:
    return list(db.execute(select(Ticket).order_by(Ticket.created_at.desc()).limit(100)).scalars())


@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    if db.get(Employee, body.requester_employee_id) is None:
        raise HTTPException(status_code=400, detail="Unknown requester")
    ticket = Ticket(
        requester_employee_id=body.requester_employee_id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/leaves", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
def create_leave(
    body: LeaveCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> LeaveOut:
    """Leave request always spawns a linked HR ticket (plan.md Week 2 pattern, scaffolded now)."""
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="end_date before start_date")
    if db.get(Employee, body.employee_id) is None:
        raise HTTPException(status_code=400, detail="Unknown employee")

    leave = LeaveRequest(
        employee_id=body.employee_id,
        leave_type=body.leave_type,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
        status=LeaveStatus.pending,
    )
    db.add(leave)
    db.flush()

    ticket = Ticket(
        requester_employee_id=body.employee_id,
        title=f"Leave request: {body.leave_type.value} ({body.start_date} → {body.end_date})",
        description=body.reason or "Leave request submitted via portal",
        category=TicketCategory.leave,
        leave_request_id=leave.id,
        status=TicketStatus.open,
    )
    db.add(ticket)
    db.commit()
    db.refresh(leave)
    db.refresh(ticket)

    return LeaveOut(
        id=leave.id,
        employee_id=leave.employee_id,
        leave_type=leave.leave_type,
        status=leave.status,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        linked_ticket_id=ticket.id,
    )


@router.get("/leaves", response_model=list[LeaveOut])
def list_leaves(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[LeaveOut]:
    leaves = list(db.execute(select(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(100)).scalars())
    out: list[LeaveOut] = []
    for leave in leaves:
        ticket = db.execute(
            select(Ticket).where(Ticket.leave_request_id == leave.id)
        ).scalar_one_or_none()
        out.append(
            LeaveOut(
                id=leave.id,
                employee_id=leave.employee_id,
                leave_type=leave.leave_type,
                status=leave.status,
                start_date=leave.start_date,
                end_date=leave.end_date,
                reason=leave.reason,
                linked_ticket_id=ticket.id if ticket else None,
            )
        )
    return out
