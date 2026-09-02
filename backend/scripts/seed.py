"""Seed a demo HR admin + sample employees for local development."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.employee import Employee, OrgUnit
from app.models.user import User, UserRole


def seed() -> None:
    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.email == "hr.admin@quadranthr.local")).scalar_one_or_none()
        if admin is None:
            admin = User(
                email="hr.admin@quadranthr.local",
                full_name="HR Admin",
                hashed_password=hash_password("changeme123"),
                role=UserRole.hr,
            )
            db.add(admin)
            db.flush()
            print("Created user hr.admin@quadranthr.local / changeme123")

        hr_unit = db.execute(select(OrgUnit).where(OrgUnit.name == "HR Operations")).scalar_one_or_none()
        if hr_unit is None:
            hr_unit = OrgUnit(name="HR Operations")
            eng = OrgUnit(name="Engineering")
            db.add_all([hr_unit, eng])
            db.flush()

        if db.execute(select(Employee).limit(1)).scalar_one_or_none() is None:
            people = [
                Employee(
                    work_email="hr.admin@quadranthr.local",
                    full_name="HR Admin",
                    job_title="Director of HR",
                    office="Seattle",
                    org_unit_id=hr_unit.id,
                    user_id=admin.id,
                ),
                Employee(
                    work_email="alex.nguyen@quadranthr.local",
                    full_name="Alex Nguyen",
                    job_title="Software Engineer",
                    office="Seattle",
                ),
                Employee(
                    work_email="samir.patel@quadranthr.local",
                    full_name="Samir Patel",
                    job_title="People Partner",
                    office="Remote",
                    org_unit_id=hr_unit.id,
                ),
            ]
            db.add_all(people)
            print(f"Seeded {len(people)} employees")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
