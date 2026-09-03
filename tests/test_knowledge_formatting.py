"""
Knowledge/RAG grounded-answer formatting tests.

Previously GROUNDED_ANSWER_PROMPT only said "keep the answer concise",
which in practice produced answers like:
"Northstar's guidance in the provided materials is: - **Submission
timing:** ... - **Required details:** ... - **Where to submit:** ..."
- correct, but visually a run-on wall of inline bold/bullets.

We cannot make live GPT calls in tests, so:
- the prompt's formatting instructions are checked structurally (the
  actual anti-patterns called out in the bug report), not pinned to
  exact wording.
- the retrieval/grounding plumbing (answer_from_context) is exercised
  directly with a FakeAIService to prove grounding/verification behavior
  is completely unchanged by the prompt rewrite - nothing about
  authorization, retrieval, or the verified/unverified contract moved.
"""

from agents.knowledge_agent import (
    GROUNDED_ANSWER_PROMPT,
    GroundedAnswer,
    answer_from_context,
)
from services.knowledge_service import KnowledgeDocument


class FakeAIService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.response


_DOC = KnowledgeDocument(
    id="doc-1",
    content=(
        "Business reimbursement requests should normally be submitted "
        "within 45 calendar days of the expense date. Include business "
        "purpose, date, amount, and receipt documentation when available. "
        "Use the ACC-001 Reimbursement service (Accounting) as a Standard "
        "Request."
    ),
    scope="Accounting",
    source="Reimbursement Policy",
)


# ---------------------------------------------------------------------------
# Prompt content: the specific anti-patterns from the bug report
# ---------------------------------------------------------------------------


def test_prompt_prefers_short_paragraphs_for_policy_questions():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "1-2 short paragraphs" in lowered or "short paragraph" in lowered


def test_prompt_restricts_bullets_to_genuine_multi_step_answers():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "distinct steps or items" in lowered


def test_prompt_requires_bullets_on_their_own_line():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "own line" in lowered


def test_prompt_forbids_inline_run_on_bullet_formatting():
    assert "**Label:** text - **Label:** text" in GROUNDED_ANSWER_PROMPT


def test_prompt_forbids_robotic_preamble():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "provided materials is" in lowered
    assert "robotic preamble" in lowered


def test_prompt_discourages_overusing_bold():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "do not overuse bold" in lowered


def test_prompt_still_forbids_inventing_policy():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "do not invent" in lowered
    assert "never outside knowledge" in lowered


def test_prompt_still_requires_unverified_fallback_when_insufficient():
    lowered = GROUNDED_ANSWER_PROMPT.lower()
    assert "verified to false" in lowered
    assert "could not be verified" in lowered


# ---------------------------------------------------------------------------
# Grounding/retrieval plumbing unchanged
# ---------------------------------------------------------------------------


def test_no_documents_still_returns_unverified_without_calling_gpt():
    ai_service = FakeAIService(response=None)
    result = answer_from_context(
        "What is the reimbursement policy?", [], ai_service=ai_service
    )
    assert result.verified is False
    assert ai_service.calls == []


def test_answer_from_context_still_grounds_strictly_on_retrieved_documents():
    # The retrieved context is exactly what's passed as user_content -
    # unrelated to formatting, and unchanged by the prompt rewrite.
    ai_service = FakeAIService(
        response=GroundedAnswer(
            answer=(
                "Business reimbursement requests should normally be "
                "submitted within 45 calendar days of the expense date. "
                "Include the business purpose, date, amount, and receipt "
                "when available.\n\nTo submit it, use the ACC-001 "
                "Reimbursement service under Accounting as a Standard "
                "Request."
            ),
            verified=True,
        )
    )
    result = answer_from_context(
        "What is the reimbursement policy?", [_DOC], ai_service=ai_service
    )
    assert result.verified is True
    assert "45 calendar days" in result.answer
    assert _DOC.content in ai_service.calls[0][1]  # user_content includes context
    assert ai_service.calls[0][2] is GroundedAnswer


def test_unverified_gpt_response_still_passes_through_unmodified():
    ai_service = FakeAIService(
        response=GroundedAnswer(
            answer="I couldn't verify an answer to that from the provided context.",
            verified=False,
        )
    )
    result = answer_from_context(
        "What is the alien invasion policy?", [_DOC], ai_service=ai_service
    )
    assert result.verified is False


def test_readable_example_answer_avoids_inline_run_on_bullets():
    # Demonstrates the desired shape from the task's example - a real
    # GPT response like this should never be reformatted/mangled by the
    # (unchanged) plumbing.
    readable_answer = (
        "Business reimbursement requests should normally be submitted "
        "within 45 calendar days of the expense date. Include the "
        "business purpose, date, amount, and receipt when available.\n\n"
        "To submit it, use the ACC-001 Reimbursement service under "
        "Accounting as a Standard Request."
    )
    ai_service = FakeAIService(
        response=GroundedAnswer(answer=readable_answer, verified=True)
    )
    result = answer_from_context(
        "What is the reimbursement policy?", [_DOC], ai_service=ai_service
    )
    assert result.answer == readable_answer
    assert "- **" not in result.answer
    assert not result.answer.lower().startswith("northstar")


def test_procedural_answer_may_use_line_separated_bullets():
    procedural_answer = (
        "To reset your password:\n"
        "1. Go to the IT self-service portal.\n"
        '2. Click "Reset Password".\n'
        "3. Follow the emailed verification link."
    )
    ai_service = FakeAIService(
        response=GroundedAnswer(answer=procedural_answer, verified=True)
    )
    result = answer_from_context(
        "How do I reset my password?", [_DOC], ai_service=ai_service
    )
    lines = [line for line in result.answer.split("\n") if line.strip()]
    assert len(lines) >= 3
