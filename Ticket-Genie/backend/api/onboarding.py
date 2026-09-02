"""Secure Super Admin onboarding workflow backed by real TicketGenie tickets."""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from agents.category_agent import is_valid_category
from database.connection import get_db
from database.models_db import OnboardingDB
from models.ticket import TICKET_DEPARTMENTS, TICKET_PRIORITIES
from services.jwt_verifier import verify_azure_user
from services.onboarding_service import (
    add_onboarding_ticket,
    get_onboarding_case,
    list_onboarding_cases,
    start_onboarding_case,
)
from services.onboarding_template_service import generate_onboarding_suggestions
from services.role_service import is_admin

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def require_onboarding_admin(
    current_user: dict = Depends(verify_azure_user),
) -> dict:
    if not is_admin(current_user.get("role"), current_user.get("is_dev", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Admin can manage onboarding.",
        )
    return current_user


class OnboardingSuggestionRequest(BaseModel):
    job_title: str = Field(min_length=2, max_length=100)
    start_date: date


class OnboardingTicketPlanItem(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    department: Literal[TICKET_DEPARTMENTS]
    category: str = Field(min_length=2, max_length=100)
    priority: Literal[TICKET_PRIORITIES] = "Medium"
    due_date: Optional[str] = None

    @model_validator(mode="after")
    def category_belongs_to_department(self):
        if not is_valid_category(self.department, self.category):
            raise ValueError(
                f"Category '{self.category}' is not valid for {self.department}."
            )
        return self


class OnboardingStartRequest(BaseModel):
    employee_name: str = Field(min_length=2, max_length=150)
    employee_email: str = Field(
        min_length=3,
        max_length=150,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    job_title: str = Field(min_length=2, max_length=100)
    employee_department: str = Field(min_length=2, max_length=100)
    manager: Optional[str] = Field(default=None, max_length=150)
    location: Optional[str] = Field(default=None, max_length=150)
    visa_status: Optional[str] = Field(default=None, max_length=100)
    start_date: date
    tickets: list[OnboardingTicketPlanItem] = Field(min_length=1, max_length=30)


class OnboardingUpdateRequest(BaseModel):
    status: Literal["In Progress", "Blocked", "Cancelled"]


@router.get("")
def list_cases(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_onboarding_admin),
):
    return list_onboarding_cases(db)


@router.post("/suggest")
def suggest_onboarding_plan(
    req: OnboardingSuggestionRequest,
    current_user: dict = Depends(require_onboarding_admin),
):
    return {
        "source": "deterministic_role_template",
        "tickets": generate_onboarding_suggestions(
            job_title=req.job_title,
            start_date=req.start_date.isoformat(),
        ),
    }


@router.post("/start", status_code=201)
def start_onboarding(
    req: OnboardingStartRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_onboarding_admin),
):
    return start_onboarding_case(req, current_user, db)


@router.get("/{onboarding_id}")
def get_case(
    onboarding_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_onboarding_admin),
):
    record = get_onboarding_case(onboarding_id, db)
    if not record:
        raise HTTPException(status_code=404, detail="Onboarding case not found")
    return record


@router.post("/{onboarding_id}/tickets", status_code=201)
def add_ticket_to_case(
    onboarding_id: str,
    req: OnboardingTicketPlanItem,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_onboarding_admin),
):
    record = db.query(OnboardingDB).filter(OnboardingDB.id == onboarding_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Onboarding case not found")
    return add_onboarding_ticket(record, req, db)


@router.patch("/{onboarding_id}")
def update_case(
    onboarding_id: str,
    req: OnboardingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_onboarding_admin),
):
    record = db.query(OnboardingDB).filter(OnboardingDB.id == onboarding_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Onboarding case not found")
    record.status = req.status
    db.commit()
    return get_onboarding_case(onboarding_id, db)
