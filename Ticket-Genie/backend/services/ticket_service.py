from typing import Optional

from opentelemetry import trace
from sqlalchemy.orm import Session

from agents.category_agent import is_valid_department
from agents.orchestrator import classify_ticket
from database.crud import create_ticket
from models.ticket import CompletedTicket, TicketCreate

_EXCLUDED_FIELDS = {"department", "category", "priority", "department_override"}

tracer = trace.get_tracer("ticketgenie.services.ticket")


def process_new_ticket(ticket: TicketCreate, db: Optional[Session] = None):
    with tracer.start_as_current_span("ticket_service.process_new_ticket") as span:
        span.set_attribute("service.name", "ticket_service")
        span.set_attribute("service.method", "process_new_ticket")
        span.set_attribute("ticket.title", ticket.title)

        # A valid explicit department override is authoritative. This covers
        # both deterministic workflow routing (for example Leave Management)
        # and a department the requester deliberately selected in the form.
        # In either case AI classification must not replace that choice.
        if ticket.department_override and is_valid_department(
            ticket.department_override
        ):
            span.set_attribute("ticket.assigned_department", ticket.department_override)
            span.set_attribute("ticket.assigned_category", ticket.category or "Other")
            span.set_attribute("ticket.assigned_priority", ticket.priority or "Medium")

            completed_ticket = CompletedTicket(
                **ticket.model_dump(exclude=_EXCLUDED_FIELDS),
                department=ticket.department_override,
                category=ticket.category or "Other",
                priority=ticket.priority or "Medium",
                confidence=1.0,
                reason=(
                    "User-selected department override; AI routing and "
                    "classification were skipped."
                ),
                needs_human_review=False,
            )

            try:
                import os

                from telemetry import record_llm_metrics

                prompt_tok = max(
                    20, len(f"{ticket.title} {ticket.description}".split()) * 3
                )
                record_llm_metrics(
                    prompt_tokens=prompt_tok,
                    completion_tokens=25,
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"),
                    agent_name="ticket_auto_triage",
                )
            except Exception:
                pass

            return create_ticket(completed_ticket, db=db)

        classification = classify_ticket(ticket.title, ticket.description)

        span.set_attribute("ticket.assigned_department", classification.department)
        span.set_attribute("ticket.assigned_category", classification.category)
        span.set_attribute("ticket.assigned_priority", classification.priority)

        completed_ticket = CompletedTicket(
            **ticket.model_dump(exclude=_EXCLUDED_FIELDS),
            department=classification.department,
            category=classification.category,
            priority=classification.priority,
            confidence=classification.confidence,
            reason=classification.reason,
            needs_human_review=classification.needs_human_review,
        )

        return create_ticket(completed_ticket, db=db)
