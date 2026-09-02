"""
Genie navigation destination coverage.

The live Svelte SPA (frontend/src/App.svelte + Sidebar.svelte) is the
source of truth for every activeTab identifier asserted here - see
tests/test_genie_live_navigation_wiring.py for the tests that check those
identifiers actually exist in the live frontend source, not just in this
file's assumptions. This file covers the backend side: that every semantic
NavigationTarget GPT can choose resolves deterministically to the exact
current activeTab string (never a legacy .html/portal path), that
role-gated destinations are denied - not silently redirected - for an
unauthorized role, and that ticket-draft/leave-draft handoff is unaffected
by any of this.
"""

from agents.chatbot_agent import (
    ChatActionType,
    ChatbotDecision,
    ExtractedTicketFields,
    NavigationTarget,
)
from agents.knowledge_agent import GroundedAnswer
from models.chatbot import ChatIntent, ChatRequest, ChatScope, RequestType
from services import chatbot_service
from services.knowledge_service import KnowledgeDocument


class FakeAIService:
    """Keyed by response_model, like tests/test_chatbot.py's FakeAIService,
    so a single fake can answer both the ChatbotDecision call and (for
    knowledge turns) the follow-up GroundedAnswer call."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.responses[response_model]


class FakeRetriever:
    def __init__(self, documents=None):
        self.documents = documents or []

    def search(self, query, allowed_scopes):
        return [doc for doc in self.documents if doc.scope in allowed_scopes]


def _no_ticket_found(ticket_id):
    return None


def ask(
    message, *, decision, role="Employee", ai_service=None, retriever=None, **kwargs
):
    request = ChatRequest(message=message, role=role, **kwargs)
    service = ai_service or FakeAIService({ChatbotDecision: decision})
    return chatbot_service.handle_message(
        request,
        ai_service=service,
        retriever=retriever or FakeRetriever(),
        ticket_lookup=_no_ticket_found,
    )


def _nav_decision(target: NavigationTarget) -> ChatbotDecision:
    return ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.NAVIGATION,
        action=ChatActionType.NAVIGATE,
        message="On it.",
        navigation_target=target,
    )


# Every destination, and the role that's guaranteed to reach it (mirrors
# frontend/src/components/Sidebar.svelte's own gating).
DESTINATIONS = [
    (NavigationTarget.DASHBOARD, "Employee", "dashboard"),
    (NavigationTarget.CREATE_TICKET, "Employee", "create-ticket"),
    (NavigationTarget.MY_TICKETS, "Employee", "dashboard"),
    (NavigationTarget.MY_TICKETS, "Department Admin", "inbox"),
    (NavigationTarget.KNOWLEDGE_BASE, "Ticketer", "knowledge"),
    (NavigationTarget.NOTIFICATIONS, "Employee", "notifications"),
    (NavigationTarget.ANNOUNCEMENTS, "Employee", "announcements"),
    (NavigationTarget.PROFILE, "Employee", "profile"),
    (NavigationTarget.SETTINGS, "Admin", "settings"),
    (NavigationTarget.ANALYTICS, "Admin", "analytics"),
    (NavigationTarget.ONBOARDING, "Admin", "onboarding"),
]


def test_every_destination_resolves_to_the_exact_live_activetab():
    for target, role, expected_tab in DESTINATIONS:
        response = ask("take me there", decision=_nav_decision(target), role=role)
        assert response.intent == "navigation"
        assert response.action is not None, f"{target}/{role} produced no action"
        assert response.action.type == "navigate"
        assert response.action.target == expected_tab, (
            f"{target} for role={role!r} resolved to "
            f"{response.action.target!r}, expected {expected_tab!r}"
        )


def test_no_navigation_target_ever_leaks_a_stale_legacy_path():
    for target, role, _ in DESTINATIONS:
        response = ask("take me there", decision=_nav_decision(target), role=role)
        target_value = response.action.target if response.action else ""
        assert ".html" not in target_value
        assert "employee_NM" not in target_value
        assert "management/" not in target_value
        assert "admin_AV" not in target_value
        assert "pages/" not in target_value


# --- RBAC: an unauthorized role gets a safe denial, never a forced view ---


UNAUTHORIZED_TARGETS = [
    NavigationTarget.KNOWLEDGE_BASE,
    NavigationTarget.SETTINGS,
    NavigationTarget.ANALYTICS,
    NavigationTarget.ONBOARDING,
]


def test_plain_employee_is_denied_gated_destinations_not_redirected():
    for target in UNAUTHORIZED_TARGETS:
        response = ask("take me there", decision=_nav_decision(target), role="Employee")
        assert response.action is None, f"{target} should not navigate for Employee"
        assert "role" in response.message.lower()


# --- ready_for_review / leave handoff is unaffected by navigation changes ---


def test_ready_for_review_never_carries_a_navigate_action():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.SUPPORT_ISSUE,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your draft.",
        request_type=RequestType.STANDARD,
        ticket_fields=ExtractedTicketFields(
            title="VPN broken",
            description="My VPN keeps disconnecting every few minutes.",
            category="IT & Technology",
        ),
    )
    response = ask(
        "My VPN keeps dropping.",
        decision=decision,
        active_intent=ChatIntent.SUPPORT_ISSUE,
    )
    assert response.ready_for_review is True
    assert response.action is None
    assert response.ticket_draft is not None
    assert response.ticket_draft.title == "VPN broken"


def test_leave_drafting_preserves_dates_and_never_forces_navigation():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.LEAVE_MANAGEMENT,
        action=ChatActionType.SHOW_TICKET_DRAFT,
        message="Here's your leave request.",
        request_type=RequestType.LEAVE_MANAGEMENT,
        ticket_fields=ExtractedTicketFields(
            description="Requesting PTO from August 24 to August 28.",
            category="Paid Time Off (PTO)",
            start_date="2026-08-24",
            end_date="2026-08-28",
        ),
    )
    response = ask(
        "I need PTO from August 24 to August 28.",
        decision=decision,
        active_intent=ChatIntent.LEAVE_MANAGEMENT,
    )
    assert response.ready_for_review is True
    assert response.action is None
    assert response.ticket_draft.startDate == "2026-08-24"
    assert response.ticket_draft.endDate == "2026-08-28"
    assert response.request_type == RequestType.LEAVE_MANAGEMENT


def test_knowledge_answer_never_sets_a_navigation_action_by_itself():
    # A verified knowledge answer should not incidentally switch the view -
    # action is only ever the "browse knowledge base" fallback, and only
    # when the answer could NOT be verified.
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.KNOWLEDGE,
        action=ChatActionType.SEARCH_KNOWLEDGE,
        message="What is the PTO accrual policy?",
        knowledge_query="PTO accrual policy",
    )
    doc = KnowledgeDocument(
        id="doc-1",
        content="Employees accrue 1.5 PTO days per month.",
        scope="General",
        source="kb",
    )
    ai_service = FakeAIService(
        {
            ChatbotDecision: decision,
            GroundedAnswer: GroundedAnswer(
                answer="You accrue 1.5 PTO days per month.", verified=True
            ),
        }
    )
    response = ask(
        "What is the PTO accrual policy?",
        decision=decision,
        ai_service=ai_service,
        retriever=FakeRetriever(documents=[doc]),
    )

    assert response.intent == "knowledge"
    assert response.action is None


def test_out_of_scope_guardrail_never_navigates():
    decision = ChatbotDecision(
        scope=ChatScope.OUT_OF_SCOPE,
        intent=ChatIntent.GENERAL,
        action=ChatActionType.RESPOND,
        message="Sure, here's a recipe...",
    )
    response = ask("Give me a biryani recipe.", decision=decision)
    assert response.action is None
    assert "workplace" in response.message.lower()
