import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from incident_policy_agent import draft_from_incident, IncidentPolicyAgentError


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_parses_clean_json(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"title": "Data Handling Policy", '
        '"requirements": ["Encrypt sensitive data at rest.", "Require MFA for admin access."]}'
    )

    result = draft_from_incident("A coworker sent a phishing email and leaked passwords.")

    assert result["title"] == "Data Handling Policy"
    assert len(result["requirements"]) == 2


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_includes_context_in_prompt(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '{"title": "T", "requirements": ["R1"]}'
    )

    draft_from_incident("Incident text", context="Follow-up: Was data exposed? Yes.")

    prompt_used = mock_service.generate_policy.call_args[0][0]
    assert "Follow-up: Was data exposed? Yes." in prompt_used


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_strips_code_fence(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = (
        '```json\n{"title": "T", "requirements": ["R1", "R2"]}\n```'
    )

    result = draft_from_incident("Incident text")

    assert result["title"] == "T"
    assert result["requirements"] == ["R1", "R2"]


def test_draft_from_incident_rejects_empty_summary():
    with pytest.raises(IncidentPolicyAgentError):
        draft_from_incident("   ")


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_raises_on_llm_failure(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.side_effect = Exception("Azure OpenAI unavailable")

    with pytest.raises(IncidentPolicyAgentError):
        draft_from_incident("Incident text")


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_raises_on_unparseable_response(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = "I can't help with that."

    with pytest.raises(IncidentPolicyAgentError):
        draft_from_incident("Incident text")


@patch("incident_policy_agent.OpenAIService")
def test_draft_from_incident_raises_on_empty_requirements(mock_service_cls):
    mock_service = mock_service_cls.return_value
    mock_service.generate_policy.return_value = '{"title": "T", "requirements": []}'

    with pytest.raises(IncidentPolicyAgentError):
        draft_from_incident("Incident text")
