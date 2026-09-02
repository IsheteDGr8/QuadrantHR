import json

from openai_service import OpenAIService
from logger import get_logger

logger = get_logger(__name__)

MAX_CHARS_FOR_DRAFT = 4000


class IncidentPolicyAgentError(Exception):
    """Raised when drafting fails — callers should let HR write the policy
    manually rather than silently produce something half-baked."""


def _build_prompt(incident_summary: str, context: str | None) -> str:
    context_block = f"\n\nAdditional context (follow-up Q&A):\n{context}" if context else ""

    return f"""An HR incident report needs to become the basis for a new company
policy that addresses what went wrong and prevents it from happening again.

Incident report:
{incident_summary[:MAX_CHARS_FOR_DRAFT]}{context_block}

Return ONLY a single JSON object, no other text, in exactly this shape:
{{"title": "...", "requirements": ["...", "..."]}}

- title: a short, specific policy title (under 10 words) describing what
  this policy governs — not a restatement of the incident itself.
- requirements: 3 to 8 concrete guideline statements a policy on this
  topic should include, each addressing the underlying issue from the
  incident (not describing the incident itself)."""


def draft_from_incident(incident_summary: str, context: str | None = None) -> dict:
    if not incident_summary.strip():
        raise IncidentPolicyAgentError(
            "incident_summary is empty — nothing to draft a policy from."
        )

    service = OpenAIService()
    prompt = _build_prompt(incident_summary, context)

    try:
        raw_response = service.generate_policy(prompt)
    except Exception as exc:
        raise IncidentPolicyAgentError(f"LLM call failed: {exc}") from exc

    try:
        cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        draft = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise IncidentPolicyAgentError(
            f"LLM returned unparseable draft: {raw_response!r}"
        ) from exc

    title = draft.get("title", "").strip()
    requirements = [r.strip() for r in draft.get("requirements", []) if isinstance(r, str) and r.strip()]

    if not title:
        raise IncidentPolicyAgentError("LLM response is missing a title.")

    if not requirements:
        raise IncidentPolicyAgentError("LLM response has no usable requirements.")

    return {"title": title, "requirements": requirements}
