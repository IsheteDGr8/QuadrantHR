"""Regression coverage for GitHub issues #120-#132 (#122 is a PR)."""

from pathlib import Path

from agents.chatbot_agent import (
    ChatActionType,
    ChatbotDecision,
    ExtractedOnboardingFields,
)
from models.chatbot import ChatIntent, ChatRequest, ChatScope
from services.chatbot_service import _handle_onboarding_drafting

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = (ROOT / "frontend/src/components/Sidebar.svelte").read_text()
TICKET_STORE = (ROOT / "frontend/src/lib/stores/tickets.js").read_text()
WIDGET = (ROOT / "frontend/src/components/GenieAgentWidget.svelte").read_text()
ONBOARDING_VIEW = (ROOT / "frontend/src/views/OnboardingView.svelte").read_text()
ONBOARDING_SERVICE = (ROOT / "backend/services/onboarding_service.py").read_text()
CREATE_VIEW = (ROOT / "frontend/src/views/CreateTicketView.svelte").read_text()


def test_120_121_automatic_ai_telemetry_and_admin_dashboard_remain_integrated():
    telemetry = (ROOT / "backend/services/ai_service.py").read_text()
    analytics = (ROOT / "frontend/src/views/GeneralAnalyticsView.svelte").read_text()
    assert "_record_structured_usage" in telemetry
    assert "apiFetchAIUsage" in analytics
    assert "AI Feature Toggles" in analytics


def test_123_auto_department_does_not_override_ai_routing():
    assert "let departmentSelect = 'Auto'" in CREATE_VIEW
    assert "let backendDept = null" in CREATE_VIEW
    assert "department_override: backendDept" in CREATE_VIEW


def test_124_announcement_genie_check_remains_integrated_with_new_requests():
    assert "apiCheckAnnouncementMatch" in CREATE_VIEW
    assert (
        "viewAnnouncement"
        in (ROOT / "frontend/src/components/CreateTicketModal.svelte").read_text()
    )


def test_125_onboarding_completion_is_explicit():
    service = (ROOT / "backend/services/onboarding_service.py").read_text()
    assert 'health = "Complete"' in service
    assert "All onboarding tickets are complete." in service
    assert "completed_tickets" in ONBOARDING_VIEW


def test_126_employee_navigation_keeps_my_tickets_and_policy_management_is_gated():
    my_tickets = SIDEBAR.index('title="My Tickets"')
    add_policies = SIDEBAR.index('title="Add Policies"')
    assert 'title="Knowledge Base"' not in SIDEBAR
    assert "showTicketerPolicies" in SIDEBAR[max(0, add_policies - 220) : add_policies]
    assert "Add Policies" not in SIDEBAR[max(0, my_tickets - 120) : my_tickets + 220]


def test_128_dashboard_navigation_is_available_to_employees():
    assert "on:click={() => setTab('dashboard')}" in SIDEBAR


def test_129_triage_search_includes_resolved_requester_fields():
    assert "t.requester_name.toLowerCase().includes" in TICKET_STORE
    assert "t.requester_id.toLowerCase().includes" in TICKET_STORE


def test_130_popup_scrolls_bound_message_container_after_updates():
    assert "bind:this={messagesContainer}" in WIDGET
    assert "messagesContainer.scrollHeight" in WIDGET
    assert "afterUpdate" in WIDGET


def test_131_complete_genie_onboarding_draft_navigates_to_prefilled_review():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.START_ONBOARDING,
        action=ChatActionType.RESPOND,
        message="Ready for review.",
        onboarding_fields=ExtractedOnboardingFields(
            employee_name="Gregory Jack",
            employee_email="gregjack@gmail.com",
            job_title="SWE II",
            employee_department="IT Team",
            location="Seattle",
            start_date="2026-08-21",
        ),
    )
    response = _handle_onboarding_drafting(
        ChatRequest(message="Onboard Gregory"), decision, {"role": "Admin"}
    )
    assert response.ready_for_review is True
    assert response.action.target == "onboarding"
    assert response.onboarding_draft.employee_name == "Gregory Jack"
    assert "onboardingDraftStore" in ONBOARDING_VIEW


def test_131_onboarding_does_not_require_entra_object_id():
    decision = ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=ChatIntent.START_ONBOARDING,
        action=ChatActionType.ASK_FOLLOWUP,
        message="What is their department?",
        onboarding_fields=ExtractedOnboardingFields(employee_name="Gregory Jack"),
    )
    response = _handle_onboarding_drafting(
        ChatRequest(message="Onboard Gregory"), decision, {"role": "Admin"}
    )
    assert all("object" not in field.lower() for field in response.missing_fields)


def test_132_linked_tickets_include_employee_context():
    for label in (
        "Name:",
        "Email:",
        "Job title:",
        "Department:",
        "Manager:",
        "Location:",
        "Start date:",
        "Onboarding case:",
    ):
        assert label in ONBOARDING_SERVICE
