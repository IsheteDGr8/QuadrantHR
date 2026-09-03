"""
Authorization boundary for knowledge access.

KNOWN GAP: There is currently no real authentication/RBAC system in this
repo (backend/api/auth.py and backend/models/user.py both exist but are
empty placeholders, and the frontend only tracks a mock `role`
("Employee"/"Management") in localStorage with no per-user department).

Because of that, this service cannot yet resolve a verified department for
a given user - it can only work with whatever `role`/`department` the
caller explicitly supplies on the request. It deliberately defaults to the
least-privileged scope set (General only) rather than guessing or granting
broad access, so it never "fakes" security while the real auth/RBAC
integration is still pending.

Once real authentication exists, wire it in by resolving the caller's
verified role/department server-side (e.g. from a session/JWT) instead of
trusting request-supplied values, and pass those into get_allowed_scopes().
"""

from typing import List, NamedTuple, Optional

GENERAL_SCOPE = "General"
DEPARTMENT_SCOPES = {"HR", "IT", "Accounting", "WorkplaceOperations"}
MANAGEMENT_SCOPE = "UpperManagement"

# Roles authorized to reassign/reprioritize tickets via Genie.
TICKET_MUTATION_ROLES = {
    "admin",
    "ticketer",
    "support",
    "agent",
    "operations admin",
    "department admin",
    "upper executive lead",
    "super admin",
}

# Canonical role vocabulary for the portal employee-assignment flow.
EMPLOYEE_ASSIGNMENT_ROLES: tuple[str, ...] = (
    "Admin",
    "Ticketer",
    "Employee",
)


def is_admin(role: Optional[str], is_dev: bool = False) -> bool:
    """Check if the user has Admin privileges."""
    return "admin" in (role or "").lower() or is_dev


def is_ticketer(role: Optional[str], is_dev: bool = False) -> bool:
    """Check if user has Ticketer or Admin privileges."""
    normalized = (role or "").lower()
    return (
        "ticketer" in normalized
        or "admin" in normalized
        or "support" in normalized
        or "agent" in normalized
        or "super" in normalized
        or is_dev
    )


def is_employee(role: Optional[str]) -> bool:
    """Check if user has Employee role."""
    normalized = (role or "").lower()
    return "employee" in normalized or normalized == ""


def is_super_admin(role: Optional[str], is_dev: bool = False) -> bool:
    """Check if user has admin or is_dev privileges."""
    return "admin" in (role or "").lower() or "super" in (role or "").lower() or is_dev


def is_department_ticketer(role: Optional[str]) -> bool:
    """Whether `role` sees department-ticketer-tier navigation (Inbox,
    Analytics) in the live UI.
    """
    normalized = (role or "").lower()
    return (
        "admin" in normalized
        or "ticketer" in normalized
        or "support" in normalized
        or "operations" in normalized
        or "super" in normalized
    )


def is_admin_role(role: Optional[str]) -> bool:
    """Whether `role` sees admin-tier navigation (Settings) in the live UI."""
    normalized = (role or "").lower()
    return "admin" in normalized or "super" in normalized


def is_ticket_mutation_authorized(role: Optional[str]) -> bool:
    """Whether `role` may reassign a ticket's department or priority.

    Deterministic, backend-only check against TICKET_MUTATION_ROLES.
    """
    return (role or "").strip().lower() in TICKET_MUTATION_ROLES


ASSIGNMENT_TO_TICKET_DEPARTMENT = {
    "IT Team": "IT Team",
    "HR Team": "HR Team",
    "Accounting Team": "Accounting Team",
    "Workplace Operations Team": "Workplace Operations Team",
}


class VisibilityScope(NamedTuple):
    """
    Result of resolve_visibility_scope(): either unrestricted
    (Super Admin / is_dev) or scoped to exactly one canonical ticket department.
    """

    unrestricted: bool
    department: Optional[str]


def resolve_visibility_scope(current_user: Optional[dict]) -> Optional[VisibilityScope]:
    """
    Determine which tickets an authenticated user may see/manage through
    Genie's management actions (reassign_ticket / change_priority).

    - If user has a department mapped in ASSIGNMENT_TO_TICKET_DEPARTMENT,
      visibility is scoped to that department.
    - If user has super admin or is_dev privilege, visibility is unrestricted.
    - Otherwise returns None (fail-closed).
    """
    assignment_department = (current_user or {}).get("department") or ""
    ticket_department = ASSIGNMENT_TO_TICKET_DEPARTMENT.get(assignment_department)
    if ticket_department:
        return VisibilityScope(unrestricted=False, department=ticket_department)

    role = (current_user or {}).get("role") or ""
    is_dev = bool((current_user or {}).get("is_dev", False))
    if "super" in role.lower() or is_dev:
        return VisibilityScope(unrestricted=True, department=None)

    return None


def get_allowed_scopes(
    role: Optional[str], department: Optional[str] = None
) -> List[str]:
    """
    Determine which knowledge scopes a user may see.

    Every user gets General (company-wide, non-restricted) knowledge.
    A department-specific scope is granted only when a matching department
    is explicitly supplied. Management additionally gets the
    UpperManagement scope. Nothing else is granted by default.
    """

    scopes = {GENERAL_SCOPE}

    normalized_department = (department or "").strip()
    if normalized_department in DEPARTMENT_SCOPES:
        scopes.add(normalized_department)

    if (role or "").strip().lower() == "management":
        scopes.add(MANAGEMENT_SCOPE)

    return sorted(scopes)
