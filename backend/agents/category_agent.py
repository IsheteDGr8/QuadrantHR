"""Allowed department/category taxonomy for ticket classification.

This is the single source of truth for which categories belong to which
department. The AI classifier is not allowed to invent labels outside of
this list.
"""

from __future__ import annotations

from typing import Any, Callable

ALLOWED_CATEGORIES: dict[str, list[str]] = {
    "HR Team": [
        "Employee Relationships",
        "Onboarding and Offboarding",
        "Benefits Inquiries",
        "Other HR Request",
    ],
    "Accounting Team": [
        "Company Card Management",
        "Reimbursement Requests",
        "Business Development Management",
        "Other Accounting Request",
    ],
    "Workplace Operations Team": [
        "Maintenance",
        "Badge Registration",
        "Office Equipment Issues",
        "Other Workplace Request",
    ],
    "IT Team": [
        "Laptop Requests",
        "Identity and Access Management",
        "Software Licensing",
        "Other IT Request",
    ],
    "Upper Management": [
        "High-Impact Company Conflict",
        "Executive Review",
        "Company-Wide Issue",
        "Other Management Issue",
    ],
}

ALLOWED_DEPARTMENTS: list[str] = list(ALLOWED_CATEGORIES.keys())


def is_valid_department(department: str) -> bool:
    """Return True if `department` is one of the allowed departments."""
    return department in ALLOWED_CATEGORIES


def is_valid_category(department: str, category: str) -> bool:
    """Return True if `category` is a valid category for `department`."""
    return (
        is_valid_department(department) and category in ALLOWED_CATEGORIES[department]
    )


def get_categories_for_department(department: str) -> list[str]:
    """Return the allowed categories for `department`, or [] if unknown."""
    return list(ALLOWED_CATEGORIES.get(department, []))


def classify_category_with_ai(
    title: str, description: str, generate: Callable[..., dict[str, Any]]
) -> dict[str, Any]:
    taxonomy = "\n".join(
        f"- {department}: {', '.join(categories)}"
        for department, categories in ALLOWED_CATEGORIES.items()
    )
    prompt = f"""You are TicketGenie's corporate helpdesk category agent.
Choose exactly one department and one category from this taxonomy:
{taxonomy}
Route employee relations matters such as harassment, discrimination,
retaliation, or bullying to HR Team / Employee Relationships.
Assess meaning and context rather than relying on keyword matching.

Title: {title}
Description: {description}"""
    schema = {
        "type": "object",
        "properties": {
            "department": {"type": "string", "enum": list(ALLOWED_CATEGORIES)},
            "category": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["department", "category", "confidence", "reason"],
        "additionalProperties": False,
    }
    return generate(prompt=prompt, schema=schema, name="ticket_category")
