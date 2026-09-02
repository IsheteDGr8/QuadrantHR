import json

from openai_service import OpenAIService
from logger import get_logger

logger = get_logger(__name__)

MIN_QUESTIONS = 3
MAX_QUESTIONS = 6


class QuestionnaireAgentError(Exception):
    """Raised when question generation fails - callers should fall back to
    the static generic questionnaire fields rather than showing nothing."""


def _build_prompt(title: str, policy_type: str | None) -> str:
    context_line = (
        f'This section is categorized under "{policy_type}".\n' if policy_type else ""
    )

    return f"""An HR person is about to write a company policy section titled:
"{title}"
{context_line}
Generate the specific questions you'd need to ask them to write this
section well - the details only they would know (their company's actual
rules, numbers, exceptions), not generic HR boilerplate.

Return ONLY a JSON array, no other text, of {MIN_QUESTIONS}-{MAX_QUESTIONS}
objects in exactly this shape:
[{{"key": "short_snake_case_id", "label": "The question, phrased directly to HR", "placeholder": "A short example of what an answer might look like"}}]

- key: unique within the array, short, snake_case, no spaces.
- label: a real question about THIS specific topic, not a restatement of
  the title.
- placeholder: brief, illustrative, not a real company's actual policy."""


def _parse_questions(raw_response: str) -> list[dict]:
    cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        questions = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise QuestionnaireAgentError(
            f"LLM returned unparseable questions: {raw_response!r}"
        ) from exc

    if not isinstance(questions, list):
        raise QuestionnaireAgentError("LLM response was not a JSON array.")

    cleaned_questions = []
    seen_keys = set()

    for item in questions:
        if not isinstance(item, dict):
            continue

        key = str(item.get("key", "")).strip()
        label = str(item.get("label", "")).strip()
        placeholder = str(item.get("placeholder", "")).strip()

        if not key or not label or key in seen_keys:
            continue

        seen_keys.add(key)
        cleaned_questions.append({"key": key, "label": label, "placeholder": placeholder})

    if not cleaned_questions:
        raise QuestionnaireAgentError("LLM response had no usable questions.")

    return cleaned_questions


def generate_questions(title: str, policy_type: str | None = None) -> list[dict]:
    if not title.strip():
        raise QuestionnaireAgentError("title is empty - nothing to generate questions about.")

    service = OpenAIService()
    prompt = _build_prompt(title, policy_type)

    try:
        raw_response = service.generate_policy(prompt)
    except Exception as exc:
        raise QuestionnaireAgentError(f"LLM call failed: {exc}") from exc

    return _parse_questions(raw_response)
