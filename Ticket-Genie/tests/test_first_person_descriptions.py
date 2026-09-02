"""
First-person ticket description tests.

Genie-generated ticket descriptions previously read like a third-person
AI/HR case note (e.g. "The employee is requesting bereavement leave due
to the death of the employee's grandmother."). The fix is entirely in
GPT-5.2's description-generation contract - chatbot_agent.
CHATBOT_DECISION_PROMPT now instructs the model to write `description` in
first person, as if the requester typed it themselves ("I"/"me"/"my"),
and explicitly forbids third-person/observer phrasing ("the employee",
"the user", "the requester", "the person", etc) - across every flow
(IT, HR, leave, accounting, workplace operations) including anonymous
requests, which stay first person without adding identity details.

We cannot make live GPT calls in tests, so:
- the prompt's instructions are checked structurally (key constraints
  present), not pinned to exact wording, matching this repo's existing
  convention (see test_ticket_description_summary.py).
- the deterministic merge/routing layer (ticket_draft_service,
  chatbot_service) is exercised with realistic first-person fixture text
  a real GPT-5.2 call would plausibly return under the new contract, to
  prove that layer never mangles perspective (no string replacement is
  involved anywhere in the merge path).
"""

import re

from agents.chatbot_agent import (
    CHATBOT_DECISION_PROMPT,
    ChatActionType,
    ChatbotDecision,
    ExtractedTicketFields,
)
from models.chatbot import ChatIntent, ChatRequest, ChatScope, RequestType
from services import chatbot_service
from services.ticket_draft_service import merge_extracted_fields

BANNED_PHRASES = ("the employee", "the user", "the requester", "the person")
_FIRST_PERSON_MARKER = re.compile(r"\b(i|my|me)\b", re.IGNORECASE)


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.decision


def _no_ticket_found(ticket_id):
    return None


def _no_classify_call(*args, **kwargs):
    raise AssertionError("classify_ticket must not be called for this flow")


def ask(message, *, decision, **kwargs):
    request = ChatRequest(message=message, **kwargs)
    response = chatbot_service.handle_message(
        request,
        ai_service=FakeAIService(decision),
        ticket_lookup=_no_ticket_found,
        classify_ticket=_no_classify_call,
    )
    return response


def _assert_first_person_no_banned_phrases(description: str):
    lowered = description.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in lowered, (
            f"found banned phrase {phrase!r} in {description!r}"
        )
    assert _FIRST_PERSON_MARKER.search(description), (
        f"expected a first-person marker (I/my/me) in {description!r}"
    )


# ---------------------------------------------------------------------------
# Prompt contract (structural - not pinned to exact wording)
# ---------------------------------------------------------------------------


def test_prompt_requires_first_person_description():
    assert "FIRST PERSON" in CHATBOT_DECISION_PROMPT
    assert '"I"' in CHATBOT_DECISION_PROMPT
    assert '"my"' in CHATBOT_DECISION_PROMPT.lower()


def test_prompt_forbids_third_person_case_note_phrases():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    for phrase in BANNED_PHRASES:
        assert f'"{phrase}"' in lowered


def test_prompt_addresses_anonymous_requests_stay_first_person():
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "anonymous" in lowered
    assert "first-person voice" in lowered or "first person" in lowered
    # Anonymous requests must not gain identity details as a side effect.
    assert "identity details" in lowered


def test_prompt_still_forbids_inventing_details_alongside_perspective_change():
    # The perspective rule must not weaken the existing no-invention /
    # concise re-synthesis contract it was added next to.
    lowered = CHATBOT_DECISION_PROMPT.lower()
    assert "never invent" in lowered
    assert "3-4 sentence" in CHATBOT_DECISION_PROMPT


# ---------------------------------------------------------------------------
# 1. IT issue
# ---------------------------------------------------------------------------


def test_it_issue_description_is_first_person():
    extracted = ExtractedTicketFields(
        title="VPN connection timeout on Mac",
        description=(
            "My VPN keeps disconnecting on my Mac. The issue started this "
            "morning and is preventing me from staying connected reliably."
        ),
        category="IT & Technology",
    )
    draft, _missing = merge_extracted_fields(
        extracted,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    _assert_first_person_no_banned_phrases(draft.description)


# ---------------------------------------------------------------------------
# 2. Leave request
# ---------------------------------------------------------------------------


def test_leave_description_is_first_person():
    extracted = ExtractedTicketFields(
        description=(
            "I am requesting two weeks of bereavement leave due to the "
            "death of my grandmother."
        ),
        category="Bereavement",
        start_date="2026-08-19",
    )
    draft, _missing = merge_extracted_fields(
        extracted,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    _assert_first_person_no_banned_phrases(draft.description)
    assert draft.department == "Upper Management"


# ---------------------------------------------------------------------------
# 3. Reimbursement / accounting
# ---------------------------------------------------------------------------


def test_reimbursement_description_is_first_person():
    extracted = ExtractedTicketFields(
        title="Client dinner reimbursement",
        description=(
            "I paid for a client dinner last Friday and would like to "
            "request reimbursement for the expense."
        ),
        category="Account Management",
    )
    draft, _missing = merge_extracted_fields(
        extracted,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    _assert_first_person_no_banned_phrases(draft.description)


# ---------------------------------------------------------------------------
# 4. Workplace / badge
# ---------------------------------------------------------------------------


def test_badge_description_is_first_person():
    extracted = ExtractedTicketFields(
        title="Badge access issue",
        description="My badge is not opening the third-floor door.",
        category="HR & Workforce Operations",
    )
    draft, _missing = merge_extracted_fields(
        extracted,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    _assert_first_person_no_banned_phrases(draft.description)


# ---------------------------------------------------------------------------
# 5. Anonymous request - first person, no identity exposure
# ---------------------------------------------------------------------------


def test_anonymous_request_description_is_first_person_without_identity():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        ticket_fields=ExtractedTicketFields(
            title="Anonymous workplace concern",
            description=(
                "I want to report a workplace concern that I would prefer "
                "to keep anonymous."
            ),
            category="HR & Workforce Operations",
        ),
        missing_fields=[],
        request_type=RequestType.ANONYMOUS,
        anonymity_requested=True,
    )
    response = ask(
        "I want to report a workplace concern but I want to stay anonymous.",
        decision=decision,
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True
    _assert_first_person_no_banned_phrases(response.ticket_draft.description)
    lowered = response.ticket_draft.description.lower()
    assert "anonymous employee" not in lowered


# ---------------------------------------------------------------------------
# 6. Multi-turn re-synthesis stays first person (no transcript, no drift
#    to third person)
# ---------------------------------------------------------------------------


def test_multi_turn_description_remains_first_person_after_resynthesis():
    turn_1 = ExtractedTicketFields(
        title="Laptop crashing",
        description="My laptop keeps crashing.",
    )
    turn_2_final = ExtractedTicketFields(
        title="Laptop crashing since update",
        description=(
            "My laptop has been crashing since I installed the update yesterday."
        ),
    )
    draft, _missing = merge_extracted_fields(
        turn_1,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    draft, _missing = merge_extracted_fields(
        turn_2_final,
        existing_draft=draft,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    # Replaced with the latest full synthesis, not appended.
    assert draft.description == turn_2_final.description
    assert turn_1.description not in draft.description
    _assert_first_person_no_banned_phrases(draft.description)


# ---------------------------------------------------------------------------
# 7. No banned third-person phrases across the whole fixture set above
# ---------------------------------------------------------------------------


def test_no_generated_description_uses_third_person_case_note_phrasing():
    fixtures = [
        "My VPN keeps disconnecting on my Mac.",
        "I am requesting two weeks of bereavement leave due to the death of my grandmother.",
        "I paid for a client dinner last Friday and would like to request reimbursement.",
        "My badge is not opening the third-floor door.",
        "I want to report a workplace concern that I would prefer to keep anonymous.",
    ]
    for text in fixtures:
        draft, _missing = merge_extracted_fields(
            ExtractedTicketFields(description=text),
            existing_draft=None,
            gpt_missing_fields=[],
            intent=ChatIntent.SUPPORT_ISSUE,
        )
        _assert_first_person_no_banned_phrases(draft.description)


# ---------------------------------------------------------------------------
# 8-11. Pre-existing behavior this change must not regress (spot-checked
# here directly; full suites live in their own files and are run in CI/
# pytest tests/).
# ---------------------------------------------------------------------------


def test_existing_concise_resynthesis_behavior_still_holds():
    # Same scenario as test_ticket_description_summary.py's headline test,
    # re-checked here to prove the perspective change didn't reintroduce
    # transcript-style appending.
    turn_1 = ExtractedTicketFields(description="The VPN is not connecting.")
    turn_2 = ExtractedTicketFields(
        description="My VPN has not been connecting on my Mac since this morning."
    )
    draft, _missing = merge_extracted_fields(
        turn_1,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    draft, _missing = merge_extracted_fields(
        turn_2,
        existing_draft=draft,
        gpt_missing_fields=[],
        intent=ChatIntent.SUPPORT_ISSUE,
    )
    assert draft.description == turn_2.description


def test_existing_leave_date_handling_still_holds():
    extracted = ExtractedTicketFields(
        description="I am requesting medical leave from August 20 to August 28.",
        category="Medical Leave",
        start_date="2026-08-20",
        end_date="2026-08-28",
    )
    draft, missing = merge_extracted_fields(
        extracted,
        existing_draft=None,
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert draft.startDate == "2026-08-20"
    assert draft.endDate == "2026-08-28"
    assert missing == []


def test_existing_leave_hard_department_rule_still_holds():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.LEAVE_MANAGEMENT,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        ticket_fields=ExtractedTicketFields(
            description="I am requesting bereavement leave due to the death of my grandmother.",
            category="Bereavement",
        ),
        missing_fields=[],
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    response = ask(
        "I need bereavement leave.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ticket_draft.department == "Upper Management"
    _assert_first_person_no_banned_phrases(response.ticket_draft.description)
