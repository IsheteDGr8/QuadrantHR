"""Unit tests for TicketGenie backend agents and AI classifier integration."""

from __future__ import annotations

import pytest

from agents.category_agent import (
    ALLOWED_DEPARTMENTS,
    get_categories_for_department,
    is_valid_category,
    is_valid_department,
)
from agents.orchestrator import TicketClassification, classify_ticket
from telemetry import record_llm_metrics


def test_category_taxonomy_validation():
    assert "IT Team" in ALLOWED_DEPARTMENTS
    assert is_valid_department("IT Team") is True
    assert is_valid_department("NonExistentTeam") is False

    it_categories = get_categories_for_department("IT Team")
    assert "Identity and Access Management" in it_categories
    assert is_valid_category("IT Team", "Identity and Access Management") is True
    assert is_valid_category("IT Team", "NonExistentCategory") is False


def test_classify_ticket_mock_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_MOCK_AI", "true")

    result = classify_ticket(
        "Cannot log into account",
        "My password is expired and I am locked out of my account.",
    )

    assert isinstance(result, TicketClassification)
    assert result.department == "IT Team"
    assert result.category == "Identity and Access Management"
    assert result.priority in {"Low", "Medium", "High", "Critical"}
    assert isinstance(result.confidence, float)
    assert result.needs_human_review is False


def test_telemetry_record_llm_metrics():
    # Verify record_llm_metrics executes without throwing an exception
    record_llm_metrics(
        prompt_tokens=150,
        completion_tokens=50,
        model="gpt-4o",
        agent_name="test_agent",
    )
