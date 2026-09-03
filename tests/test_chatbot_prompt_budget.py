"""Regression tests for the compact, workflow-aware chatbot prompt."""

from agents.chatbot_agent import (
    CHATBOT_DECISION_PROMPT,
    _build_decision_prompt,
    _format_history,
)
from models.chatbot import ChatIntent, ChatTurn


def test_unknown_intent_prompt_is_materially_smaller_than_legacy_contract():
    prompt = _build_decision_prompt(None)
    assert len(prompt) < len(CHATBOT_DECISION_PROMPT) * 0.45
    assert "SCOPE:" in prompt
    assert "TICKET/LEAVE:" in prompt
    assert "MANAGEMENT:" in prompt


def test_known_workflow_receives_only_relevant_rules():
    ticket_prompt = _build_decision_prompt(ChatIntent.SUPPORT_ISSUE)
    assert "TICKET/LEAVE:" in ticket_prompt
    assert "MANAGEMENT:" not in ticket_prompt
    assert "NAVIGATION:" not in ticket_prompt

    management_prompt = _build_decision_prompt(ChatIntent.REASSIGN_TICKET)
    assert "MANAGEMENT:" in management_prompt
    assert "TICKET/LEAVE:" not in management_prompt


def test_history_is_limited_by_turn_count_and_message_length():
    history = [
        ChatTurn(role="user", message=f"turn-{index} " + "x" * 600)
        for index in range(10)
    ]
    formatted = _format_history(history)
    lines = formatted.splitlines()

    assert len(lines) == 6
    assert "turn-3" not in formatted
    assert "turn-4" in formatted
    assert all(len(line.removeprefix("user: ")) <= 400 for line in lines)
