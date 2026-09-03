# backend/agents/response_agent.py

from pydantic import BaseModel, Field

from services.ai_service import ai_service as default_ai_service


class EmployeeResponse(BaseModel):
    message: str
    suggested_actions: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Two to four concise action bullets, each no more than 12 words.",
    )
    safety_notice_required: bool = False


RESPONSE_PROMPT = """
You are the suggested-response agent for TicketGenie.

Draft a concise professional response for a human support agent to review.

Important rules:
- The draft is a suggestion for an HR/support professional, not a final decision.
- Acknowledge the employee's concern with appropriate empathy without admitting
  wrongdoing, assigning blame, or making a legal conclusion.
- Do not claim an action was completed unless explicitly stated.
- Do not claim something was escalated, approved, resolved, assigned,
  investigated, or fixed unless that is known.
- Do not invent company policy.
- Do not promise a resolution time.
- For sensitive HR, security, or executive matters, keep the response cautious.
- Never repeat private, medical, or sensitive details unless needed to answer.
- Use the conversation history to avoid asking for information already provided.
- Do not include a greeting with a guessed employee name.
- Ask for missing information only when it is actually needed.
- suggested_actions must contain 2-4 short, actionable bullet fragments.
- Keep each suggested action to 12 words or fewer.
- Start each action with a direct verb (for example: Confirm, Check, Escalate, or Reply).
- Do not include paragraphs, explanations, headings, numbering, or repeated context in suggested_actions.
- safety_notice_required should be true for sensitive/high-risk cases.

Return:
- message
- suggested_actions
- safety_notice_required
"""


def draft_response(
    title: str,
    description: str,
    *,
    category: str,
    priority: str,
    queue: str,
    conversation_history: str = "No prior public conversation.",
    ai_service=default_ai_service,
) -> EmployeeResponse:
    user_content = f"""
Ticket title:
{title}

Ticket description:
{description}

Category:
{category}

Priority:
{priority}

Assigned queue:
{queue}

Public conversation history (oldest to newest):
{conversation_history[:12000]}
"""

    return ai_service.generate(
        system_prompt=RESPONSE_PROMPT,
        user_content=user_content,
        response_model=EmployeeResponse,
    )
