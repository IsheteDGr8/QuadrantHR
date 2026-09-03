"""Routing validation helpers.

Confirms a (department, category, priority) triple is internally consistent
before a classification result is trusted. This module never touches the
database — it is pure validation logic.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.category_agent import is_valid_category, is_valid_department
from agents.priority_agent import is_valid_priority


def validate_routing(department: str, category: str, priority: str) -> list[str]:
    """Return a list of human-readable validation errors.

    An empty list means the (department, category, priority) triple is
    valid and consistent.
    """
    errors: list[str] = []

    if not is_valid_department(department):
        errors.append(f"'{department}' is not an allowed department.")
    elif not is_valid_category(department, category):
        errors.append(
            f"'{category}' is not a valid category for department '{department}'."
        )

    if not is_valid_priority(priority):
        errors.append(f"'{priority}' is not a valid priority.")

    return errors


def is_valid_routing(department: str, category: str, priority: str) -> bool:
    """Return True if the (department, category, priority) triple is valid."""
    return not validate_routing(department, category, priority)


def reconcile_routing_with_ai(
    title: str,
    description: str,
    category_result: dict[str, Any],
    priority_result: dict[str, Any],
    generate: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    from agents.category_agent import ALLOWED_CATEGORIES
    from agents.priority_agent import ALLOWED_PRIORITIES

    prompt = f"""You are TicketGenie's routing agent. Reconcile the two
specialist assessments below. Return a valid department/category pairing,
final priority, confidence, concise reason, and whether a human must review.
Do not invent taxonomy values.
Harassment is High unless there is a separate explicit indication of imminent
serious physical danger or violence; potential legal risk alone is not Critical.

Title: {title}
Description: {description}
Category agent: {json.dumps(category_result)}
Priority agent: {json.dumps(priority_result)}
Taxonomy: {json.dumps(ALLOWED_CATEGORIES)}"""
    schema = {
        "type": "object",
        "properties": {
            "department": {"type": "string", "enum": list(ALLOWED_CATEGORIES)},
            "category": {"type": "string"},
            "priority": {"type": "string", "enum": ALLOWED_PRIORITIES},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
            "needs_human_review": {"type": "boolean"},
        },
        "required": [
            "department",
            "category",
            "priority",
            "confidence",
            "reason",
            "needs_human_review",
        ],
        "additionalProperties": False,
    }
    return generate(prompt=prompt, schema=schema, name="ticket_routing")
