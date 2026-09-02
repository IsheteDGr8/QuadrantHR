from pathlib import Path
from unittest.mock import patch

from models.chatbot import ChatIntent, ChatRequest
from services import announcement_action_service

ROOT = Path(__file__).resolve().parents[1]


def _admin():
    return {"role": "Admin", "name": "Alex Admin", "email": "alex@example.com"}


def _ticketer():
    return {
        "role": "Ticketer",
        "name": "Taylor Ticketer",
        "email": "taylor@example.com",
    }


def test_genie_announcement_creation_requires_confirmation():
    first = announcement_action_service.handle_turn(
        ChatRequest(message="create announcement titled Office closure"),
        ChatIntent.CREATE_ANNOUNCEMENT,
        _admin(),
    )
    assert first.pending_action.awaiting == "announcement_content"

    second = announcement_action_service.handle_turn(
        ChatRequest(
            message="The office is closed Friday", pending_action=first.pending_action
        ),
        ChatIntent.CREATE_ANNOUNCEMENT,
        _admin(),
    )
    assert second.pending_action.awaiting == "announcement_confirmation"

    with patch.object(
        announcement_action_service,
        "create_announcement",
        return_value={"title": "Office closure"},
    ) as create:
        done = announcement_action_service.handle_turn(
            ChatRequest(message="yes", pending_action=second.pending_action),
            ChatIntent.CREATE_ANNOUNCEMENT,
            _admin(),
        )
    assert "Published" in done.message
    create.assert_called_once()


def test_genie_announcement_delete_requires_confirmation():
    existing = [{"id": "anc-1", "title": "Office closure"}]
    with patch.object(
        announcement_action_service, "get_announcements", return_value=existing
    ):
        first = announcement_action_service.handle_turn(
            ChatRequest(message="delete announcement Office closure"),
            ChatIntent.DELETE_ANNOUNCEMENT,
            _admin(),
        )
    assert first.pending_action.awaiting == "announcement_confirmation"

    with patch.object(
        announcement_action_service, "delete_announcement", return_value=True
    ) as delete:
        done = announcement_action_service.handle_turn(
            ChatRequest(message="yes", pending_action=first.pending_action),
            ChatIntent.DELETE_ANNOUNCEMENT,
            _admin(),
        )
    assert "Deleted" in done.message
    delete.assert_called_once_with("anc-1")


def test_employee_cannot_mutate_announcements_with_genie():
    response = announcement_action_service.handle_turn(
        ChatRequest(message="delete announcement Office closure"),
        ChatIntent.DELETE_ANNOUNCEMENT,
        {"role": "Employee"},
    )
    assert "only authorized Ticketers and Admins" in response.message
    assert response.pending_action is None


def test_ticketer_can_manage_announcements_with_genie():
    response = announcement_action_service.handle_turn(
        ChatRequest(message="create announcement titled Network maintenance"),
        ChatIntent.CREATE_ANNOUNCEMENT,
        _ticketer(),
    )
    assert response.pending_action.awaiting == "announcement_content"


def test_employee_knowledge_navigation_is_removed_and_onboarding_is_highlighted():
    sidebar = (ROOT / "frontend/src/components/Sidebar.svelte").read_text(
        encoding="utf-8"
    )
    app = (ROOT / "frontend/src/App.svelte").read_text(encoding="utf-8")
    genie = (ROOT / "frontend/src/lib/stores/genieChat.js").read_text(encoding="utf-8")
    onboarding = (ROOT / "frontend/src/views/OnboardingView.svelte").read_text(
        encoding="utf-8"
    )
    announcements = (ROOT / "frontend/src/views/AnnouncementsView.svelte").read_text(
        encoding="utf-8"
    )

    assert 'title="Knowledge Base"' not in sidebar
    assert "{#if showTicketerPolicies}" in sidebar
    assert 'title="Add Policies"' in sidebar
    assert "$activeTab === 'knowledge' && !isTicketer($userStore)" in app
    assert "knowledge: isTicketer" in genie
    assert "class:resolved={item.health === 'Complete'}" in onboarding
    assert "✓ Resolved" in onboarding
    assert "apiDeleteAnnouncement" in announcements
