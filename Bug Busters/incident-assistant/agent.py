from openai import OpenAI

from models import Policy
from settings import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT


class AgentError(Exception):
    """Raised when the follow-up question can't be generated — callers
    catch this and set the ticket status to "error" rather than letting it
    propagate as a 500."""


def _build_prompt(incident_text: str, policy: Policy) -> str:
    return f"""You are an HR incident-intake assistant. An employee has reported the
following incident, which has been matched to a company policy.

Incident report:
{incident_text}

Matched policy: {policy.name}
Policy description: {policy.description}

Ask exactly one concise, specific follow-up question that would help HR
assess this incident against the matched policy. Return only the question
itself — no preamble, no numbering, no extra commentary."""


class IncidentAgent:
    def __init__(self):
        self.client = None
        self.deployment = AZURE_OPENAI_DEPLOYMENT

        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            return

        self.client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=AZURE_OPENAI_ENDPOINT.rstrip("/") + "/openai/v1/",
        )

    def generate_follow_up_question(self, incident_text: str, policy: Policy) -> str:
        if self.client is None or not self.deployment:
            raise AgentError(
                "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT, "
                "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
            )

        prompt = _build_prompt(incident_text, policy)

        try:
            response = self.client.responses.create(
                model=self.deployment,
                input=prompt,
            )
        except Exception as exc:
            raise AgentError(f"LLM call failed: {exc}") from exc

        question = (response.output_text or "").strip()

        if not question:
            raise AgentError("LLM returned an empty follow-up question.")

        return question
