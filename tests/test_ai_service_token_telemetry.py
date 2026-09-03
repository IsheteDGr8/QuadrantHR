"""Regression coverage for structured Azure OpenAI token telemetry."""

from types import SimpleNamespace
from unittest.mock import Mock

from services import ai_service


def test_generate_structured_records_responses_api_token_usage(monkeypatch):
    monkeypatch.setenv(
        "GROUP1OPENAIENDPOINT", "https://example.test/openai/v1/responses"
    )
    monkeypatch.setenv("GROUP1OPENAIAPIKEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-deployment")

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "output_text": '{"result":"ok"}',
        "usage": {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168},
    }
    monkeypatch.setattr(ai_service.requests, "post", Mock(return_value=response))

    record_metrics = Mock()
    monkeypatch.setattr("telemetry.record_llm_metrics", record_metrics)

    result = ai_service.generate_structured(
        prompt="Classify this request",
        schema={"type": "object"},
        name="ChatbotDecision",
    )

    assert result == {"result": "ok"}
    record_metrics.assert_called_once_with(
        prompt_tokens=123,
        completion_tokens=45,
        model="test-deployment",
        agent_name="structured_ChatbotDecision",
        cached_tokens=0,
    )


def test_structured_usage_supports_chat_completions_field_names(monkeypatch):
    record_metrics = Mock()
    monkeypatch.setattr("telemetry.record_llm_metrics", record_metrics)

    ai_service._record_structured_usage(
        SimpleNamespace(prompt_tokens=80, completion_tokens=20),
        model="fallback-deployment",
        agent_name="structured_KnowledgeDecision",
    )

    record_metrics.assert_called_once_with(
        prompt_tokens=80,
        completion_tokens=20,
        model="fallback-deployment",
        agent_name="structured_KnowledgeDecision",
        cached_tokens=0,
    )


def test_structured_usage_ignores_empty_usage(monkeypatch):
    record_metrics = Mock()
    monkeypatch.setattr("telemetry.record_llm_metrics", record_metrics)

    ai_service._record_structured_usage(
        {"input_tokens": 0, "output_tokens": 0},
        model="test-deployment",
        agent_name="structured_ChatbotDecision",
    )

    record_metrics.assert_not_called()
