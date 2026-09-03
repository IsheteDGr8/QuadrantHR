"""
Request-type / form-selection drafting tests.

Covers which of the three existing New Request forms (Standard, Anonymous,
Leave Management) the chatbot picks for a draft, and the deterministic
rules layered on top of GPT's semantic decision: leave always forces
department=Upper Management and skips normal classification, "Other"
triggers reuse of Saketh's real classifier (agents.orchestrator.classify_
ticket), and General is never a department. All GPT/classifier calls are
faked - no live Azure requests.
"""

from agents.chatbot_agent import ChatActionType, ChatbotDecision, ExtractedTicketFields
from agents.orchestrator import TicketClassification
from models.chatbot import ChatIntent, ChatRequest, ChatScope, RequestType, TicketDraft
from services import chatbot_service, ticket_draft_service


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.decision


def _no_ticket_found(ticket_id):
    return None


def _classification(department, category="Other IT Request"):
    return TicketClassification(
        department=department,
        category=category,
        priority="Medium",
        confidence=0.9,
        reason="test",
        needs_human_review=False,
    )


def _no_classify_call(*args, **kwargs):
    raise AssertionError("classify_ticket must not be called for this flow")


def ask(message, *, decision, classify_ticket=_no_classify_call, **kwargs):
    request = ChatRequest(message=message, **kwargs)
    response = chatbot_service.handle_message(
        request,
        ai_service=FakeAIService(decision),
        ticket_lookup=_no_ticket_found,
        classify_ticket=classify_ticket,
    )
    return response


def _standard_decision(**overrides):
    fields = dict(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        ticket_fields=ExtractedTicketFields(
            title="Need two monitors",
            description="I need two monitors for my desk.",
            category="IT & Technology",
        ),
        missing_fields=[],
        request_type=RequestType.STANDARD,
    )
    fields.update(overrides)
    return ChatbotDecision(**fields)


# ---------------------------------------------------------------------------
# Standard-is-the-default scenarios (explicit product requirement: never
# ask Standard vs Anonymous for an ordinary support request).
# ---------------------------------------------------------------------------


def test_vpn_issue_defaults_to_standard():
    decision = _standard_decision(
        ticket_fields=ExtractedTicketFields(
            title="VPN not working",
            description="My VPN is not working.",
            category="IT & Technology",
        )
    )
    response = ask("I am facing issues with my VPN", decision=decision)
    assert response.request_type == RequestType.STANDARD
    assert response.ready_for_review is True


def test_two_monitors_defaults_to_standard():
    response = ask("I need two monitors", decision=_standard_decision())
    assert response.request_type == RequestType.STANDARD


def test_reimbursement_help_defaults_to_standard():
    decision = _standard_decision(
        ticket_fields=ExtractedTicketFields(
            title="Reimbursement help",
            description="I need help with reimbursement.",
            category="Account Management",
        )
    )
    response = ask("I need help with reimbursement", decision=decision)
    assert response.request_type == RequestType.STANDARD


def test_explicit_anonymity_in_free_text_selects_anonymous():
    decision = _standard_decision(
        request_type=RequestType.ANONYMOUS,
        anonymity_requested=True,
        ticket_fields=ExtractedTicketFields(
            title="Anonymous report",
            description="I need to report an issue but want to stay anonymous.",
            category="HR & Workforce Operations",
        ),
    )
    response = ask(
        "I need to report an issue but want to stay anonymous.", decision=decision
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True


def test_explicit_anonymous_ui_selection_is_respected():
    # e.g. the user picked the Anonymous Request tab explicitly - echoed
    # back as active_request_type - even if this turn's free text alone
    # wouldn't have implied anonymity.
    decision = _standard_decision(request_type=None)
    response = ask(
        "It happened yesterday.",
        decision=decision,
        active_intent=ChatIntent.SUPPORT_ISSUE,
        active_request_type=RequestType.ANONYMOUS,
        draft=TicketDraft(description="I need to report a concern."),
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True


def test_leave_request_selects_leave_management():
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(
            description="Requesting PTO next week.", category="Paid Time Off (PTO)"
        ),
    )
    response = ask(
        "I'd like to request PTO next week.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT


def test_gpt_proposing_anonymous_without_explicit_evidence_is_deterministically_downgraded():
    # GPT sets request_type=anonymous but never marked anonymity_requested
    # - nothing in the conversation actually asked for anonymity.
    decision = _standard_decision(
        request_type=RequestType.ANONYMOUS, anonymity_requested=False
    )
    response = ask("I am facing issues with my VPN", decision=decision)
    assert response.request_type == RequestType.STANDARD
    assert response.ticket_draft.is_anonymous is False


# ---------------------------------------------------------------------------
# Form selection
# ---------------------------------------------------------------------------


def test_standard_request_selected_when_no_anonymity_requested():
    response = ask("I need two monitors for my desk.", decision=_standard_decision())
    assert response.request_type == RequestType.STANDARD
    assert response.ticket_draft.is_anonymous is False


def test_anonymous_selected_when_user_explicitly_asks():
    decision = _standard_decision(
        request_type=RequestType.ANONYMOUS,
        anonymity_requested=True,
        ticket_fields=ExtractedTicketFields(
            title="Workplace concern",
            description="I need to report a workplace issue but want to remain anonymous.",
            category="HR & Workforce Operations",
        ),
    )
    response = ask(
        "I need to report a workplace issue but I don't want my name attached.",
        decision=decision,
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True


def test_leave_intent_always_resolves_to_leave_management_request_type():
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(
            description="Requesting medical leave from August 20 to August 28.",
            category="Medical Leave",
            preferred_date="2026-08-20",
        ),
    )
    response = ask(
        "I need medical leave from August 20 to August 28.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT


def test_ambiguous_request_type_defaults_to_standard_without_asking():
    # No standard-vs-anonymous clarifying question should ever be asked -
    # ordinary requests just default to standard.
    decision = _standard_decision(request_type=None)
    response = ask("My VPN has been broken since this morning.", decision=decision)
    assert response.request_type == RequestType.STANDARD
    assert "anonymous" not in response.message.lower()


def test_gpt_anonymous_without_explicit_anonymity_downgrades_to_standard():
    # GPT incorrectly proposes anonymous but never set anonymity_requested
    # - the deterministic backend check must downgrade this to standard.
    decision = _standard_decision(
        request_type=RequestType.ANONYMOUS, anonymity_requested=False
    )
    response = ask("My VPN has been broken since this morning.", decision=decision)
    assert response.request_type == RequestType.STANDARD
    assert response.ticket_draft.is_anonymous is False


def test_sensitive_topic_never_assumed_anonymous():
    decision = _standard_decision(
        request_type=None,
        ticket_fields=ExtractedTicketFields(
            title="Workplace conflict",
            description="I want to report a harassment incident with my manager.",
            category="HR & Workforce Operations",
        ),
    )
    response = ask(
        "I want to report a harassment incident with my manager.", decision=decision
    )
    assert response.request_type == RequestType.STANDARD


def test_continuation_keeps_previously_chosen_request_type():
    existing = TicketDraft(description="I need to report a concern.")
    decision = _standard_decision(request_type=None, missing_fields=[])
    response = ask(
        "It happened yesterday afternoon.",
        decision=decision,
        active_intent=ChatIntent.SUPPORT_ISSUE,
        active_request_type=RequestType.ANONYMOUS,
        draft=existing,
    )
    assert response.request_type == RequestType.ANONYMOUS
    assert response.ticket_draft.is_anonymous is True


def test_knowledge_navigation_status_never_set_request_type_or_draft():
    from agents.chatbot_agent import NavigationTarget

    nav_decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.NAVIGATION,
        action=ChatActionType.NAVIGATE,
        message="Heading to My Tickets.",
        navigation_target=NavigationTarget.MY_TICKETS,
    )
    response = ask("Where can I see my submitted requests?", decision=nav_decision)
    assert response.request_type is None
    assert response.ticket_draft is None


# ---------------------------------------------------------------------------
# Leave hard routing rule
# ---------------------------------------------------------------------------


def test_leave_draft_always_routes_to_upper_management():
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(
            description="Requesting PTO next week.", category="Paid Time Off (PTO)"
        ),
    )
    response = ask(
        "I'd like to request PTO next week.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ticket_draft.department == ticket_draft_service.LEAVE_DEPARTMENT
    assert response.ticket_draft.department == "Upper Management"


def test_leave_management_skips_normal_classification():
    # classify_ticket defaults to _no_classify_call, which raises if invoked
    # at all - proves reclassify_other_category is never reached for leave.
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(
            description="Requesting unpaid leave.", category="Other"
        ),
    )
    response = ask(
        "I need unpaid leave.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ticket_draft.department == "Upper Management"


def test_model_cannot_override_hard_leave_department_rule():
    # The model incorrectly claims request_type=standard for a leave
    # intent - the deterministic rule must win regardless.
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.STANDARD,
        ticket_fields=ExtractedTicketFields(
            description="Requesting bereavement leave.", category="Bereavement"
        ),
    )
    response = ask(
        "I need bereavement leave.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ticket_draft.department == "Upper Management"


def test_leave_never_becomes_standard_across_turns():
    existing = TicketDraft(
        description="Requesting PTO.", category="Paid Time Off (PTO)"
    )
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
        missing_fields=[],
    )
    response = ask(
        "Starting next Monday.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
        active_request_type=RequestType.LEAVE_MANAGEMENT,
        draft=existing,
    )
    assert response.request_type == RequestType.LEAVE_MANAGEMENT
    assert response.ticket_draft.department == "Upper Management"


# ---------------------------------------------------------------------------
# Standard / Anonymous "Other" reclassification (reuses the real classifier)
# ---------------------------------------------------------------------------


def test_other_category_reclassified_via_existing_classifier_for_standard():
    decision = _standard_decision(
        ticket_fields=ExtractedTicketFields(
            title="Badge issue",
            description="My office badge stopped working.",
            category="Other",
        )
    )
    response = ask(
        "My office badge stopped working.",
        decision=decision,
        classify_ticket=lambda t, d: _classification("IT Team"),
    )
    assert response.ticket_draft.category == "IT & Technology"


def test_other_category_reclassified_for_anonymous_too():
    decision = _standard_decision(
        request_type=RequestType.ANONYMOUS,
        anonymity_requested=True,
        ticket_fields=ExtractedTicketFields(
            title="Accounting concern",
            description="There's a billing discrepancy on my company card.",
            category="Other",
        ),
    )
    response = ask(
        "I don't want my name attached to this billing concern.",
        decision=decision,
        classify_ticket=lambda t, d: _classification(
            "Accounting Team", category="Company Card Management"
        ),
    )
    assert response.ticket_draft.category == "Account Management"
    assert response.ticket_draft.is_anonymous is True


def test_department_with_no_standard_category_equivalent_falls_back_to_other():
    decision = _standard_decision(
        ticket_fields=ExtractedTicketFields(
            title="Office maintenance",
            description="The office A/C is broken.",
            category="Other",
        )
    )
    response = ask(
        "The office A/C is broken.",
        decision=decision,
        classify_ticket=lambda t, d: _classification(
            "Workplace Operations Team", category="Maintenance"
        ),
    )
    assert response.ticket_draft.category == "Other"


def test_classifier_failure_falls_back_safely_to_other():
    def _raise(title, description):
        raise RuntimeError("classifier unavailable")

    decision = _standard_decision(
        ticket_fields=ExtractedTicketFields(
            title="Something broke",
            description="Not sure what department this belongs to.",
            category="Other",
        )
    )
    response = ask(
        "Not sure what department this belongs to.",
        decision=decision,
        classify_ticket=_raise,
    )
    assert response.ticket_draft.category == "Other"


def test_explicit_known_category_is_preserved_and_never_reclassified():
    existing = TicketDraft(
        description="VPN is down.", category="IT & Technology", title="VPN issue"
    )
    decision = _standard_decision(missing_fields=[])
    response = ask(
        "It started this morning.",
        decision=decision,
        active_intent=ChatIntent.SUPPORT_ISSUE,
        active_request_type=RequestType.STANDARD,
        draft=existing,
        # classify_ticket left as _no_classify_call default: raises if
        # invoked, proving a known non-"Other" category is never touched.
    )
    assert response.ticket_draft.category == "IT & Technology"


# ---------------------------------------------------------------------------
# General is never a department; drafting never invents facts
# ---------------------------------------------------------------------------


def test_general_never_appears_as_a_department():
    decision = _standard_decision(
        intent=ChatIntent.LEAVE_MANAGEMENT,
        request_type=RequestType.LEAVE_MANAGEMENT,
    )
    response = ask(
        "I need leave.", decision=decision, active_intent=ChatIntent.LEAVE_MANAGEMENT
    )
    assert response.ticket_draft.department != "General"


def test_ready_for_review_only_true_when_draft_is_complete():
    decision = _standard_decision(missing_fields=["more detail about what's going on"])
    decision.ticket_fields.description = None
    response = ask("I need help.", decision=decision)
    assert response.ready_for_review is False


def test_ready_for_review_true_when_draft_is_complete():
    response = ask("I need two monitors for my desk.", decision=_standard_decision())
    assert response.ready_for_review is True
    assert response.missing_fields == []


# ---------------------------------------------------------------------------
# No auto-submit (structural)
# ---------------------------------------------------------------------------


def test_chatbot_service_never_calls_ticket_creation():
    import inspect

    source = inspect.getsource(chatbot_service)
    for forbidden in ("create_ticket(", "handle_create_ticket(", "process_new_ticket("):
        assert forbidden not in source
