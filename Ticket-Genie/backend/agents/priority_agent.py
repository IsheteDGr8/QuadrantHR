"""Priority levels and definitions for ticket classification."""

from __future__ import annotations

from typing import Any, Callable

from opentelemetry import trace

tracer = trace.get_tracer("ticketgenie.agents.priority_agent")

ALLOWED_PRIORITIES: list[str] = ["Low", "Medium", "High", "Critical"]

PRIORITY_RANK: dict[str, int] = {
    priority: rank for rank, priority in enumerate(ALLOWED_PRIORITIES)
}

PRIORITY_DESCRIPTIONS: dict[str, str] = {
    "Low": (
        "General or informational request. Little business impact. "
        "Work is not blocked. No important deadline."
    ),
    "Medium": (
        "Work is affected, but a workaround exists. Impact is limited. "
        "Should be handled soon."
    ),
    "High": (
        "Important work is blocked, there is serious individual impact, "
        "or an important deadline is approaching. Strongly affects the "
        "employee's ability to work."
    ),
    "Critical": (
        "Safety concern, security incident, serious legal/company risk, "
        "company-wide outage, many employees blocked, or severe "
        "organizational impact. The word 'urgent' by itself does NOT "
        "make a ticket Critical."
    ),
}


def is_valid_priority(priority: str) -> bool:
    """Return True if `priority` is one of the allowed priority levels."""
    return priority in ALLOWED_PRIORITIES


# Corporate triage signals. Roots intentionally cover common grammatical
# forms (for example: harassment/harassed/harassing and
# discrimination/discriminated/discriminatory).
CRITICAL_SIGNALS: tuple[str, ...] = (
    "active shooter",
    "bomb threat",
    "credible threat",
    "immediate danger",
    "imminent danger",
    "physical assault",
    "threatened to kill",
    "weapon at work",
    "workplace violence",
    "security breach",
    "data breach",
    "company-wide",
    "company wide",
    "company-wide outage",
    "company wide outage",
    "entire company cannot",
    "all employees cannot",
    "across the entire company",
)

HIGH_SIGNALS: tuple[str, ...] = (
    "harass",
    "discriminat",
    "retaliat",
    "sexual misconduct",
    "hostile work environment",
    "workplace bullying",
    "cannot work",
    "can't work",
    "unable to work",
    "locked out",
    "cannot log in",
    "can't log in",
    "important deadline",
    "approaching deadline",
    "cannot access",
    "can't access",
)

LOW_SIGNALS: tuple[str, ...] = (
    "still works",
    "no rush",
    "not urgent",
    "just a question",
    "just curious",
    "whenever you get a chance",
)


def classify_priority(text: str) -> str:
    """Assign a deterministic corporate triage priority from ticket text."""
    with tracer.start_as_current_span("priority_agent.classify_priority") as span:
        span.set_attribute("agent.name", "priority_agent")
        span.set_attribute("service.method", "classify_priority")
        result = _classify_priority_internal(text)
        span.set_attribute("agent.priority_assigned", result)
        return result


def _classify_priority_internal(text: str) -> str:
    normalized = text.lower()
    if any(signal in normalized for signal in CRITICAL_SIGNALS):
        return "Critical"
    if any(signal in normalized for signal in HIGH_SIGNALS):
        return "High"
    if any(signal in normalized for signal in LOW_SIGNALS):
        return "Low"
    return "Medium"


def enforce_minimum_priority(priority: str, minimum: str) -> str:
    """Return at least ``minimum`` without lowering a more severe result."""
    if not is_valid_priority(priority):
        return minimum
    return minimum if PRIORITY_RANK[priority] < PRIORITY_RANK[minimum] else priority


def classify_priority_with_ai(
    title: str, description: str, generate: Callable[..., dict[str, Any]]
) -> dict[str, Any]:
    with tracer.start_as_current_span(
        "priority_agent.classify_priority_with_ai"
    ) as span:
        span.set_attribute("agent.name", "priority_agent")
        span.set_attribute("service.method", "classify_priority_with_ai")
        res = _classify_priority_with_ai_internal(title, description, generate)
        span.set_attribute("agent.priority_assigned", str(res.get("priority", "")))
        return res


def _classify_priority_with_ai_internal(
    title: str, description: str, generate: Callable[..., dict[str, Any]]
) -> dict[str, Any]:
    definitions = "\n".join(
        f"- {name}: {description}"
        for name, description in PRIORITY_DESCRIPTIONS.items()
    )
    prompt = f"""You are TicketGenie's corporate helpdesk priority agent.
Assess employee safety, legal/compliance exposure, financial consequences,
people affected, work blockage, deadlines, business impact, and workarounds.
The word urgent alone does not determine severity.
Workplace harassment, discrimination, retaliation, or bullying is High by
default. It is Critical only when the ticket also reports an immediate or
credible threat of serious physical harm, violence, a weapon, or assault in
progress. Potential legal exposure by itself is not Critical.

Priority definitions:
{definitions}

Title: {title}
Description: {description}"""
    schema = {
        "type": "object",
        "properties": {
            "priority": {"type": "string", "enum": ALLOWED_PRIORITIES},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["priority", "confidence", "reason"],
        "additionalProperties": False,
    }
    return generate(prompt=prompt, schema=schema, name="ticket_priority")
