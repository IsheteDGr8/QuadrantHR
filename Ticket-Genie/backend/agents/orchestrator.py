"""Main entry point for AI ticket classification.

Coordinates a single AI request (services/ai_service.py) with the
department/category/priority validators (agents/category_agent.py,
agents/priority_agent.py, agents/routing_agent.py) and returns one
validated TicketClassification.

classify_ticket() never raises. Any failure (missing config, Azure error,
malformed output, invalid taxonomy) is turned into a fallback
TicketClassification with needs_human_review=True so callers can always
trust the return value.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, Optional

from opentelemetry import trace
from pydantic import BaseModel, Field, model_validator

from agents.category_agent import classify_category_with_ai
from agents.priority_agent import (
    classify_priority,
    classify_priority_with_ai,
    enforce_minimum_priority,
)
from agents.routing_agent import reconcile_routing_with_ai, validate_routing
from services import ai_service

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("ticketgenie.agents.orchestrator")

Department = Literal[
    "HR Team",
    "Accounting Team",
    "Workplace Operations Team",
    "IT Team",
    "Upper Management",
]
Priority = Literal["Low", "Medium", "High", "Critical"]

FALLBACK_DEPARTMENT: Department = "Upper Management"
FALLBACK_CATEGORY = "Other Management Issue"
FALLBACK_PRIORITY: Priority = "Medium"

# Very short tickets rarely carry enough information to classify confidently.
_VAGUE_WORD_COUNT_THRESHOLD = 6

_SENSITIVE_KEYWORDS = (
    "harassment",
    "discrimination",
    "assault",
    "threat",
    "weapon",
    "lawsuit",
    "legal action",
    "safety concern",
    "security breach",
    "data breach",
    "self-harm",
)

_HR_EMPLOYEE_RELATIONS_ROOTS = (
    "harass",
    "discriminat",
    "retaliat",
    "sexual misconduct",
    "hostile work environment",
    "workplace bullying",
)


class TicketClassification(BaseModel):
    department: Department
    category: str = Field(min_length=1, max_length=100)
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=500)
    needs_human_review: bool

    @model_validator(mode="after")
    def _check_routing(self) -> "TicketClassification":
        errors = validate_routing(self.department, self.category, self.priority)
        if errors:
            raise ValueError("; ".join(errors))
        return self


def _is_vague(title: str, description: str) -> bool:
    word_count = len(f"{title} {description}".split())
    return word_count < _VAGUE_WORD_COUNT_THRESHOLD


def _is_sensitive(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(keyword in text for keyword in _SENSITIVE_KEYWORDS)


def _fallback_classification(
    reason: str, priority: Priority = FALLBACK_PRIORITY
) -> TicketClassification:
    return TicketClassification(
        department=FALLBACK_DEPARTMENT,
        category=FALLBACK_CATEGORY,
        priority=priority,
        confidence=0.0,
        reason=reason,
        needs_human_review=True,
    )


def classify_ticket(
    title: str,
    description: str,
    context: Optional[dict[str, Any]] = None,
) -> TicketClassification:
    """Classify a ticket into department, category, and priority.

    `context` is any optional structured ticket data already available in
    the backend (e.g. requester role, location) that may help classification.
    Never raises — on failure, returns a fallback result flagged for
    human review.
    """
    with tracer.start_as_current_span("orchestrator.classify_ticket") as span:
        span.set_attribute("agent.name", "orchestrator")
        span.set_attribute("service.method", "classify_ticket")
        res = _classify_ticket_internal(title, description, context)
        span.set_attribute("classification.department", res.department)
        span.set_attribute("classification.category", res.category)
        span.set_attribute("classification.priority", res.priority)
        return res


def _classify_ticket_internal(
    title: str,
    description: str,
    context: Optional[dict[str, Any]] = None,
) -> TicketClassification:
    try:
        if ai_service.use_mock_ai():
            raw_result = ai_service.get_ai_classification(title, description, context)
        else:
            with ThreadPoolExecutor(max_workers=2) as executor:
                category_future = executor.submit(
                    classify_category_with_ai,
                    title,
                    description,
                    ai_service.generate_structured,
                )
                priority_future = executor.submit(
                    classify_priority_with_ai,
                    title,
                    description,
                    ai_service.generate_structured,
                )
                category_result = category_future.result()
                priority_result = priority_future.result()
            raw_result = reconcile_routing_with_ai(
                title,
                description,
                category_result,
                priority_result,
                ai_service.generate_structured,
            )
    except ai_service.AIServiceError as exc:
        logger.warning("AI classification request failed: %s", exc)
        return _fallback_classification(f"AI classification unavailable: {exc}")
    except Exception:
        logger.exception("Unexpected error calling AI classification service.")
        return _fallback_classification(
            "AI classification unavailable due to an unexpected error."
        )

    if not isinstance(raw_result, dict):
        logger.error(
            "AI classification returned a non-dict result: %r", type(raw_result)
        )
        return _fallback_classification("AI classification returned an invalid result.")

    # Deterministic policy guardrails apply in both mock and real-AI modes.
    # This prevents model wording variance from downgrading or misrouting
    # sensitive employee-relations reports.
    text = f"{title} {description}".lower()
    if any(root in text for root in _HR_EMPLOYEE_RELATIONS_ROOTS):
        raw_result = dict(raw_result)
        raw_result["department"] = "HR Team"
        raw_result["category"] = "Employee Relationships"
        raw_result["priority"] = enforce_minimum_priority(
            str(raw_result.get("priority", "Medium")), "High"
        )
        raw_result["needs_human_review"] = True

        # Corporate policy keeps sensitive employee-relations reports at High
        # unless the text independently meets the explicit Critical threshold.
        if classify_priority(text) != "Critical":
            raw_result["priority"] = "High"

    policy_priority = classify_priority(text)
    if policy_priority == "Critical":
        raw_result = dict(raw_result)
        raw_result["priority"] = "Critical"
        raw_result["needs_human_review"] = True

    try:
        classification = TicketClassification(**raw_result)
    except Exception as exc:
        logger.error("AI classification output failed validation: %s", exc)
        return _fallback_classification(
            "AI classification output was invalid and could not be used."
        )

    needs_review = (
        classification.needs_human_review
        or classification.confidence < ai_service.get_confidence_threshold()
        or _is_vague(title, description)
        or _is_sensitive(title, description)
    )

    if needs_review and not classification.needs_human_review:
        classification = classification.model_copy(update={"needs_human_review": True})

    return classification
