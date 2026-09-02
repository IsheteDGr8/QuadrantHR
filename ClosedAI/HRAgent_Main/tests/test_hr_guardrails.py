"""HITL guardrails must pause sends even when policy/analyzer are missing."""

from __future__ import annotations

from types import SimpleNamespace

from security.policies.confirmation_policy import ConfirmRisky, NeverConfirm
from security.policies.hr_guardrails import (
    READ_ONLY_BLOCK_MESSAGE,
    combine_risks,
    conversation_is_read_only,
    is_forced_high_risk_tool,
    is_mutating_hr_tool,
    resolve_event_risk,
    should_pause_for_confirmation,
)
from security.policies.llm_analyzer import LLMSecurityAnalyzer
from security.policies.risk import SecurityRisk


def _event(name: str, risk: SecurityRisk = SecurityRisk.UNKNOWN) -> SimpleNamespace:
    return SimpleNamespace(tool_name=name, security_risk=risk)


def test_forced_high_matches_client_and_mcp_names():
    assert is_forced_high_risk_tool("send_slack_message")
    assert is_forced_high_risk_tool("gmail_send_email")
    assert is_forced_high_risk_tool("slack_send_message")
    assert is_forced_high_risk_tool("upsert_document")
    assert not is_forced_high_risk_tool("list_slack_channels")
    assert not is_forced_high_risk_tool("list_emails")
    assert not is_forced_high_risk_tool("policy_search")
    assert not is_forced_high_risk_tool("create_draft")


def test_never_confirm_still_pauses_send():
    policy = NeverConfirm()
    events = [_event("send_email", SecurityRisk.LOW)]
    assert should_pause_for_confirmation(policy, events, analyzer=None) is True


def test_missing_analyzer_still_pauses_forced_high():
    policy = ConfirmRisky(confirm_unknown=False)
    events = [_event("send_slack_message", SecurityRisk.UNKNOWN)]
    assert should_pause_for_confirmation(policy, events, analyzer=None) is True


def test_reads_do_not_pause_when_confirm_unknown_false():
    policy = ConfirmRisky(confirm_unknown=False)
    events = [_event("list_emails", SecurityRisk.UNKNOWN)]
    assert should_pause_for_confirmation(policy, events, analyzer=None) is False


def test_model_low_label_cannot_skip_send():
    policy = ConfirmRisky(confirm_unknown=False)
    analyzer = LLMSecurityAnalyzer()
    events = [_event("send_teams_message", SecurityRisk.LOW)]
    assert resolve_event_risk(events[0], analyzer) is SecurityRisk.HIGH
    assert should_pause_for_confirmation(policy, events, analyzer) is True


def test_combine_risks_prefers_high():
    assert combine_risks(SecurityRisk.UNKNOWN, SecurityRisk.HIGH) is SecurityRisk.HIGH
    assert combine_risks(SecurityRisk.LOW, SecurityRisk.MEDIUM) is SecurityRisk.MEDIUM


def test_read_only_conversation_and_mutating_tools():
    conv = SimpleNamespace(
        state=SimpleNamespace(agent_state={"hr_read_only": True}, tags={})
    )
    assert conversation_is_read_only(conv)
    assert is_mutating_hr_tool("send_slack_message")
    assert is_mutating_hr_tool("create_draft")
    assert not is_mutating_hr_tool("list_emails")
    tagged = SimpleNamespace(state=SimpleNamespace(agent_state={}, tags={"readonly": "true"}))
    assert conversation_is_read_only(tagged)
    assert READ_ONLY_BLOCK_MESSAGE
