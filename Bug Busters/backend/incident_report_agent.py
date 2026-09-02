import json

from openai import BadRequestError

from openai_service import OpenAIService


class IncidentReportAgentError(Exception):
    """Raised when the incident report assistant's LLM calls fail —
    callers should let the user retry rather than silently produce
    nothing."""

    def __init__(self, message: str, *, content_filtered: bool = False):
        super().__init__(message)
        # True when Azure's content safety filter blocked the request
        # itself, rather than the call actually failing - callers should
        # tell the user to rephrase, not report an outage.
        self.content_filtered = content_filtered


def _is_content_filtered(exc: BadRequestError) -> bool:
    return exc.code == "content_filter"


def _call_llm(service: OpenAIService, prompt: str) -> str:
    try:
        return service.generate_policy(prompt)
    except BadRequestError as exc:
        if _is_content_filtered(exc):
            # Conversations describing a real incident (harassment,
            # violence, etc.) can trip Azure's content filter even
            # though the content itself is legitimate to report - most
            # often it's the "User: ...\nAssistant: ..." transcript
            # format in the prompt getting misread as a jailbreak
            # attempt, not the subject matter itself.
            raise IncidentReportAgentError(
                "This message was flagged by the AI content safety filter. "
                "Try rephrasing it, or continue describing the incident "
                "differently.",
                content_filtered=True,
            ) from exc
        raise IncidentReportAgentError(f"LLM call failed: {exc}") from exc
    except Exception as exc:
        raise IncidentReportAgentError(f"LLM call failed: {exc}") from exc


def _format_conversation(messages: list[dict]) -> str:
    return "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['text']}"
        for m in messages
    )


def _build_reply_prompt(messages: list[dict]) -> str:
    conversation_text = _format_conversation(messages)
    questions_asked = sum(1 for m in messages if m["role"] == "assistant")

    # A soft nudge toward wrapping up - not the actual stopping point.
    # reply_to_incident_message enforces a hard cutoff below regardless
    # of what the model does here, since a prompt instruction alone is
    # just a suggestion the model can (and does) ignore.
    if questions_asked >= 3:
        urgency = (
            "You've already asked several questions - lean toward "
            "acknowledging and suggesting they generate the report unless "
            "something genuinely critical (what happened, or who was "
            "involved) is still completely missing.\n"
        )
    else:
        urgency = ""

    return f"""You are a private assistant helping someone describe a
workplace incident in their own words, one step at a time. Nothing here
is saved or reported to anyone yet — you're just helping them think
through and document what happened before they generate a summary.

Conversation so far:
{conversation_text}

Ask ONE short, focused follow-up question that would help capture an
important missing detail — what happened, when and where, who was
involved or witnessed it, and any immediate impact. Base it on what has
and hasn't been covered already; do not repeat something already
answered.

If the conversation already covers enough to write a useful summary,
respond with a brief acknowledgement instead of a question, and suggest
they click "Generate Summary Report" when ready.

{urgency}Return only your reply — nothing else."""


def _build_summary_prompt(messages: list[dict]) -> str:
    # Only the user's own words go into the summary — the assistant's
    # follow-up questions aren't part of what happened.
    conversation_text = _format_conversation(
        [m for m in messages if m["role"] == "user"]
    )

    return f"""An HR incident report assistant had this conversation with
someone describing a workplace incident:

{conversation_text}

Return ONLY a single JSON object, no other text, in exactly this shape:
{{"summary": "...", "next_steps": ["...", "..."]}}

- summary: a clear, well-structured overview of what was described,
  written in third person, suitable to hand to HR or a manager. Do not
  invent details that weren't mentioned.
- next_steps: 3 to 5 concrete, actionable next steps appropriate to this
  specific incident (e.g. who to escalate to, what evidence to preserve,
  who to check in with) — not generic advice."""


# Hard cap on follow-up questions - the prompt's own "lean toward
# acknowledging" nudge (above) is only a suggestion the model doesn't
# reliably follow, so past this many questions the backend stops asking
# the LLM for another one at all and just tells the user to generate.
MAX_FOLLOW_UP_QUESTIONS = 6


def reply_to_incident_message(messages: list[dict]) -> str:
    if not messages:
        raise IncidentReportAgentError("No conversation to reply to.")

    questions_asked = sum(1 for m in messages if m["role"] == "assistant")

    if questions_asked >= MAX_FOLLOW_UP_QUESTIONS:
        return (
            'I have enough to work with. Click "Generate Summary Report" '
            "when you're ready — or keep adding detail first."
        )

    service = OpenAIService()
    prompt = _build_reply_prompt(messages)
    reply = _call_llm(service, prompt).strip()

    if not reply:
        raise IncidentReportAgentError("LLM returned an empty reply.")

    return reply


def summarize_incident(messages: list[dict]) -> dict:
    if not any(m["role"] == "user" for m in messages):
        raise IncidentReportAgentError("No user messages to summarize.")

    service = OpenAIService()
    prompt = _build_summary_prompt(messages)
    raw_response = _call_llm(service, prompt)

    try:
        cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise IncidentReportAgentError(
            f"LLM returned an unparseable summary: {raw_response!r}"
        ) from exc

    summary = parsed.get("summary", "").strip()
    next_steps = [s.strip() for s in parsed.get("next_steps", []) if isinstance(s, str) and s.strip()]

    if not summary:
        raise IncidentReportAgentError("LLM response is missing a summary.")

    if not next_steps:
        raise IncidentReportAgentError("LLM response has no usable next steps.")

    return {"summary": summary, "next_steps": next_steps}
