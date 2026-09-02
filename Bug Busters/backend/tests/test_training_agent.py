import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

import training_agent
from training_agent import generate_metadata, TrainingAgentError


@patch("training_agent.OpenAIService")
def test_generate_metadata_parses_clean_json(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"title": "Remote Work Handbook", '
        '"description": "Covers eligibility and expectations for remote work.", '
        '"category": "Handbook"}'
    )

    result = generate_metadata("handbook.pdf", "This handbook covers remote work policy...")

    assert result == {
        "title": "Remote Work Handbook",
        "description": "Covers eligibility and expectations for remote work.",
        "category": "Handbook",
    }


@patch("training_agent.OpenAIService")
def test_generate_metadata_strips_code_fence(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '```json\n{"title": "T", "description": "D", "category": "Onboarding"}\n```'
    )

    result = generate_metadata("doc.pdf", "some content")

    assert result["title"] == "T"
    assert result["category"] == "Onboarding"


def test_generate_metadata_rejects_empty_text():
    with pytest.raises(TrainingAgentError):
        generate_metadata("empty.pdf", "   ")


@patch("training_agent.OpenAIService")
def test_generate_metadata_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(TrainingAgentError):
        generate_metadata("doc.pdf", "some content")


@patch("training_agent.OpenAIService")
def test_generate_metadata_raises_on_unparseable_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "Sorry, I can't help with that."

    with pytest.raises(TrainingAgentError):
        generate_metadata("doc.pdf", "some content")


@patch("training_agent.OpenAIService")
def test_generate_metadata_raises_on_missing_field(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '{"title": "T", "description": "D"}'

    with pytest.raises(TrainingAgentError):
        generate_metadata("doc.pdf", "some content")
