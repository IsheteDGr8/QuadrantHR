"""Azure Application Insights AI-usage query and aggregation tests."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.azure_ai_usage_service import (
    AI_USAGE_QUERY,
    AzureAIUsageUnavailableError,
    get_azure_ai_usage,
    is_ai_usage_admin,
)


class FakeLogsClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query_workspace(self, workspace_id, query, **kwargs):
        self.calls.append((workspace_id, query, kwargs))
        columns = [
            "Day",
            "Agent",
            "Model",
            "Calls",
            "PromptTokens",
            "CompletionTokens",
            "TotalTokens",
            "EstimatedCostUsd",
            "LastSeen",
        ]
        table = SimpleNamespace(columns=columns, rows=self.rows)
        return SimpleNamespace(status="Success", tables=[table])


def test_azure_usage_aggregates_daily_agent_rows():
    day = datetime(2026, 8, 20, tzinfo=timezone.utc)
    client = FakeLogsClient(
        [
            [day, "chatbot", "gpt-a", 2, 100, 40, 140, 0.0011, day],
            [day, "classifier", "gpt-a", 1, 50, 10, 60, 0.0004, day],
        ]
    )

    result = get_azure_ai_usage(days=30, workspace_id="workspace-id", client=client)

    assert result["source"] == "Azure Application Insights"
    assert result["totals"] == {
        "calls": 3,
        "prompt_tokens": 150,
        "completion_tokens": 50,
        "total_tokens": 200,
        "estimated_cost_usd": 0.0015,
    }
    assert result["daily"] == [
        {
            "day": "2026-08-20",
            "calls": 3,
            "total_tokens": 200,
            "estimated_cost_usd": 0.0015,
        }
    ]
    assert client.calls[0][0] == "workspace-id"
    assert client.calls[0][1] == AI_USAGE_QUERY


def test_azure_usage_requires_workspace_configuration(monkeypatch):
    monkeypatch.delenv("LOG_ANALYTICS_WORKSPACE_ID", raising=False)
    with pytest.raises(AzureAIUsageUnavailableError):
        get_azure_ai_usage(client=FakeLogsClient([]))


def test_ai_usage_role_boundary_is_exact_and_verified():
    assert is_ai_usage_admin({"role": "Admin"}) is True
    assert is_ai_usage_admin({"role": "Super Admin"}) is True
    assert is_ai_usage_admin({"role": "Employee"}) is False
    assert is_ai_usage_admin({"role": "Department Admin"}) is False
    assert is_ai_usage_admin(None) is False


def test_build_azure_credential_constructs_chain(monkeypatch):
    from azure.identity import ChainedTokenCredential

    from services.azure_ai_usage_service import _build_azure_credential

    monkeypatch.setenv("AZURE_CLIENT_ID", "fake-app-registration-id")
    credential = _build_azure_credential()
    assert isinstance(credential, ChainedTokenCredential)
