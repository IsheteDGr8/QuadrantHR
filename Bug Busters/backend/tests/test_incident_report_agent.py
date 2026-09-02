import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import httpx
import pytest
from openai import BadRequestError

from incident_report_agent import (
    reply_to_incident_message,
    summarize_incident,
    IncidentReportAgentError,
)


def _content_filter_error():
    # Shape confirmed against a real Azure OpenAI content-filter block:
    # "code" sits at the top level of body, not nested under "error" -
    # the openai SDK itself parses exc.code as body.get("code").
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.com"))
    return BadRequestError(
        "content filtered",
        response=response,
        body={"code": "content_filter", "message": "flagged"},
    )


def _other_bad_request_error():
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.com"))
    return BadRequestError(
        "bad request",
        response=response,
        body={"code": "invalid_request_error", "message": "oops"},
    )


def _conversation(user_turns):
    # Alternates user/assistant, ending on a user turn - matches the real
    # shape IncidentReport.jsx sends.
    messages = []
    for i in range(user_turns):
        messages.append({"role": "user", "text": f"answer {i}"})
        if i < user_turns - 1:
            messages.append({"role": "assistant", "text": f"question {i}"})
    return messages


@patch("incident_report_agent.OpenAIService")
def test_reply_prompt_short_conversation_has_no_urgency_nudge(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Follow-up?"

    reply_to_incident_message(_conversation(2))  # 1 assistant turn

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "lean toward acknowledging" not in prompt_used
    assert "MUST respond with a brief acknowledgement" not in prompt_used


@patch("incident_report_agent.OpenAIService")
def test_reply_prompt_three_questions_gets_soft_nudge(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Follow-up?"

    reply_to_incident_message(_conversation(4))  # 3 assistant turns

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "lean toward acknowledging" in prompt_used
    assert "MUST respond with a brief acknowledgement" not in prompt_used


@patch("incident_report_agent.OpenAIService")
def test_reply_still_calls_llm_below_the_hard_cutoff(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Follow-up?"

    reply = reply_to_incident_message(_conversation(6))  # 5 assistant turns

    mock_service.generate_policy.assert_called_once()
    assert reply == "Follow-up?"


@patch("incident_report_agent.OpenAIService")
def test_reply_hits_hard_cutoff_without_calling_llm(mock_service_cls):
    mock_service = mock_service_cls.return_value

    reply = reply_to_incident_message(_conversation(7))  # 6 assistant turns

    mock_service.generate_policy.assert_not_called()
    assert "Generate Summary Report" in reply


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_returns_reply(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "  When and where did this happen?  "

    reply = reply_to_incident_message(
        [{"role": "user", "text": "A coworker was yelling at me in a meeting."}]
    )

    assert reply == "When and where did this happen?"


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_includes_conversation_in_prompt(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Follow-up question?"

    reply_to_incident_message(
        [
            {"role": "user", "text": "A coworker was yelling at me."},
            {"role": "assistant", "text": "When did this happen?"},
            {"role": "user", "text": "Yesterday, in the conference room."},
        ]
    )

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "A coworker was yelling at me." in prompt_used
    assert "Yesterday, in the conference room." in prompt_used


def test_reply_to_incident_message_rejects_empty_conversation():
    with pytest.raises(IncidentReportAgentError):
        reply_to_incident_message([])


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(IncidentReportAgentError):
        reply_to_incident_message([{"role": "user", "text": "Something happened."}])


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_raises_on_empty_reply(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "   "

    with pytest.raises(IncidentReportAgentError):
        reply_to_incident_message([{"role": "user", "text": "Something happened."}])


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_flags_content_filter_block(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = _content_filter_error()

    with pytest.raises(IncidentReportAgentError) as exc_info:
        reply_to_incident_message([{"role": "user", "text": "Something happened."}])

    assert exc_info.value.content_filtered is True


@patch("incident_report_agent.OpenAIService")
def test_reply_to_incident_message_other_bad_request_not_flagged(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = _other_bad_request_error()

    with pytest.raises(IncidentReportAgentError) as exc_info:
        reply_to_incident_message([{"role": "user", "text": "Something happened."}])

    assert exc_info.value.content_filtered is False


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_parses_clean_json(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"summary": "A coworker raised their voice during a meeting.", '
        '"next_steps": ["Escalate to HR.", "Document witnesses."]}'
    )

    result = summarize_incident(
        [{"role": "user", "text": "A coworker was yelling at me in a meeting."}]
    )

    assert result["summary"] == "A coworker raised their voice during a meeting."
    assert result["next_steps"] == ["Escalate to HR.", "Document witnesses."]


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_strips_code_fence(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '```json\n{"summary": "S", "next_steps": ["N1", "N2"]}\n```'
    )

    result = summarize_incident([{"role": "user", "text": "Something happened."}])

    assert result["summary"] == "S"
    assert result["next_steps"] == ["N1", "N2"]


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_only_uses_user_messages_in_prompt(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '{"summary": "S", "next_steps": ["N1"]}'

    summarize_incident(
        [
            {"role": "user", "text": "A coworker was yelling at me."},
            {"role": "assistant", "text": "When and where did this happen?"},
        ]
    )

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "A coworker was yelling at me." in prompt_used
    assert "When and where did this happen?" not in prompt_used


def test_summarize_incident_rejects_conversation_with_no_user_messages():
    with pytest.raises(IncidentReportAgentError):
        summarize_incident([{"role": "assistant", "text": "Hi, what happened?"}])


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(IncidentReportAgentError):
        summarize_incident([{"role": "user", "text": "Something happened."}])


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_flags_content_filter_block(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = _content_filter_error()

    with pytest.raises(IncidentReportAgentError) as exc_info:
        summarize_incident([{"role": "user", "text": "Something happened."}])

    assert exc_info.value.content_filtered is True


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_raises_on_unparseable_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "I can't help with that."

    with pytest.raises(IncidentReportAgentError):
        summarize_incident([{"role": "user", "text": "Something happened."}])


@patch("incident_report_agent.OpenAIService")
def test_summarize_incident_raises_on_empty_next_steps(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '{"summary": "S", "next_steps": []}'

    with pytest.raises(IncidentReportAgentError):
        summarize_incident([{"role": "user", "text": "Something happened."}])
