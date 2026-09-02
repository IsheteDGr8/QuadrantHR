"""
Workplace-only scope guardrail tests (see models.chatbot.ChatScope and
services.chatbot_service._out_of_scope_response).

Same convention as tests/test_chatbot.py: GPT's structured decision
(including the semantic `scope` classification) is supplied directly via
a FakeAIService rather than making a live call - what's under test is the
deterministic hard-early-exit enforcement built on top of that
classification, not GPT's semantic judgment itself.
"""

from agents.chatbot_agent import (
    ChatActionType,
    ChatbotDecision,
    ExtractedTicketFields,
)
from models.chatbot import (
    ChatIntent,
    ChatRequest,
    ChatScope,
    PendingManagementAction,
    TicketDraft,
)
from services import chatbot_service, management_action_service
from services.chatbot_service import GPT_UNAVAILABLE_MESSAGE, OUT_OF_SCOPE_MESSAGE
from services.knowledge_service import SearchUnavailableError


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.decision


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, allowed_scopes):
        self.calls.append((query, list(allowed_scopes)))
        raise SearchUnavailableError("must never be called for out-of-scope turns")


def _no_ticket_found(ticket_id):
    return None


def ask(message, *, decision, retriever=None, current_user=None, **kwargs):
    request = ChatRequest(message=message, **kwargs)
    ai_service = FakeAIService(decision)
    retriever = retriever or FakeRetriever()
    response = chatbot_service.handle_message(
        request,
        current_user=current_user,
        ai_service=ai_service,
        retriever=retriever,
        ticket_lookup=_no_ticket_found,
    )
    return response, ai_service, retriever


def _out_of_scope_decision(**overrides):
    fields = dict(
        scope=ChatScope.OUT_OF_SCOPE,
        intent=ChatIntent.GENERAL,
        action=ChatActionType.RESPOND,
        message="Sure! Here's a great recipe for chicken biryani...",
    )
    fields.update(overrides)
    return ChatbotDecision(**fields)


# 1. Biryani recipe: immediate workplace-only response, no draft mutation,
# no missing-field follow-up.
def test_biryani_recipe_is_blocked_immediately():
    decision = _out_of_scope_decision()
    response, _, _ = ask("Give me a biryani recipe.", decision=decision)
    assert response.message == OUT_OF_SCOPE_MESSAGE
    assert response.ticket_draft is None
    assert response.missing_fields == []
    assert response.ready_for_review is False


# 2. Movie recommendation: blocked immediately.
def test_movie_recommendation_is_blocked():
    decision = _out_of_scope_decision(
        message="Great picks depend on mood - action, comedy..."
    )
    response, _, _ = ask("What movie should I watch?", decision=decision)
    assert response.message == OUT_OF_SCOPE_MESSAGE


# 3 & 8. Voting question: blocked immediately.
def test_voting_question_is_blocked():
    decision = _out_of_scope_decision(message="That's a personal choice...")
    response, _, _ = ask("Who should I vote for?", decision=decision)
    assert response.message == OUT_OF_SCOPE_MESSAGE


# 4. Weather question unrelated to office operations: blocked immediately.
def test_weather_question_is_blocked():
    decision = _out_of_scope_decision(message="Tomorrow looks sunny...")
    response, _, _ = ask("What's tomorrow's weather?", decision=decision)
    assert response.message == OUT_OF_SCOPE_MESSAGE


# 10. Netflix recommendation: blocked (contrast with the allowed Netflix
# company-device question below).
def test_netflix_recommendation_is_blocked():
    decision = _out_of_scope_decision(message="You might enjoy...")
    response, _, _ = ask("Recommend me a Netflix show.", decision=decision)
    assert response.message == OUT_OF_SCOPE_MESSAGE


# 5. Genuine workplace issue proceeds through the normal ticket-drafting
# flow - the scope field defaults to workplace and never blocks it.
def test_vpn_issue_proceeds_through_normal_workplace_flow():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.ASK_FOLLOWUP,
        message="Could you tell me more about what's going on?",
        ticket_fields=ExtractedTicketFields(description="My VPN isn't working."),
        missing_fields=["more detail about what happened"],
    )
    response, _, _ = ask("My VPN isn't working.", decision=decision)
    assert response.message != OUT_OF_SCOPE_MESSAGE
    assert response.intent == "support_issue"
    assert response.ticket_draft is not None


# 6. Genuine workplace knowledge question reaches RAG normally.
def test_reimbursement_question_reaches_knowledge_flow():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.KNOWLEDGE,
        action=ChatActionType.SEARCH_KNOWLEDGE,
        message="Let me check.",
        knowledge_query="reimbursement process",
    )

    class _EmptyRetriever:
        def __init__(self):
            self.calls = []

        def search(self, query, allowed_scopes):
            self.calls.append((query, list(allowed_scopes)))
            return []

    retriever = _EmptyRetriever()
    response, _, retriever = ask(
        "How do reimbursements work?", decision=decision, retriever=retriever
    )
    assert response.intent == "knowledge"
    assert retriever.calls  # RAG was actually queried


# 7. Company policy question about a sensitive-sounding topic is workplace
# in scope because the subject is company policy.
def test_company_policy_on_political_discussions_is_allowed():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.KNOWLEDGE,
        action=ChatActionType.SEARCH_KNOWLEDGE,
        message="Let me check.",
        knowledge_query="policy on political discussions at work",
    )

    class _EmptyRetriever:
        def __init__(self):
            self.calls = []

        def search(self, query, allowed_scopes):
            self.calls.append((query, list(allowed_scopes)))
            return []

    retriever = _EmptyRetriever()
    response, _, retriever = ask(
        "What is the company's policy on political discussions at work?",
        decision=decision,
        retriever=retriever,
    )
    assert response.message != OUT_OF_SCOPE_MESSAGE
    assert retriever.calls


# 9. Company-device question is workplace, not blocked.
def test_netflix_on_company_laptop_is_allowed():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.KNOWLEDGE,
        action=ChatActionType.SEARCH_KNOWLEDGE,
        message="Let me check.",
        knowledge_query="personal streaming apps on company laptop policy",
    )

    class _EmptyRetriever:
        def __init__(self):
            self.calls = []

        def search(self, query, allowed_scopes):
            self.calls.append((query, list(allowed_scopes)))
            return []

    retriever = _EmptyRetriever()
    response, _, retriever = ask(
        "Can I watch Netflix on my company laptop?",
        decision=decision,
        retriever=retriever,
    )
    assert response.message != OUT_OF_SCOPE_MESSAGE
    assert retriever.calls


# 11. An in-progress ticket draft cannot be bypassed/polluted by an
# unrelated turn - the guardrail check runs regardless of active_intent,
# and the response never carries the unrelated message into the draft.
def test_unrelated_turn_does_not_pollute_existing_ticket_draft():
    existing_draft = TicketDraft(
        title="VPN connection issue",
        description="VPN keeps disconnecting during video calls.",
        category="IT & Technology",
    )
    decision = _out_of_scope_decision(message="Anything with rice works well...")
    response, ai_service, _ = ask(
        "What movie should I watch?",
        decision=decision,
        active_intent=ChatIntent.SUPPORT_ISSUE,
        draft=existing_draft,
    )
    assert response.message == OUT_OF_SCOPE_MESSAGE
    assert response.ticket_draft is None
    assert response.ready_for_review is False
    # GPT was still consulted (semantic classification, not a keyword
    # skip), but its answer to the unrelated question never surfaces.
    assert ai_service.calls
    assert "rice" not in response.message


# 12. Out-of-scope requests never reach knowledge/RAG retrieval, even if
# GPT's own intent field looked like a knowledge request.
def test_out_of_scope_never_calls_knowledge_retriever():
    decision = _out_of_scope_decision(
        intent=ChatIntent.KNOWLEDGE,
        action=ChatActionType.SEARCH_KNOWLEDGE,
        knowledge_query="Taylor Swift discography",
        message="Sure, here's her discography...",
    )
    retriever = FakeRetriever()
    response, _, retriever = ask(
        "Tell me about Taylor Swift.", decision=decision, retriever=retriever
    )
    assert response.message == OUT_OF_SCOPE_MESSAGE
    assert retriever.calls == []


# 13. Out-of-scope requests never reach management_action_service, even if
# GPT's own intent field looked like a management action.
def test_out_of_scope_never_calls_management_action_service(monkeypatch):
    called = []

    def _fail_if_called(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("management_action_service.handle_turn must not run")

    monkeypatch.setattr(management_action_service, "handle_turn", _fail_if_called)

    decision = _out_of_scope_decision(
        intent=ChatIntent.REASSIGN_TICKET,
        action=ChatActionType.MANAGEMENT_ACTION,
        message="Sure, I'll move that ticket...",
    )
    response, _, _ = ask(
        "Move HD-1023 to IT, also what movie should I watch?",
        decision=decision,
        current_user={"role": "Super Admin", "oid": "u1", "email": "a@co.com"},
    )
    assert response.message == OUT_OF_SCOPE_MESSAGE
    assert called == []


# 14. Out-of-scope requests never transition to ready_for_review / a
# ticket-form navigation action.
def test_out_of_scope_never_triggers_ready_for_review_or_form_navigation():
    decision = _out_of_scope_decision()
    response, _, _ = ask("Give me a biryani recipe.", decision=decision)
    assert response.ready_for_review is False
    assert response.ticket_draft is None
    assert response.action is None
    assert response.request_type is None


# 14b. Also verified with a pending management action in flight - an
# unrelated turn must not be treated as a confirmation/field answer that
# advances the pending action toward execution.
def test_out_of_scope_does_not_advance_pending_management_action():
    pending = PendingManagementAction(
        action_type=ChatIntent.REASSIGN_TICKET,
        awaiting="target_department",
        ticket_id="HD-1023",
    )
    decision = _out_of_scope_decision()
    response, _, _ = ask(
        "What movie should I watch?",
        decision=decision,
        pending_action=pending,
        current_user={"role": "Super Admin", "oid": "u1", "email": "a@co.com"},
    )
    assert response.message == OUT_OF_SCOPE_MESSAGE
    assert response.ready_for_review is False


# scope is a required structured-output field (no default) precisely so
# that a malformed/missing-scope GPT response cannot fail open into the
# normal pipeline. It must go through the EXISTING AI-failure handling -
# neither silently treated as workplace, nor converted into a fake
# out-of-scope refusal - and must not reach ticket drafting, RAG, or
# management-action dispatch on its way there.
def test_malformed_decision_missing_scope_uses_existing_ai_failure_handling(
    monkeypatch,
):
    class _MalformedScopeAIService:
        def generate(self, *, system_prompt, user_content, response_model):
            # Mirrors exactly what services.ai_service.AIServiceWrapper.
            # generate() does with a real malformed GPT payload: it calls
            # response_model.model_validate(data), which now raises
            # because `scope` (required, no default) is absent - the same
            # pydantic ValidationError a real missing-field response would
            # produce, not a hand-rolled substitute exception.
            payload = {
                "intent": "support_issue",
                "action": "show_ticket_draft",
                "message": "Here's your draft.",
                "ticket_fields": {"description": "My VPN isn't working."},
                "missing_fields": [],
            }
            return response_model.model_validate(payload)

    management_calls = []

    def _fail_if_called(*args, **kwargs):
        management_calls.append((args, kwargs))
        raise AssertionError("management_action_service.handle_turn must not run")

    monkeypatch.setattr(management_action_service, "handle_turn", _fail_if_called)

    retriever = FakeRetriever()
    request = ChatRequest(message="My VPN isn't working.")
    response = chatbot_service.handle_message(
        request,
        ai_service=_MalformedScopeAIService(),
        retriever=retriever,
        ticket_lookup=_no_ticket_found,
    )

    # Existing AI-failure handling, not a fabricated policy refusal.
    assert response.message == GPT_UNAVAILABLE_MESSAGE
    assert response.message != OUT_OF_SCOPE_MESSAGE
    assert response.intent == "general"

    # Never fell through into ticket drafting, RAG, or management actions.
    assert response.ticket_draft is None
    assert response.ready_for_review is False
    assert retriever.calls == []
    assert management_calls == []


# 15. Employee, Department Admin, and Super Admin all get the same
# workplace-only guardrail - being Admin/Super Admin is not an exemption.
def test_guardrail_applies_equally_to_every_role():
    for role in ("Employee", "Department Admin", "Super Admin"):
        decision = _out_of_scope_decision()
        response, _, _ = ask(
            "Give me a biryani recipe.",
            decision=decision,
            current_user={"role": role, "oid": "u1", "email": "a@co.com"},
        )
        assert response.message == OUT_OF_SCOPE_MESSAGE, f"role={role}"
