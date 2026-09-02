from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.employee import Employee
from app.models.schemas import EmployeeCreate, EmployeeOut
from app.models.user import User

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(None, description="Name, email, or title search"),
    limit: int = Query(25, ge=1, le=100),
) -> list[Employee]:
    stmt = select(Employee).order_by(Employee.full_name).limit(limit)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(like),
                Employee.work_email.ilike(like),
                Employee.job_title.ilike(like),
            )
        )
    return list(db.execute(stmt).scalars().all())


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Employee:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: EmployeeCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Employee:
    exists = db.execute(
        select(Employee).where(Employee.work_email == body.work_email.lower())
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    emp = Employee(
        work_email=body.work_email.lower(),
        full_name=body.full_name,
        job_title=body.job_title,
        office=body.office,
        org_unit_id=body.org_unit_id,
        manager_id=body.manager_id,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp
