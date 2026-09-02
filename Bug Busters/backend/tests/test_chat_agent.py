import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from chat_agent import answer_chat_message, interpret_chat_intent, ChatAgentError

SAMPLE_SCREENS = [
    {"id": "hr-policies", "name": "Policies page"},
    {"id": "hr-teams", "name": "Teams page"},
]

SAMPLE_ROSTER = [
    {"email": "reeha.r@quadranttechnologies.com", "display_name": "Reeha R", "role": "HR"},
    {"email": "i-maria.zia@quadranttechnologies.com", "display_name": "Maria Zia", "role": "Intern"},
]


@pytest.fixture(autouse=True)
def mock_roster():
    # Every test in this file mocks the OpenAI call, so it never matters
    # what's actually in the real demo_login.db - keep these tests fast
    # and isolated from that file entirely.
    with patch("chat_agent.list_users", return_value=SAMPLE_ROSTER):
        yield


@patch("chat_agent.OpenAIService")
def test_answer_chat_message_returns_reply(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "You can find that under the Policies tab."

    result = answer_chat_message("Where do I find the PTO policy?")

    assert result == "You can find that under the Policies tab."


@patch("chat_agent.OpenAIService")
def test_answer_chat_message_strips_whitespace(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "  Sure, here you go.  \n"

    result = answer_chat_message("Hi")

    assert result == "Sure, here you go."


def test_answer_chat_message_rejects_empty_message():
    with pytest.raises(ChatAgentError):
        answer_chat_message("   ")


@patch("chat_agent.OpenAIService")
def test_answer_chat_message_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(ChatAgentError):
        answer_chat_message("Hi")


@patch("chat_agent.OpenAIService")
def test_answer_chat_message_raises_on_empty_reply(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "   "

    with pytest.raises(ChatAgentError):
        answer_chat_message("Hi")


@patch("chat_agent.OpenAIService")
def test_prompt_includes_roster_for_who_is_questions(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Reeha R is HR."

    answer_chat_message("who is reeha")

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "Reeha R (reeha.r@quadranttechnologies.com) - HR" in prompt_used
    assert "who is reeha" in prompt_used


@patch("chat_agent.OpenAIService")
def test_prompt_instructs_off_topic_refusal(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "I can only help with Quadrant Technologies questions."

    answer_chat_message("who is bill gates")

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "do NOT answer it" in prompt_used
    assert "ONLY answer questions about Quadrant Technologies" in prompt_used


@patch("chat_agent.list_users")
@patch("chat_agent.OpenAIService")
def test_prompt_survives_roster_lookup_failure(mock_service_cls, mock_list_users):
    # If the roster can't be loaded (e.g. DB not initialized yet), the
    # chatbot should still answer general questions rather than 500.
    mock_list_users.side_effect = Exception("db not ready")
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Sure, here's how to sign in..."

    result = answer_chat_message("How do I sign in?")

    assert result == "Sure, here's how to sign in..."


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_recognizes_theme_phrased_unexpectedly(mock_service_cls):
    # The whole point: no fixed keyword list, so an unusual phrasing the
    # LLM still understands (not literally "dark mode") must work.
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"intent": "set_theme", "theme": "dark", "screen_id": null}'
    )

    result = interpret_chat_intent("can you make this darker please", SAMPLE_SCREENS)

    assert result == {"intent": "set_theme", "theme": "dark", "screen_id": None}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_recognizes_navigation(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"intent": "navigate", "theme": null, "screen_id": "hr-teams"}'
    )

    result = interpret_chat_intent("take me to my team's page", SAMPLE_SCREENS)

    assert result == {"intent": "navigate", "theme": None, "screen_id": "hr-teams"}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_falls_back_to_other(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"intent": "other", "theme": null, "screen_id": null}'
    )

    result = interpret_chat_intent("what's the PTO policy?", SAMPLE_SCREENS)

    assert result == {"intent": "other", "theme": None, "screen_id": None}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_rejects_screen_id_not_in_list(mock_service_cls):
    # The LLM must not be trusted to invent a real-looking id - only ids
    # actually passed in are ever accepted.
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"intent": "navigate", "theme": null, "screen_id": "made-up-screen"}'
    )

    result = interpret_chat_intent("go to the made up screen", SAMPLE_SCREENS)

    assert result == {"intent": "other", "theme": None, "screen_id": None}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_rejects_invalid_theme_value(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"intent": "set_theme", "theme": "blue", "screen_id": null}'
    )

    result = interpret_chat_intent("make it blue", SAMPLE_SCREENS)

    assert result == {"intent": "other", "theme": None, "screen_id": None}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_handles_markdown_fenced_json(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '```json\n{"intent": "set_theme", "theme": "light", "screen_id": null}\n```'
    )

    result = interpret_chat_intent("light mode please", SAMPLE_SCREENS)

    assert result == {"intent": "set_theme", "theme": "light", "screen_id": None}


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_raises_on_unparseable_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "not json at all"

    with pytest.raises(ChatAgentError):
        interpret_chat_intent("hello", SAMPLE_SCREENS)


def test_interpret_chat_intent_rejects_empty_message():
    with pytest.raises(ChatAgentError):
        interpret_chat_intent("   ", SAMPLE_SCREENS)


@patch("chat_agent.OpenAIService")
def test_interpret_chat_intent_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(ChatAgentError):
        interpret_chat_intent("dark mode", SAMPLE_SCREENS)
