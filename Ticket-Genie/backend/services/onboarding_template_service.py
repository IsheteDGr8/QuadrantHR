"""Deterministic onboarding ticket templates and role overlays."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

BASE_TEMPLATE = [
    {
        "title": "Provision company laptop",
        "description": "Prepare and configure the standard company laptop for the new employee.",
        "department": "IT Team",
        "category": "Laptop Requests",
        "priority": "High",
        "due_offset_days": -3,
    },
    {
        "title": "Create Microsoft 365 account",
        "description": "Create the employee Microsoft 365 identity and enable required core services.",
        "department": "IT Team",
        "category": "Identity and Access Management",
        "priority": "High",
        "due_offset_days": -3,
    },
    {
        "title": "Complete onboarding documentation",
        "description": "Collect and review all required new-hire onboarding documentation.",
        "department": "HR Team",
        "category": "Onboarding and Offboarding",
        "priority": "High",
        "due_offset_days": 0,
    },
    {
        "title": "Set up payroll profile",
        "description": "Create the employee payroll profile and verify required payment information.",
        "department": "Accounting Team",
        "category": "Other Accounting Request",
        "priority": "High",
        "due_offset_days": 0,
    },
    {
        "title": "Prepare building and workspace access",
        "description": "Arrange badge access and confirm the employee workspace is ready.",
        "department": "Workplace Operations Team",
        "category": "Badge Registration",
        "priority": "Medium",
        "due_offset_days": -1,
    },
]

ROLE_OVERLAYS = {
    "data": [
        (
            "Grant Power BI workspace access",
            "Grant access to the approved Power BI workspaces and analytics groups.",
        ),
        (
            "Provision SQL and data access",
            "Provision approved SQL and analytics data access for the employee role.",
        ),
    ],
    "analyst": [
        (
            "Grant Power BI workspace access",
            "Grant access to the approved Power BI workspaces and analytics groups.",
        ),
        (
            "Provision SQL and data access",
            "Provision approved SQL and analytics data access for the employee role.",
        ),
    ],
    "engineer": [
        (
            "Configure development environment",
            "Install and configure the approved engineering development toolchain.",
        ),
        (
            "Grant repository and Azure DevOps access",
            "Add the employee to approved repositories and Azure DevOps projects.",
        ),
    ],
    "developer": [
        (
            "Configure development environment",
            "Install and configure the approved engineering development toolchain.",
        ),
        (
            "Grant repository and Azure DevOps access",
            "Add the employee to approved repositories and Azure DevOps projects.",
        ),
    ],
    "hr": [
        (
            "Provision HR systems access",
            "Grant role-appropriate access to approved HR administration systems.",
        ),
        (
            "Assign HR compliance training",
            "Assign required HR privacy and compliance training modules.",
        ),
    ],
    "intern": [
        (
            "Configure limited system access",
            "Grant only the approved systems and groups required for the internship.",
        ),
        (
            "Schedule manager and team orientation",
            "Arrange manager, mentor, and team orientation sessions.",
        ),
    ],
    "manager": [
        (
            "Configure manager permissions",
            "Grant approved manager reporting and team administration permissions.",
        ),
    ],
}


def generate_onboarding_suggestions(job_title: str, start_date: str) -> list[dict]:
    """Return a stable baseline plus de-duplicated role-specific suggestions."""
    suggestions = deepcopy(BASE_TEMPLATE)
    normalized_role = (job_title or "").lower()
    existing_titles = {item["title"] for item in suggestions}

    for keyword, additions in ROLE_OVERLAYS.items():
        if keyword not in normalized_role:
            continue
        for title, description in additions:
            if title in existing_titles:
                continue
            suggestions.append(
                {
                    "title": title,
                    "description": description,
                    "department": "IT Team",
                    "category": "Identity and Access Management",
                    "priority": "Medium",
                    "due_offset_days": -1,
                }
            )
            existing_titles.add(title)

    try:
        employee_start = date.fromisoformat(start_date)
    except (TypeError, ValueError):
        employee_start = date.today()

    for index, suggestion in enumerate(suggestions, start=1):
        offset = suggestion.pop("due_offset_days", 0)
        suggestion["id"] = f"suggestion-{index}"
        suggestion["due_date"] = (employee_start + timedelta(days=offset)).isoformat()
        suggestion["selected"] = True

    return suggestions
