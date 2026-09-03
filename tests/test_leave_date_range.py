"""
Regression tests for Genie's Leave Management date-range handling
(startDate/endDate) - see models.chatbot.TicketDraft,
agents.chatbot_agent.ExtractedTicketFields, and
services.ticket_draft_service.merge_extracted_fields.

Same convention as tests/test_chatbot.py - GPT's structured decision is
supplied directly via a FakeAIService, since what's under test is the
deterministic merge/validation/missing-field logic built on top of it, not
GPT itself. Frontend assertions are content-level checks on the actual
served script.js, matching tests/test_frontend_chatbot_wiring.py's approach.
"""

from pathlib import Path

from agents.chatbot_agent import ChatActionType, ChatbotDecision, ExtractedTicketFields
from models.chatbot import ChatIntent, ChatRequest, ChatScope, RequestType, TicketDraft
from services import chatbot_service
from services.ticket_draft_service import merge_extracted_fields


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision

    def generate(self, *, system_prompt, user_content, response_model):
        return self.decision


def ask_leave(message, *, decision, **kwargs):
    request = ChatRequest(message=message, **kwargs)
    return chatbot_service.handle_message(request, ai_service=FakeAIService(decision))


def _leave_decision(action_type=ChatActionType.SHOW_TICKET_DRAFT, **fields):
    return ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.LEAVE_MANAGEMENT,
        action=action_type,
        message="",
        ticket_fields=ExtractedTicketFields(**fields) if fields else None,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )


# ---------------------------------------------------------------------------
# 1-3: backend draft merge / serialization / persistence across turns
# ---------------------------------------------------------------------------


def test_date_range_message_produces_both_start_and_end_date():
    decision = _leave_decision(
        start_date="2026-08-24",
        end_date="2026-08-28",
        description="PTO for a family trip.",
        category="Paid Time Off (PTO)",
    )
    response = ask_leave(
        "I need PTO from August 24 through August 28.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ticket_draft.startDate == "2026-08-24"
    assert response.ticket_draft.endDate == "2026-08-28"


def test_both_dates_survive_json_serialization():
    decision = _leave_decision(
        start_date="2026-08-24",
        end_date="2026-08-28",
        description="PTO for a family trip.",
        category="Paid Time Off (PTO)",
    )
    response = ask_leave(
        "I need PTO from August 24 through August 28.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    payload = response.model_dump_json()
    assert '"startDate":"2026-08-24"' in payload
    assert '"endDate":"2026-08-28"' in payload

    # And back out through JSON, exactly as the frontend's sessionStorage
    # pending-draft round trip (JSON.stringify/JSON.parse) does.
    import json

    parsed = json.loads(payload)
    assert parsed["ticket_draft"]["startDate"] == "2026-08-24"
    assert parsed["ticket_draft"]["endDate"] == "2026-08-28"


def test_both_dates_survive_a_turn_that_only_changes_description():
    first_draft = TicketDraft(
        startDate="2026-08-24",
        endDate="2026-08-28",
        category="Paid Time Off (PTO)",
        description="PTO for a family trip.",
        department="Upper Management",
    )
    # Turn 2: "because of a family trip" - GPT extracts only a description
    # update this turn, no dates at all.
    decision = _leave_decision(description="PTO because of a family reunion trip.")
    response = ask_leave(
        "because of a family trip",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
        draft=first_draft,
    )
    assert response.ticket_draft.startDate == "2026-08-24"
    assert response.ticket_draft.endDate == "2026-08-28"
    assert response.ticket_draft.description == "PTO because of a family reunion trip."


def test_short_unpaid_leave_request_sets_type_without_model_category():
    decision = _leave_decision(description="I am requesting unpaid leave.")
    response = ask_leave(
        "I want an unpaid leave",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ticket_draft.category == "Unpaid Leave"
    assert response.missing_fields == ["the start and end dates"]


def test_explicit_unpaid_leave_corrects_stale_pto_category():
    decision = _leave_decision(description="I am requesting unpaid leave.")
    response = ask_leave(
        "Actually, I want unpaid leave",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
        draft=TicketDraft(
            category="Paid Time Off (PTO)",
            description="I am requesting paid time off.",
        ),
    )
    assert response.ticket_draft.category == "Unpaid Leave"


# ---------------------------------------------------------------------------
# 7-10: missing-field / readiness rules
# ---------------------------------------------------------------------------


def test_both_dates_present_does_not_ask_for_date_again():
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(),
        existing_draft=TicketDraft(
            startDate="2026-08-24",
            endDate="2026-08-28",
            category="Paid Time Off (PTO)",
            description="PTO trip",
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert not any("date" in m.lower() for m in missing)


def test_start_only_asks_only_for_end_date():
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(start_date="2026-08-24"),
        existing_draft=TicketDraft(
            category="Paid Time Off (PTO)", description="PTO trip"
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert draft.startDate == "2026-08-24"
    assert draft.endDate is None
    assert missing == ["the end date"]


def test_end_only_asks_only_for_start_date():
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(end_date="2026-08-28"),
        existing_draft=TicketDraft(
            category="Paid Time Off (PTO)", description="PTO trip"
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert draft.endDate == "2026-08-28"
    assert draft.startDate is None
    assert missing == ["the start date"]


def test_neither_date_asks_for_both():
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(),
        existing_draft=TicketDraft(
            category="Paid Time Off (PTO)", description="PTO trip"
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert draft.startDate is None
    assert draft.endDate is None
    assert missing == ["the start and end dates"]


def test_backward_compat_preferred_date_fills_start_date_only():
    # A leave draft that (defensively) only got preferred_date extracted -
    # e.g. GPT put the leave date there instead of start_date - still
    # fills startDate, and never invents an endDate from it.
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(preferred_date="2026-08-24"),
        existing_draft=TicketDraft(
            category="Paid Time Off (PTO)", description="PTO trip"
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert draft.startDate == "2026-08-24"
    assert draft.endDate is None
    assert missing == ["the end date"]


def test_preferred_date_never_used_as_proof_the_range_is_complete():
    # Simulates a stale/older draft that only ever had preferredDate set
    # (no startDate/endDate) - missing-field logic must still ask for
    # dates, never treat preferredDate alone as "the range is done".
    draft, missing = merge_extracted_fields(
        ExtractedTicketFields(),
        existing_draft=TicketDraft(
            preferredDate="2026-08-24",
            category="Paid Time Off (PTO)",
            description="PTO trip",
        ),
        gpt_missing_fields=[],
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    assert missing == ["the start and end dates"]


# ---------------------------------------------------------------------------
# 4-6: frontend prefill wiring (content-level checks on the live script)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SCRIPT_JS = (FRONTEND_DIR / "js" / "script.js").read_text()


def _leave_prefill_block(source: str) -> str:
    start = source.index('requestType === "leave_management"')
    end = source.index("\n    }", start)
    return source[start:end]


def test_frontend_prefill_targets_leave_start_and_end_date_ids():
    block = _leave_prefill_block(SCRIPT_JS)
    assert "leaveStartDate" in block
    assert "leaveEndDate" in block


def test_frontend_sets_leave_end_date_from_draft_end_date():
    block = _leave_prefill_block(SCRIPT_JS)
    assert 'setFieldValue("leaveEndDate", draft.endDate)' in block


def test_frontend_never_sets_leave_end_date_from_preferred_date():
    block = _leave_prefill_block(SCRIPT_JS)
    end_date_line = next(
        line
        for line in block.splitlines()
        if "leaveEndDate" in line and "setFieldValue" in line
    )
    assert "preferredDate" not in end_date_line


def test_frontend_preferred_date_only_fills_start_when_start_missing():
    block = _leave_prefill_block(SCRIPT_JS)
    assert "draft.startDate" in block
    assert 'setFieldValue("leaveStartDate", draft.preferredDate)' in block
    # The preferredDate fallback must be gated behind an explicit
    # "startDate missing" check (an else-if off of `if (draft.startDate)`),
    # not applied unconditionally alongside/after startDate.
    assert "else if (draft.preferredDate)" in block
