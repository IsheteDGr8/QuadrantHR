"""
Chatbot AI-failure handling + shared-service migration tests.

History: services/ai_service.py's AIServiceWrapper.generate() used to
silently swallow every failure (missing config, a connection error, or a
mock-mode response_model that can't be default-constructed) and return
None instead of raising, which crashed chatbot_service.handle_message()
with an unhandled AttributeError -> 500. That was fixed once already, but
a later `dev` merge reverted both the safe-failure handling AND (as we
since learned from Saketh) generate() was never on the same Azure/OpenAI
path as the working category/priority/routing agents in the first place:
it opened its own AzureOpenAI SDK client against AZURE_OPENAI_ENDPOINT /
AZURE_OPENAI_API_KEY / AZURE_OPENAI_API_VERSION, which are placeholders
in this deployment, while agents/orchestrator.py's classification agents
go through ai_service.generate_structured(), which prefers the shared
GROUP1OPENAIENDPOINT / GROUP1OPENAIAPIKEY configuration.

This file covers both halves of the (now re-applied) fix:
- ai_service.AIServiceWrapper.generate() now always either returns a
  valid response_model instance or raises AIServiceError - never None -
  and does so by calling generate_structured() (the same shared path),
  never by opening a second AzureOpenAI client.
- chatbot_service.handle_message() never dereferences a None/missing
  decision, and returns a safe, fixed ChatResponse for any AI failure,
  without ever creating or submitting a ticket.
"""

from __future__ import annotations

import inspect
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.main import app
from models.chatbot import ChatRequest
from services import ai_service as ai_service_module
from services import chatbot_service
from services.ai_service import (
    AIServiceError,
    AIServiceWrapper,
    _pydantic_to_strict_schema,
)

client = TestClient(app)
client.headers["Authorization"] = (
    "Bearer eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCJ9.eyJvaWQiOiAiZGMzYjU2ZTktOTI4MC00MGRjLThkNzMtOThiZmQ4MWZkZDZhIiwgImVtYWlsIjogIkFkbWluMUB2aWduZXNocXVhZHJhbnRvdXRsb29rLm9ubWljcm9zb2Z0LmNvbSIsICJuYW1lIjogIkFkbWluIFVzZXIiLCAicm9sZSI6ICJTdXBlciBBZG1pbiIsICJleHAiOiAyNTM0MDIzMDA3OTl9.mock"
)


class _RequiredFieldModel(BaseModel):
    # Mirrors the shape of every real response_model this wrapper is
    # actually used with (ChatbotDecision, GroundedAnswer, ...): at least
    # one required field with no default, so a bare `_RequiredFieldModel()`
    # cannot be constructed.
    value: str


class _FakeHTTPResponse:
    def __init__(self, payload: dict, status_ok: bool = True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            import requests

            raise requests.HTTPError("boom")

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# services/ai_service.py: generate() must never return None
# ---------------------------------------------------------------------------


def test_mock_mode_raises_instead_of_returning_none_for_required_fields(
    monkeypatch,
):
    monkeypatch.setenv("USE_MOCK_AI", "true")
    wrapper = AIServiceWrapper()
    with pytest.raises(AIServiceError):
        wrapper.generate(
            system_prompt="x", user_content="y", response_model=_RequiredFieldModel
        )


def test_missing_azure_config_raises_instead_of_returning_none(monkeypatch):
    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.delenv("GROUP1OPENAIENDPOINT", raising=False)
    monkeypatch.delenv("GROUP1OPENAIAPIKEY", raising=False)
    wrapper = AIServiceWrapper()
    with pytest.raises(AIServiceError):
        wrapper.generate(
            system_prompt="x", user_content="y", response_model=_RequiredFieldModel
        )


def test_connection_error_raises_ai_service_error(monkeypatch):
    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.setenv("GROUP1OPENAIENDPOINT", "https://group-1.example/v1/responses")
    monkeypatch.setenv("GROUP1OPENAIAPIKEY", "fake-key")

    def _boom(*args, **kwargs):
        import requests

        raise requests.ConnectionError("Connection error.")

    monkeypatch.setattr(ai_service_module.requests, "post", _boom)

    wrapper = AIServiceWrapper()
    with pytest.raises(AIServiceError):
        wrapper.generate(
            system_prompt="x", user_content="y", response_model=_RequiredFieldModel
        )


# ---------------------------------------------------------------------------
# generate() must go through the SHARED generate_structured() path, not a
# second AzureOpenAI SDK client on the legacy/placeholder env vars.
# ---------------------------------------------------------------------------


def test_generate_does_not_construct_an_azure_openai_client():
    source = inspect.getsource(AIServiceWrapper.generate)
    assert "AzureOpenAI" not in source


def test_generate_prefers_shared_group1_endpoint_over_legacy_placeholder(
    monkeypatch,
):
    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.setenv("GROUP1OPENAIENDPOINT", "https://group-1.example/v1/responses")
    monkeypatch.setenv("GROUP1OPENAIAPIKEY", "real-shared-key")
    # Deliberately placeholder-looking legacy values, exactly like the
    # reported Docker environment - these must NOT be what gets called.
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "placeholder")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "placeholder")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "placeholder")

    calls = []

    def _fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "body": json})
        return _FakeHTTPResponse({"output_text": '{"value": "ok"}'})

    monkeypatch.setattr(ai_service_module.requests, "post", _fake_post)

    result = AIServiceWrapper().generate(
        system_prompt="x", user_content="y", response_model=_RequiredFieldModel
    )
    assert result.value == "ok"
    assert len(calls) == 1
    assert calls[0]["url"] == "https://group-1.example/v1/responses"
    assert calls[0]["headers"]["api-key"] == "real-shared-key"


def test_chatbot_decision_round_trips_through_the_shared_strict_schema_path(
    monkeypatch,
):
    """
    ChatbotDecision is a realistically complex model (nested Optional
    sub-model, enums, a list) - this proves the strict-JSON-schema
    conversion isn't just working for a trivial model.
    """
    from agents.chatbot_agent import ChatbotDecision

    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.setenv("GROUP1OPENAIENDPOINT", "https://group-1.example/v1/responses")
    monkeypatch.setenv("GROUP1OPENAIAPIKEY", "real-shared-key")

    decision_payload = {
        "scope": "workplace",
        "intent": "support_issue",
        "action": "show_ticket_draft",
        "message": "Here's your draft.",
        "navigation_target": None,
        "knowledge_query": None,
        "ticket_fields": {
            "title": "Need two monitors",
            "description": "I need two monitors for my desk.",
            "category": "IT & Technology",
            "preferred_date": None,
            "ticket_id": None,
        },
        "missing_fields": [],
        "request_type": "standard",
    }

    def _fake_post(url, headers=None, json=None, timeout=None):
        return _FakeHTTPResponse(
            {"output_text": __import__("json").dumps(decision_payload)}
        )

    monkeypatch.setattr(ai_service_module.requests, "post", _fake_post)

    result = AIServiceWrapper().generate(
        system_prompt="x", user_content="y", response_model=ChatbotDecision
    )
    assert isinstance(result, ChatbotDecision)
    assert result.intent == "support_issue"
    assert result.request_type == "standard"
    assert result.ticket_fields.title == "Need two monitors"


def test_strict_schema_never_puts_a_sibling_keyword_next_to_a_ref():
    """
    Regression guard: Azure/OpenAI's strict json_schema mode rejects any
    property whose schema is a "$ref" with a sibling keyword (e.g.
    "description") - live error: "$ref cannot have keywords
    {'description'}". Pydantic emits a bare "$ref" for an enum-typed
    field (see ChatIntent/RequestType/etc. above), but adding
    Field(description=...) to an enum-typed field makes Pydantic attach
    that description alongside the "$ref" instead, which is invalid under
    strict mode and made EVERY chatbot turn fail with a 400 - not just
    scope-related ones - until models.chatbot.ChatbotDecision.scope was
    fixed to a bare annotation. This walks the real schema every chatbot
    request sends and fails if any $defs-based ("$ref") property ever
    regresses to carrying a sibling keyword again, for any field.
    """

    from agents.chatbot_agent import ChatbotDecision

    def _check(node, path):
        if isinstance(node, dict):
            if "$ref" in node and len(node) > 1:
                extra = set(node) - {"$ref"}
                raise AssertionError(
                    f"{path}: $ref has forbidden sibling keyword(s) {extra}"
                )
            for key, value in node.items():
                _check(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _check(item, f"{path}[{i}]")

    schema = _pydantic_to_strict_schema(ChatbotDecision)
    _check(schema, "schema")


def test_grounded_answer_round_trips_through_the_shared_strict_schema_path(
    monkeypatch,
):
    from agents.knowledge_agent import GroundedAnswer

    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.setenv("GROUP1OPENAIENDPOINT", "https://group-1.example/v1/responses")
    monkeypatch.setenv("GROUP1OPENAIAPIKEY", "real-shared-key")

    payload = {"answer": "Reimbursements take 5-7 business days.", "verified": True}
    output_text = json.dumps(payload)

    def _fake_post(url, headers=None, json=None, timeout=None):
        return _FakeHTTPResponse({"output_text": output_text})

    monkeypatch.setattr(ai_service_module.requests, "post", _fake_post)

    result = AIServiceWrapper().generate(
        system_prompt="x", user_content="y", response_model=GroundedAnswer
    )
    assert isinstance(result, GroundedAnswer)
    assert result.verified is True


# ---------------------------------------------------------------------------
# services/chatbot_service.py: handle_message() must never crash on a
# missing/None decision, and must never fabricate content on AI failure.
# ---------------------------------------------------------------------------


class _NoneReturningAIService:
    """Simulates a decision that never materialized without raising -
    i.e. a violation of ai_service's contract - to prove the defensive
    `decision is None` guard in handle_message() actually holds even if
    that contract is ever broken again."""

    def generate(self, *, system_prompt, user_content, response_model):
        return None


class _ConnectionErrorAIService:
    def generate(self, *, system_prompt, user_content, response_model):
        raise AIServiceError("Could not connect to the Azure OpenAI endpoint.")


def _assert_safe_fallback(response):
    assert response.message == chatbot_service.GPT_UNAVAILABLE_MESSAGE
    assert response.intent == "general"
    assert response.request_type is None
    assert response.ticket_draft is None
    assert response.missing_fields == []
    assert response.ready_for_review is False
    assert response.action is None
    assert response.knowledge_verified is None


def test_gpt_decision_none_returns_safe_fallback_not_crash():
    request = ChatRequest(message="I need two monitors for my desk.")
    response = chatbot_service.handle_message(
        request, ai_service=_NoneReturningAIService()
    )
    _assert_safe_fallback(response)


def test_ai_service_connection_error_returns_safe_fallback():
    request = ChatRequest(message="I need medical leave from August 20 to August 28.")
    response = chatbot_service.handle_message(
        request, ai_service=_ConnectionErrorAIService()
    )
    _assert_safe_fallback(response)


def test_ai_failure_never_produces_a_ticket_draft_for_any_intent():
    for message in (
        "I need two monitors for my desk.",
        "I want to report something anonymously.",
        "I need PTO next week.",
    ):
        response = chatbot_service.handle_message(
            ChatRequest(message=message), ai_service=_ConnectionErrorAIService()
        )
        assert response.ticket_draft is None
        assert response.ready_for_review is False


def test_ai_failure_path_never_calls_ticket_creation():
    source = inspect.getsource(chatbot_service._gpt_unavailable_response)
    assert "create_ticket(" not in source
    assert "process_new_ticket(" not in source


def test_chatbot_endpoint_returns_200_not_500_on_ai_failure(monkeypatch):
    monkeypatch.delenv("USE_MOCK_AI", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROUP1OPENAIENDPOINT", raising=False)
    monkeypatch.delenv("GROUP1OPENAIAPIKEY", raising=False)

    response = client.post(
        "/api/chatbot/message",
        json={"message": "My VPN has been broken since this morning."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == chatbot_service.GPT_UNAVAILABLE_MESSAGE
    assert body["ticket_draft"] is None
    assert body["ready_for_review"] is False


# ---------------------------------------------------------------------------
# Existing successful behavior is unaffected by the fix
# ---------------------------------------------------------------------------


def test_successful_decision_still_works_normally():
    from agents.chatbot_agent import (
        ChatActionType,
        ChatbotDecision,
        ExtractedTicketFields,
    )
    from models.chatbot import ChatIntent, ChatScope, RequestType

    class _FakeAIService:
        def generate(self, *, system_prompt, user_content, response_model):
            return ChatbotDecision(
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

    response = chatbot_service.handle_message(
        ChatRequest(message="I need two monitors for my desk."),
        ai_service=_FakeAIService(),
    )
    assert response.ready_for_review is True
    assert response.ticket_draft.title == "Need two monitors"
