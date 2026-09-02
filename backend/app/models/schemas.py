from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.leave import LeaveStatus, LeaveType
from app.models.ticket import TicketCategory, TicketPriority, TicketStatus
from app.models.user import UserRole


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: UserRole = UserRole.employee


class EmployeeOut(BaseModel):
    id: UUID
    work_email: str
    full_name: str
    job_title: str | None
    office: str | None
    org_unit_id: UUID | None
    manager_id: UUID | None

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    work_email: EmailStr
    full_name: str
    job_title: str | None = None
    office: str | None = None
    org_unit_id: UUID | None = None
    manager_id: UUID | None = None


class TicketCreate(BaseModel):
    title: str
    description: str
    category: TicketCategory = TicketCategory.other
    priority: TicketPriority = TicketPriority.medium
    requester_employee_id: UUID


class TicketOut(BaseModel):
    id: UUID
    title: str
    description: str
    category: TicketCategory
    status: TicketStatus
    priority: TicketPriority
    requester_employee_id: UUID
    leave_request_id: UUID | None

    model_config = {"from_attributes": True}


class LeaveCreate(BaseModel):
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveOut(BaseModel):
    id: UUID
    employee_id: UUID
    leave_type: LeaveType
    status: LeaveStatus
    start_date: date
    end_date: date
    reason: str | None
    linked_ticket_id: UUID | None = None

    model_config = {"from_attributes": True}


class CopilotAskIn(BaseModel):
    message: str
    employee_id: UUID | None = None


class CopilotAskOut(BaseModel):
    reply: str
    provider: str
