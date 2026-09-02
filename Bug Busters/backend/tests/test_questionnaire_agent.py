import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from questionnaire_agent import generate_questions, QuestionnaireAgentError


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_parses_clean_json(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '[{"key": "pet_types", "label": "Which pets are allowed?", "placeholder": "Dogs and cats"}, '
        '{"key": "areas", "label": "Which office areas are off-limits?", "placeholder": "Kitchen, server room"}, '
        '{"key": "approval", "label": "Who approves bringing a pet in?", "placeholder": "Direct manager"}]'
    )

    questions = generate_questions("Office Pet Policy")

    assert len(questions) == 3
    assert questions[0] == {
        "key": "pet_types",
        "label": "Which pets are allowed?",
        "placeholder": "Dogs and cats",
    }


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_includes_policy_type_in_prompt(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '[{"key": "a", "label": "Q1?", "placeholder": "p"}, '
        '{"key": "b", "label": "Q2?", "placeholder": "p"}, '
        '{"key": "c", "label": "Q3?", "placeholder": "p"}]'
    )

    generate_questions("Office Pet Policy", policy_type="Custom Section")

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert 'categorized under "Custom Section"' in prompt_used


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_strips_code_fence(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '```json\n[{"key": "a", "label": "Q1?", "placeholder": "p"}, '
        '{"key": "b", "label": "Q2?", "placeholder": "p"}, '
        '{"key": "c", "label": "Q3?", "placeholder": "p"}]\n```'
    )

    questions = generate_questions("Office Pet Policy")

    assert len(questions) == 3


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_drops_duplicate_and_malformed_entries(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '[{"key": "a", "label": "Q1?", "placeholder": "p"}, '
        '{"key": "a", "label": "Duplicate key", "placeholder": "p"}, '
        '{"key": "", "label": "Missing key", "placeholder": "p"}, '
        '{"key": "b", "label": "", "placeholder": "p"}, '
        '"not a dict", '
        '{"key": "c", "label": "Q3?", "placeholder": "p"}]'
    )

    questions = generate_questions("Office Pet Policy")

    assert [q["key"] for q in questions] == ["a", "c"]


def test_generate_questions_rejects_empty_title():
    with pytest.raises(QuestionnaireAgentError):
        generate_questions("   ")


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(QuestionnaireAgentError):
        generate_questions("Office Pet Policy")


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_raises_on_unparseable_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "I can't help with that."

    with pytest.raises(QuestionnaireAgentError):
        generate_questions("Office Pet Policy")


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_raises_on_non_array_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '{"key": "a", "label": "Q1?"}'

    with pytest.raises(QuestionnaireAgentError):
        generate_questions("Office Pet Policy")


@patch("questionnaire_agent.OpenAIService")
def test_generate_questions_raises_when_all_entries_invalid(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '[{"key": "", "label": ""}]'

    with pytest.raises(QuestionnaireAgentError):
        generate_questions("Office Pet Policy")
