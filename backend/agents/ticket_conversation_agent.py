# backend/agents/ticket_conversation_agent.py

from typing import List

from pydantic import BaseModel

from services.ai_service import ai_service as default_ai_service

CONVERSATION_SUMMARY_PROMPT = """
You are summarizing a single support ticket's conversation for
TicketGenie's chat assistant, Genie, so it can give the requester a
quick status update.

Use ONLY the ticket title/description and comments supplied below -
never outside knowledge, and never anything not explicitly present in
that text. This content has already been retrieved from the ticket and
permission-filtered for this user (any comment the caller isn't
authorized to see was removed before you ever saw this prompt) - you
never decide what they're authorized to see, and everything you receive
here is safe to summarize.

Rules:
- Summarize only what is present. Never invent or infer an approval,
  denial, decision, assignee, date, or next step that isn't explicitly
  stated in the text below - if something isn't said, it isn't in the
  summary.
- In roughly 1-3 sentences, capture: what the requester originally
  needed, any meaningful staff response or decision, and where things
  currently stand - including a genuinely unresolved next step, but only
  if one is actually stated in the text.
- Synthesize, don't transcribe - do not restate every comment
  individually or quote them verbatim.
- If the supplied text has no real conversation to summarize (e.g. the
  comments are all trivial/administrative - a bare "ok", a system log
  line like ticket assignment, or otherwise carry no substantive
  update), set has_meaningful_content to false and leave summary empty -
  never pad the summary with content that "should" exist just to have
  something to say.
"""


class ConversationSummary(BaseModel):
    has_meaningful_content: bool
    summary: str = ""


def summarize_conversation(
    title: str,
    description: str,
    comment_lines: List[str],
    *,
    ai_service=default_ai_service,
) -> ConversationSummary:
    """
    Deterministic callers (services.chatbot_service) are responsible for
    only ever passing already-authorized comment text in `comment_lines`
    - this function trusts its input is pre-filtered and never fetches or
    filters anything itself.
    """
    conversation_block = "\n".join(comment_lines) if comment_lines else "(none)"
    user_content = f"""
TICKET TITLE:
{title}

ORIGINAL REQUEST:
{description}

VISIBLE COMMENTS (oldest to newest):
{conversation_block}
"""

    return ai_service.generate(
        system_prompt=CONVERSATION_SUMMARY_PROMPT,
        user_content=user_content,
        response_model=ConversationSummary,
    )
