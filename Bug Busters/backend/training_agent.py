import json

from openai_service import OpenAIService
from logger import get_logger

logger = get_logger(__name__)

# Guidance, not a hard enum — keeps categories consistent enough to be
# useful for filtering later without boxing the AI into a category that
# doesn't actually fit a given document.
SUGGESTED_CATEGORIES = [
    "Handbook",
    "Onboarding",
    "Conduct",
    "Compliance",
    "Benefits",
    "Safety",
    "Training",
]

# Long documents don't need to be sent in full for a title/summary — this
# keeps prompt size (and cost) down without losing what the document is
# actually about, which is usually clear from the opening portion.
MAX_CHARS_FOR_METADATA = 6000


class TrainingAgentError(Exception):
    """Raised when metadata generation fails — callers should fall back to
    asking a human, not silently invent a title."""


def _build_prompt(filename: str, extracted_text: str) -> str:
    excerpt = extracted_text[:MAX_CHARS_FOR_METADATA]
    categories = ", ".join(SUGGESTED_CATEGORIES)

    return f"""You are cataloging a company training/onboarding document so employees can find it later.

Filename: {filename}

Document content (may be truncated):
---
{excerpt}
---

Suggested categories (pick the best fit, or a short one-or-two-word
category of your own if none of these actually fit): {categories}

Return ONLY a single JSON object, no other text, in exactly this shape:
{{"title": "...", "description": "...", "category": "..."}}

- title: a short, specific title (under 10 words) — not the filename.
- description: one or two sentences describing what an employee would
  learn or find in this document.
- category: one of the suggested categories, or your own short one if
  none fit."""


def generate_metadata(filename: str, extracted_text: str) -> dict:
    if not extracted_text.strip():
        raise TrainingAgentError(
            "No extractable text — can't generate metadata from an empty document."
        )

    service = OpenAIService()
    prompt = _build_prompt(filename, extracted_text)

    try:
        raw_response = service.generate_policy(prompt)
    except Exception as exc:
        raise TrainingAgentError(f"LLM call failed: {exc}") from exc

    try:
        # Models sometimes wrap JSON in a code fence despite instructions —
        # strip that before parsing rather than failing on it.
        cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        metadata = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise TrainingAgentError(
            f"LLM returned unparseable metadata: {raw_response!r}"
        ) from exc

    for field in ("title", "description", "category"):
        if not metadata.get(field, "").strip():
            raise TrainingAgentError(f"LLM response is missing '{field}'.")

    return {
        "title": metadata["title"].strip(),
        "description": metadata["description"].strip(),
        "category": metadata["category"].strip(),
    }
