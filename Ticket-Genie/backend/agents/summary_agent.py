# backend/agents/summary_agent.py

from pydantic import BaseModel, Field

try:
    from services.ai_service import ai_service as default_ai_service
except ImportError:
    from backend.services.ai_service import ai_service as default_ai_service


class TicketSummary(BaseModel):
    summary: str
    requested_action: str
    key_facts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


SUMMARY_PROMPT = """
You are the summarization agent for TicketGenie.

Summarize the ticket for a support agent.

Return:
- summary: one concise sentence describing the issue
- requested_action: what the employee needs
- key_facts: important facts explicitly present in the ticket
- missing_information: information that may be needed to resolve the issue

Important rules:
- Do not invent facts.
- Keep the summary concise.
- Only list missing information that is genuinely relevant.
"""


def summarize_ticket(
    title: str,
    description: str,
    *,
    ai_service=default_ai_service,
) -> TicketSummary:
    user_content = f"""
Ticket title:
{title}

Ticket description:
{description}
"""

    return ai_service.generate(
        system_prompt=SUMMARY_PROMPT,
        user_content=user_content,
        response_model=TicketSummary,
    )
