"""Database Seeding Module for TicketGenie.

Loads and seeds initial records cleanly using SQLAlchemy ORM to guarantee
cross-database dialect compatibility (SQLite, Azure SQL / MSSQL, PostgreSQL)
and executes optional external SQL seed scripts idempotently.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import SessionLocal, engine
from database.models_db import DepartmentDB, DepartmentUserDB, TicketDB, UserProfileDB

logger = logging.getLogger("ticketgenie.database.seed")

SEED_SQL_FILE = (
    Path(__file__).resolve().parent.parent.parent / "database" / "seed_data.sql"
)

# Canonical Default Seed Records
DEFAULT_DEPARTMENTS = [
    {
        "id": "dept-it-001",
        "name": "IT Team",
        "queue_name": "IT - Service Desk",
        "description": "IT Support and hardware/software service desk queue",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "dept-hr-002",
        "name": "HR Team",
        "queue_name": "HR - Employee Relations",
        "description": "Human resources, benefits, and employee relations queue",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "dept-acc-003",
        "name": "Accounting Team",
        "queue_name": "Accounting - Payroll",
        "description": "Finance, accounts payable, and payroll queue",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "dept-exec-004",
        "name": "Upper Executive Management",
        "queue_name": "Upper Management - Leave Approval",
        "description": "Executive leadership and leave approval escalations",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "dept-wop-005",
        "name": "Workplace Operations Team",
        "queue_name": "Workplace Operations - Facilities",
        "description": "Workplace operations, facilities, and logistics queue",
        "createdAt": "2026-08-16T12:00:00",
    },
]

DEFAULT_DEPARTMENT_USERS = [
    {
        "id": "uobj-admin-dc3b56e9",
        "department_name": "Upper Executive Management",
        "azure_object_id": "dc3b56e9-9280-40dc-8d73-98bfd81fdd6a",
        "role": "Admin",
        "user_email": "Admin1@vigneshquadrantoutlook.onmicrosoft.com",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "uobj-ticketer-it-01",
        "department_name": "IT Team",
        "azure_object_id": "it-ticketer-oid-1001",
        "role": "Ticketer",
        "user_email": "it.agent@ticketgenie.test",
        "createdAt": "2026-08-16T12:00:00",
    },
    {
        "id": "uobj-employee-01",
        "department_name": "IT Team",
        "azure_object_id": "employee-demo-oid-2001",
        "role": "Employee",
        "user_email": "employee.demo@ticketgenie.test",
        "createdAt": "2026-08-16T12:00:00",
    },
]

DEFAULT_USER_PROFILES = [
    {
        "id": "usr-admin-dc3b56e9",
        "name": "Greg Davis",
        "email": "Admin1@vigneshquadrantoutlook.onmicrosoft.com",
        "role": "Admin",
        "department": "Upper Executive Management",
        "phone": "+1 (555) 019-9999",
        "avatar": "GD",
        "azure_object_id": "dc3b56e9-9280-40dc-8d73-98bfd81fdd6a",
    },
    {
        "id": "usr-ticketer-it-01",
        "name": "Ethan Brooks",
        "email": "it.agent@ticketgenie.test",
        "role": "Ticketer",
        "department": "IT Team",
        "phone": "+1 (555) 019-2222",
        "avatar": "EB",
        "azure_object_id": "it-ticketer-oid-1001",
    },
    {
        "id": "usr-employee-01",
        "name": "Maya Patel",
        "email": "employee.demo@ticketgenie.test",
        "role": "Employee",
        "department": "IT Team",
        "phone": "+1 (555) 019-1111",
        "avatar": "MP",
        "azure_object_id": "employee-demo-oid-2001",
    },
]

DEFAULT_TICKETS = [
    {
        "id": "HD-2001",
        "title": "VPN Connection Issue for Admin User",
        "department": "IT Team",
        "queue": "IT - Service Desk",
        "category": "IT Support",
        "priority": "High",
        "status": "Open",
        "description": "Unable to connect to internal VPN network from remote office.",
        "date": "2026-08-16",
        "createdAt": "2026-08-16T23:06:00",
        "is_anonymous": False,
        "auto_resolved": False,
        "is_synthetic": False,
        "requester_id": "usr-admin-dc3b56e9",
        "classification_status": "Classified",
        "classification_confidence": "0.95",
        "classification_reason": "IT Support request regarding VPN",
        "needs_human_review": False,
        "model_deployment": "gpt-5.2",
    },
    {
        "id": "HD-2002",
        "title": "Payroll Discrepancy Inquiry",
        "department": "HR Team",
        "queue": "HR - Employee Relations",
        "category": "Payroll",
        "priority": "Medium",
        "status": "Open",
        "description": "Overtime pay was not reflected on recent paystub.",
        "date": "2026-08-16",
        "createdAt": "2026-08-16T23:06:30",
        "is_anonymous": False,
        "auto_resolved": False,
        "is_synthetic": False,
        "requester_id": "other-employee-7890",
        "classification_status": "Classified",
        "classification_confidence": "0.90",
        "classification_reason": "HR Payroll request",
        "needs_human_review": False,
        "model_deployment": "gpt-5.2",
    },
]


def seed_initial_data(db: Optional[Session] = None) -> None:
    """Seed initial database records idempotently using SQLAlchemy ORM.

    Guarantees cross-dialect compatibility across SQLite, Azure SQL (MSSQL),
    and PostgreSQL without failing on syntax or constraint differences.
    """
    session = db or SessionLocal()
    should_close = db is None

    try:
        # 1. Seed Core Departments
        for dept_data in DEFAULT_DEPARTMENTS:
            dept_obj = DepartmentDB(**dept_data)
            session.merge(dept_obj)

        # 2. Seed Department Users (RBAC)
        for du_data in DEFAULT_DEPARTMENT_USERS:
            du_obj = DepartmentUserDB(**du_data)
            session.merge(du_obj)

        # 3. Seed User Profiles
        for prof_data in DEFAULT_USER_PROFILES:
            prof_obj = UserProfileDB(**prof_data)
            session.merge(prof_obj)

        # 4. Seed Initial Tickets
        for ticket_data in DEFAULT_TICKETS:
            ticket_obj = TicketDB(**ticket_data)
            session.merge(ticket_obj)

        session.commit()
        print(
            "✅ Executed database seed: Core departments, RBAC users, profiles, and tickets populated."
        )

        # 5. Optionally execute external SQL file if present and readable
        if SEED_SQL_FILE.exists():
            _execute_sql_file(SEED_SQL_FILE)

    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database records: {e}")
        print(f"⚠️ Error executing database seed: {e}")
    finally:
        if should_close:
            session.close()


def _execute_sql_file(file_path: Path) -> None:
    """Execute statements from SQL file with dialect awareness and error safety."""
    try:
        sql_content = file_path.read_text(encoding="utf-8")
        raw_blocks = sql_content.split(";")
        with engine.connect() as conn:
            for block in raw_blocks:
                lines = [
                    line
                    for line in block.splitlines()
                    if not line.strip().startswith("--")
                ]
                stmt = "\n".join(lines).strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception as stmt_err:
                        # Log and continue so non-portable optional statements don't crash startup
                        logger.debug(
                            f"Non-critical SQL seed statement note: {stmt_err}"
                        )
            conn.commit()
    except Exception as e:
        logger.debug(f"Note executing optional SQL seed file {file_path.name}: {e}")
