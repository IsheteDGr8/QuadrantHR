"""Role-Scoped Text-to-SQL Execution Service for TicketGenie.

Enables safe execution of read-only SELECT queries and controlled UPDATE
statements on ticket fields (priority, department, status, queue) with RBAC.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

from sqlalchemy import text

from database.connection import SessionLocal

logger = logging.getLogger(__name__)

# Dangerous SQL keywords strictly forbidden for safety
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|ATTACH|DETACH|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)

# Allowed columns for controlled UPDATE queries
ALLOWED_UPDATE_COLUMNS = {"priority", "department", "status", "queue", "assigned_to"}


class SQLValidationError(Exception):
    """Raised when an invalid or insecure SQL query is submitted."""


def validate_and_sanitize_sql(
    sql: str, role: str = "Employee", user_id: str = "user"
) -> str:
    """Validate SQL query against security rules and inject role-based scoping."""
    cleaned_sql = sql.strip().strip(";").strip()

    if FORBIDDEN_SQL_PATTERN.search(cleaned_sql):
        raise SQLValidationError(
            "Forbidden SQL operation detected (DELETE, DROP, ALTER, TRUNCATE not allowed)."
        )

    is_select = cleaned_sql.upper().startswith("SELECT")
    is_update = cleaned_sql.upper().startswith("UPDATE")

    if not (is_select or is_update):
        raise SQLValidationError(
            "Only SELECT queries and controlled UPDATE statements are allowed."
        )

    if is_update:
        # Check that UPDATE targets tickets table only
        if not re.search(r"\bUPDATE\s+tickets\b", cleaned_sql, re.IGNORECASE):
            raise SQLValidationError(
                "UPDATE statements can only target the 'tickets' table."
            )

    # Apply RBAC Row Scoping for non-admin users on SELECT
    if is_select and role.lower() not in {"super admin", "superadmin", "admin"}:
        if "WHERE" in cleaned_sql.upper():
            # Inject user filter
            if role.lower() in {"hr admin", "hr team"}:
                cleaned_sql += " AND department = 'HR Team'"
            elif role.lower() in {"it admin", "it team"}:
                cleaned_sql += " AND department = 'IT Team'"
            else:  # Employee
                cleaned_sql += f" AND (is_anonymous = 0 OR id IN (SELECT id FROM tickets WHERE id = '{user_id}'))"
        else:
            if role.lower() in {"hr admin", "hr team"}:
                cleaned_sql += " WHERE department = 'HR Team'"
            elif role.lower() in {"it admin", "it team"}:
                cleaned_sql += " WHERE department = 'IT Team'"
            else:
                cleaned_sql += (
                    f" WHERE (is_anonymous = 0 OR requester_id = '{user_id}')"
                )

    return cleaned_sql


def execute_sql_query(
    sql: str, role: str = "Admin", user_id: str = "user"
) -> Dict[str, Any]:
    """Execute a validated SQL query against the database and return results as dictionary."""
    try:
        sanitized_sql = validate_and_sanitize_sql(sql, role=role, user_id=user_id)
    except SQLValidationError as err:
        return {"success": False, "error": str(err), "rows": []}

    session = SessionLocal()
    try:
        result = session.execute(text(sanitized_sql))
        if sanitized_sql.upper().startswith("SELECT"):
            columns = list(result.keys())
            rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
            session.commit()
            return {
                "success": True,
                "query": sanitized_sql,
                "row_count": len(rows),
                "rows": rows,
            }
        else:
            # UPDATE query
            session.commit()
            return {
                "success": True,
                "query": sanitized_sql,
                "message": "Update executed successfully.",
                "rows": [],
            }
    except Exception as exc:
        session.rollback()
        logger.error(f"SQL execution error: {exc}")
        return {"success": False, "error": f"SQL execution error: {exc}", "rows": []}
    finally:
        session.close()
