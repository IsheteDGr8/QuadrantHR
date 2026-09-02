"""
Genie AI full-page chat - conversation persistence & cross-user isolation.

These tests hit the real HTTP route (POST /api/chatbot/message and the new
GET /api/chatbot/conversations[/{id}]) via TestClient, with two distinct mock
Azure JWTs (User A / User B) built the same unsigned-token way
tests/test_chatbot.py does. services.ai_service.ai_service.generate is
monkeypatched so no live GPT call is made - handle_message() itself is
exercised exactly as it runs in production, only the AI boundary is faked.
"""

import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

from agents.chatbot_agent import ChatActionType, ChatbotDecision
from backend.main import app
from models.chatbot import ChatIntent, ChatScope
from services import ai_service as ai_service_module


def _mock_bearer_token(
    *, oid: str, email: str, name: str, role: str = "Employee"
) -> str:
    def b64(payload: dict) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        )

    header = b64({"alg": "RS256", "typ": "JWT"})
    body = b64(
        {
            "oid": oid,
            "email": email,
            "name": name,
            "role": role,
            "exp": int(time.time()) + 3600,
        }
    )
    return f"{header}.{body}.mock"


USER_A_TOKEN = _mock_bearer_token(
    oid="11111111-aaaa-4aaa-8aaa-111111111111",
    email="usera-conv-test@company.com",
    name="User A",
)
USER_B_TOKEN = _mock_bearer_token(
    oid="22222222-bbbb-4bbb-8bbb-222222222222",
    email="userb-conv-test@company.com",
    name="User B",
)


def _client_for(token: str) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    """No live GPT calls - canned GENERAL/workplace decision for every turn."""

    def fake_generate(*, system_prompt, user_content, response_model):
        assert response_model is ChatbotDecision
        return ChatbotDecision(
            scope=ChatScope.WORKPLACE,
            intent=ChatIntent.GENERAL,
            action=ChatActionType.RESPOND,
            message="Sure, happy to help with that.",
        )

    monkeypatch.setattr(ai_service_module.ai_service, "generate", fake_generate)


@pytest.fixture(autouse=True)
def _cleanup_chat_tables():
    from database.connection import SessionLocal
    from database.models_db import ChatConversationDB, ChatMessageDB

    with SessionLocal() as db:
        initial_conv_ids = {c.id for c in db.query(ChatConversationDB.id).all()}
        initial_msg_ids = {m.id for m in db.query(ChatMessageDB.id).all()}

    yield

    with SessionLocal() as db:
        for msg in db.query(ChatMessageDB).all():
            if msg.id not in initial_msg_ids:
                db.delete(msg)
        for conv in db.query(ChatConversationDB).all():
            if conv.id not in initial_conv_ids:
                db.delete(conv)
        db.commit()


def test_first_message_creates_and_returns_conversation_id():
    client = _client_for(USER_A_TOKEN)
    resp = client.post(
        "/api/chatbot/message", json={"message": "How do I set up my VPN?"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"]


def test_second_message_with_conversation_id_appends_not_creates_new():
    client = _client_for(USER_A_TOKEN)
    first = client.post(
        "/api/chatbot/message", json={"message": "First message"}
    ).json()
    conv_id = first["conversation_id"]

    second = client.post(
        "/api/chatbot/message",
        json={"message": "Second message", "conversation_id": conv_id},
    ).json()
    assert second["conversation_id"] == conv_id

    detail = client.get(f"/api/chatbot/conversations/{conv_id}").json()
    assert len(detail["messages"]) == 4  # 2 user + 2 assistant turns
    assert [m["content"] for m in detail["messages"] if m["role"] == "user"] == [
        "First message",
        "Second message",
    ]


def test_empty_message_does_not_create_a_junk_conversation():
    client = _client_for(USER_A_TOKEN)
    resp = client.post("/api/chatbot/message", json={"message": ""})
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] is None
    assert client.get("/api/chatbot/conversations").json() == []


def test_list_conversations_most_recent_first_for_current_user():
    client = _client_for(USER_A_TOKEN)
    client.post("/api/chatbot/message", json={"message": "Older conversation"})
    client.post("/api/chatbot/message", json={"message": "Newer conversation"})

    listing = client.get("/api/chatbot/conversations").json()
    assert len(listing) == 2
    assert listing[0]["title"].startswith("Newer conversation")
    assert listing[1]["title"].startswith("Older conversation")


def test_user_b_cannot_see_user_a_conversation_in_list():
    client_a = _client_for(USER_A_TOKEN)
    client_b = _client_for(USER_B_TOKEN)

    client_a.post("/api/chatbot/message", json={"message": "User A's private message"})

    listing_b = client_b.get("/api/chatbot/conversations").json()
    assert listing_b == []


def test_user_b_cannot_fetch_user_a_conversation_by_id():
    client_a = _client_for(USER_A_TOKEN)
    client_b = _client_for(USER_B_TOKEN)

    conv_id = client_a.post(
        "/api/chatbot/message", json={"message": "User A's secret ticket issue"}
    ).json()["conversation_id"]

    resp = client_b.get(f"/api/chatbot/conversations/{conv_id}")
    assert resp.status_code == 404
    assert "secret" not in resp.text


def test_user_b_cannot_post_into_user_as_conversation():
    client_a = _client_for(USER_A_TOKEN)
    client_b = _client_for(USER_B_TOKEN)

    conv_id = client_a.post(
        "/api/chatbot/message", json={"message": "User A starts a chat"}
    ).json()["conversation_id"]

    resp = client_b.post(
        "/api/chatbot/message",
        json={"message": "User B trying to hijack", "conversation_id": conv_id},
    )
    assert resp.status_code == 404

    detail_a = client_a.get(f"/api/chatbot/conversations/{conv_id}").json()
    assert all("hijack" not in m["content"] for m in detail_a["messages"])


def test_unknown_conversation_id_returns_404_not_500():
    client = _client_for(USER_A_TOKEN)
    resp = client.get("/api/chatbot/conversations/does-not-exist")
    assert resp.status_code == 404

    resp2 = client.post(
        "/api/chatbot/message",
        json={"message": "hi", "conversation_id": "does-not-exist"},
    )
    assert resp2.status_code == 404


def test_owner_can_export_conversation_as_pdf():
    client = _client_for(USER_A_TOKEN)
    conv_id = client.post(
        "/api/chatbot/message", json={"message": "Please help with my VPN"}
    ).json()["conversation_id"]

    resp = client.get(f"/api/chatbot/conversations/{conv_id}/export")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")


def test_other_user_cannot_export_conversation_pdf():
    client_a = _client_for(USER_A_TOKEN)
    client_b = _client_for(USER_B_TOKEN)
    conv_id = client_a.post(
        "/api/chatbot/message", json={"message": "Private VPN conversation"}
    ).json()["conversation_id"]

    resp = client_b.get(f"/api/chatbot/conversations/{conv_id}/export")

    assert resp.status_code == 404
    assert "Private VPN conversation" not in resp.text


def test_natural_language_pdf_request_returns_download_action_without_ai_call(
    monkeypatch,
):
    client = _client_for(USER_A_TOKEN)
    conv_id = client.post(
        "/api/chatbot/message", json={"message": "Start a saved conversation"}
    ).json()["conversation_id"]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Explicit PDF export requests must not call GPT")

    monkeypatch.setattr(ai_service_module.ai_service, "generate", fail_if_called)
    resp = client.post(
        "/api/chatbot/message",
        json={
            "message": "Generate a PDF of this conversation",
            "conversation_id": conv_id,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == conv_id
    assert body["action"]["type"] == "export_conversation_pdf"
    assert "PDF" in body["message"]


def test_pdf_request_without_saved_conversation_does_not_offer_download_action():
    client = _client_for(USER_A_TOKEN)
    resp = client.post(
        "/api/chatbot/message",
        json={"message": "Download this conversation as a PDF"},
    )

    assert resp.status_code == 200
    assert resp.json()["action"] is None
    assert resp.json()["conversation_id"] is None
    assert "no saved conversation" in resp.json()["message"].lower()


def test_title_derivation_truncates_long_first_message():
    from services.conversation_service import derive_title

    long_message = "I need help resetting my corporate VPN client credentials please"
    title = derive_title(long_message)
    assert title != long_message
    assert title.endswith("…")


def test_title_derivation_fallback_for_empty_message():
    from services.conversation_service import derive_title

    assert derive_title("   ") == "New conversation"
