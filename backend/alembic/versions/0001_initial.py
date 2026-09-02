"""initial unified HR schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM(
        "employee", "manager", "hr", "admin", name="user_role", create_type=False
    )
    leave_type = postgresql.ENUM(
        "pto", "sick", "parental", "unpaid", "other", name="leave_type", create_type=False
    )
    leave_status = postgresql.ENUM(
        "pending", "approved", "rejected", "cancelled", name="leave_status", create_type=False
    )
    ticket_category = postgresql.ENUM(
        "it", "hr", "facilities", "other", "leave", name="ticket_category", create_type=False
    )
    ticket_status = postgresql.ENUM(
        "open", "in_progress", "waiting", "resolved", "closed", name="ticket_status", create_type=False
    )
    ticket_priority = postgresql.ENUM(
        "low", "medium", "high", "urgent", name="ticket_priority", create_type=False
    )

    user_role.create(op.get_bind(), checkfirst=True)
    leave_type.create(op.get_bind(), checkfirst=True)
    leave_status.create(op.get_bind(), checkfirst=True)
    ticket_category.create(op.get_bind(), checkfirst=True)
    ticket_status.create(op.get_bind(), checkfirst=True)
    ticket_priority.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "org_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org_units.id")),
    )
    op.create_index("ix_org_units_name", "org_units", ["name"], unique=True)

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True),
        sa.Column("work_email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("job_title", sa.String(255)),
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org_units.id")),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id")),
        sa.Column("office", sa.String(255)),
        sa.Column("bio", sa.Text()),
        sa.Column("profile_image_url", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_employees_work_email", "employees", ["work_email"], unique=True)
    op.create_index("ix_employees_full_name", "employees", ["full_name"])

    op.create_table(
        "leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("leave_type", leave_type, nullable=False),
        sa.Column("status", leave_status, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("approver_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("assignee_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("leave_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_requests.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tickets_requester_employee_id", "tickets", ["requester_employee_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("tickets")
    op.drop_table("leave_requests")
    op.drop_table("employees")
    op.drop_table("org_units")
    op.drop_table("users")
    for name in (
        "ticket_priority",
        "ticket_status",
        "ticket_category",
        "leave_status",
        "leave_type",
        "user_role",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
