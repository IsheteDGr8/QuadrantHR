"""
Regression tests for the Genie leave-drafting -> Create Ticket "Leave
Management" tab routing bug (branch fix/genie-leave-tab-routing).

Root cause: models.chatbot.ChatResponse.request_type is a field on the
response itself, deliberately separate from ChatResponse.ticket_draft
(models.chatbot.TicketDraft mirrors TicketCreate and has no request_type
field - see its docstring). frontend/src/components/GenieAgentWidget.svelte
used to write only `res.ticket_draft` into genieDraftStore, dropping
`res.request_type` on the floor. frontend/src/views/CreateTicketView.svelte
picks activeFormTab from `$genieDraftStore.request_type`, so every draft
landed with request_type=undefined and silently fell through to its
`else` (Standard) branch - regardless of the actual intent - and leave
text got prefilled into the Standard form instead.

There's no JS test runner in this repo (see test_frontend_chatbot_wiring.py
/ test_leave_date_range.py's module docstrings for the same convention) so
the live-Svelte assertions here are content-level checks on the actual
served files, plus backend-level tests on services.chatbot_service proving
request_type/dates/category survive exactly the shapes the frontend reads.
"""

from pathlib import Path

from agents.chatbot_agent import ChatActionType, ChatbotDecision, ExtractedTicketFields
from models.chatbot import ChatIntent, ChatRequest, ChatScope, RequestType, TicketDraft
from services import chatbot_service

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
GENIE_WIDGET_SVELTE = (
    FRONTEND_DIR / "src" / "components" / "GenieAgentWidget.svelte"
).read_text()
# Both the floating popup (GenieAgentWidget.svelte) and the full page
# (GenieAIView.svelte) call the SAME applyGenieResponseActions() in
# lib/stores/genieChat.js for the ticket_draft/request_type merge and the
# ready_for_review handoff - neither surface owns this logic itself (see
# tests/test_genie_ai_page_wiring.py's module docstring).
GENIE_CHAT_STORE_JS = (
    FRONTEND_DIR / "src" / "lib" / "stores" / "genieChat.js"
).read_text()
CREATE_TICKET_VIEW_SVELTE = (
    FRONTEND_DIR / "src" / "views" / "CreateTicketView.svelte"
).read_text()


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision

    def generate(self, *, system_prompt, user_content, response_model):
        return self.decision


def ask(message, *, decision, **kwargs):
    request = ChatRequest(message=message, **kwargs)
    return chatbot_service.handle_message(request, ai_service=FakeAIService(decision))


def _leave_decision(**fields):
    return ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.LEAVE_MANAGEMENT,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="",
        ticket_fields=ExtractedTicketFields(**fields) if fields else None,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )


# ---------------------------------------------------------------------------
# Live Svelte wiring: genieDraftStore must carry request_type
# ---------------------------------------------------------------------------


def test_genie_chat_store_merges_request_type_into_the_draft_store():
    # The exact bug: genieDraftStore.set(res.ticket_draft) alone drops
    # res.request_type, since TicketDraft has no such field of its own.
    assert "genieDraftStore.set(res.ticket_draft)" not in GENIE_CHAT_STORE_JS
    assert "request_type: res.request_type" in GENIE_CHAT_STORE_JS


def test_genie_chat_store_still_navigates_to_create_ticket_on_ready_for_review():
    assert "res.ready_for_review" in GENIE_CHAT_STORE_JS
    assert "activeTab.set('create-ticket')" in GENIE_CHAT_STORE_JS


# ---------------------------------------------------------------------------
# Live Svelte wiring: CreateTicketView tab selection is deterministic on
# request_type, never on keyword-matching title/description text.
# ---------------------------------------------------------------------------


def _leave_prefill_block(source: str) -> str:
    start = source.index("request_type === 'leave_management'")
    end = source.index("} else if (draft.request_type === 'anonymous')", start)
    return source[start:end]


def test_leave_request_type_activates_leave_tab():
    block = _leave_prefill_block(CREATE_TICKET_VIEW_SVELTE)
    assert "activeFormTab = 'leave'" in block


def test_anonymous_request_type_activates_anonymous_tab():
    start = CREATE_TICKET_VIEW_SVELTE.index("draft.request_type === 'anonymous'")
    end = CREATE_TICKET_VIEW_SVELTE.index("} else {", start)
    block = CREATE_TICKET_VIEW_SVELTE[start:end]
    assert "activeFormTab = 'anonymous'" in block


def test_fallback_branch_activates_standard_tab():
    start = CREATE_TICKET_VIEW_SVELTE.index(
        "} else {\n      activeFormTab = 'standard';"
    )
    assert "activeFormTab = 'standard'" in CREATE_TICKET_VIEW_SVELTE[start : start + 80]


def test_tab_selection_never_keyword_matches_description_text():
    block = _leave_prefill_block(CREATE_TICKET_VIEW_SVELTE)
    assert "description.includes" not in block
    assert "title.includes" not in block


def test_leave_tab_prefill_maps_start_and_end_date_separately():
    block = _leave_prefill_block(CREATE_TICKET_VIEW_SVELTE)
    assert "startDate = draft.startDate" in block
    assert "endDate = draft.endDate" in block
    # preferredDate may only ever act as a startDate fallback, never as a
    # source for endDate (that would fabricate an end of range).
    assert "endDate = draft.preferredDate" not in block


def test_leave_tab_prefill_maps_category_through_a_compatibility_table_not_title():
    block = _leave_prefill_block(CREATE_TICKET_VIEW_SVELTE)
    # The old bug mapped the free-text title onto the leave-type <select>.
    assert "leaveType = draft.title" not in block
    assert "LEAVE_CATEGORY_TO_FORM_TYPE" in block
    assert "'Bereavement': 'Bereavement Leave'" in CREATE_TICKET_VIEW_SVELTE
    assert "'Medical Leave': 'Sick Leave'" in CREATE_TICKET_VIEW_SVELTE


def test_leave_form_never_auto_submits_from_the_prefill_reactive_block():
    block = _leave_prefill_block(CREATE_TICKET_VIEW_SVELTE)
    assert "submitNewTicket" not in block
    assert ".submit()" not in block


def test_genie_draft_is_consumed_after_prefill_so_fields_remain_editable():
    """The shared draft must not keep overwriting user-controlled form state."""
    prefill_start = CREATE_TICKET_VIEW_SVELTE.index("$: if ($genieDraftStore)")
    prefill_end = CREATE_TICKET_VIEW_SVELTE.index("// Standard Request Fields")
    prefill_block = CREATE_TICKET_VIEW_SVELTE[prefill_start:prefill_end]

    assert "genieDraftStore.set(null)" in prefill_block
    assert (
        '<select id="leave-type" bind:value={leaveType}>' in CREATE_TICKET_VIEW_SVELTE
    )
    assert 'type="date" bind:value={startDate}' in CREATE_TICKET_VIEW_SVELTE
    assert 'type="date" bind:value={endDate}' in CREATE_TICKET_VIEW_SVELTE
    assert "bind:value={leaveNotes}" in CREATE_TICKET_VIEW_SVELTE


# ---------------------------------------------------------------------------
# Backend: request_type + draft fields are exactly what CreateTicketView
# needs, in the exact bereavement/PTO/medical scenarios from the bug report.
# ---------------------------------------------------------------------------


def test_bereavement_leave_ready_for_review_carries_leave_request_type():
    decision = _leave_decision(
        description="Requesting bereavement leave.",
        category="Bereavement",
        start_date="2026-08-19",
        end_date="2026-09-02",
    )
    response = ask(
        "bereavement obviously and yes it will be 2 weeks from today",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ready_for_review is True
    assert response.ticket_draft.category == "Bereavement"
    assert response.ticket_draft.startDate == "2026-08-19"
    assert response.ticket_draft.endDate == "2026-09-02"


def test_pto_leave_draft_carries_leave_request_type():
    decision = _leave_decision(
        description="Requesting PTO next week.",
        category="Paid Time Off (PTO)",
        start_date="2026-08-24",
        end_date="2026-08-28",
    )
    response = ask(
        "I need PTO next week.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ticket_draft.category == "Paid Time Off (PTO)"


def test_medical_sick_leave_draft_carries_leave_request_type():
    decision = _leave_decision(
        description="Requesting medical leave from August 20 to August 28.",
        category="Medical Leave",
        start_date="2026-08-20",
        end_date="2026-08-28",
    )
    response = ask(
        "I need medical leave from August 20 to August 28.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ticket_draft.category == "Medical Leave"


def test_multi_turn_leave_flow_still_carries_leave_request_type_on_final_date_only_turn():
    # "What kind of leave?" -> "Bereavement." -> "When should it start and
    # end?" -> "Today for two weeks." The final user turn is only a
    # date/duration - no mention of "leave" at all - so request_type must
    # come from the continued active_intent, never re-derived from this
    # turn's text.
    existing = TicketDraft(
        description="Requesting bereavement leave.",
        category="Bereavement",
        department="Upper Management",
    )
    decision = _leave_decision(start_date="2026-08-19", end_date="2026-09-02")
    response = ask(
        "Today for two weeks.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
        active_request_type=RequestType.LEAVE_MANAGEMENT,
        draft=existing,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ticket_draft.startDate == "2026-08-19"
    assert response.ticket_draft.endDate == "2026-09-02"
    assert response.ticket_draft.category == "Bereavement"


def test_standard_request_ready_for_review_carries_standard_request_type():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        ticket_fields=ExtractedTicketFields(
            title="VPN not working",
            description="My VPN is not working.",
            category="IT & Technology",
        ),
        request_type=RequestType.STANDARD,
    )
    response = ask("My VPN is broken.", decision=decision)
    assert response.request_type == RequestType.STANDARD
    assert response.ready_for_review is True


def test_anonymous_request_ready_for_review_carries_anonymous_request_type():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        request_type=RequestType.ANONYMOUS,
        anonymity_requested=True,
        ticket_fields=ExtractedTicketFields(
            title="Workplace concern",
            description="I need to report a workplace issue anonymously.",
            category="HR & Workforce Operations",
        ),
    )
    response = ask(
        "I need to report a workplace issue but want to stay anonymous.",
        decision=decision,
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True


def test_leave_drafting_response_never_carries_a_navigate_action():
    decision = _leave_decision(
        description="Requesting PTO next week.", category="Paid Time Off (PTO)"
    )
    response = ask(
        "I'd like to request PTO next week.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.action is None


def test_leave_intent_continuation_is_never_reclassified_as_navigation():
    # Even if GPT's own decision.intent this turn drifted to navigation,
    # an in-progress leave draft (echoed via active_intent) must keep being
    # handled as ticket drafting, never navigation/calendar routing.
    existing = TicketDraft(
        description="Requesting PTO.", category="Paid Time Off (PTO)"
    )
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.NAVIGATION,
        action=ChatActionType.NAVIGATE,
        message="",
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(start_date="2026-08-24"),
    )
    response = ask(
        "Starting next Monday.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
        active_request_type=RequestType.LEAVE_MANAGEMENT,
        draft=existing,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.action is None
