"""Deterministic HR HITL / read-only rails.

Prompt text and ConfirmRisky + LLMSecurityAnalyzer are not enough:

- Stored conversations default to ``NeverConfirm`` when the create payload
  omitted a policy (or an old chat was created before ConfirmRisky).
- When ``security_analyzer`` is missing, ``Agent._requires_user_confirmation``
  used to treat every action as UNKNOWN. Combined with ``confirm_unknown=false``
  that skipped approval for sends and writes.
- The model can omit ``security_risk`` or label a send LOW.

These helpers are the hard floor: outbound / mutating tools always pause for
Approve & Send, and read-only conversations never execute them.
"""

from __future__ import annotations

from security.policies.confirmation_policy import ConfirmationPolicyBase
from security.policies.risk import SecurityRisk

# Substring tokens matched against the lowercased tool name (client tools and
# MCP-prefixed names like ``gmail_send_email`` / ``slack_send_message``).
_FORCED_HIGH_TOKENS = (
    "send_email",
    "send_slack_message",
    "send_teams_message",
    "send_message",
    "upsert_document",
    "replace_document",
    "delete_document",
    "delete_item",
    "drafts_send",
    "send_draft",
    "messages_send",
    "chat_postmessage",
    "office_fill",
    "office_template_fill",
)

_MUTATING_TOKENS = _FORCED_HIGH_TOKENS + (
    "create_draft",
    "write_workspace_file",
    "generate_document",
)

READ_ONLY_BLOCK_MESSAGE = (
    "Read-only mode is on for this conversation. Sends and record writes are "
    "blocked. Turn off Settings → Tool Permissions → Read-only mode, then "
    "start a New Chat."
)


def is_forced_high_risk_tool(tool_name: str | None) -> bool:
    """True when this tool must pause for ConfirmRisky even if labeled LOW."""
    if not tool_name:
        return False
    name = tool_name.strip().lower().replace("-", "_")
    return any(tok in name for tok in _FORCED_HIGH_TOKENS)


def is_mutating_hr_tool(tool_name: str | None) -> bool:
    """True when read-only mode must refuse execution."""
    if not tool_name:
        return False
    name = tool_name.strip().lower().replace("-", "_")
    return any(tok in name for tok in _MUTATING_TOKENS)


def conversation_is_read_only(conversation: object | None) -> bool:
    if conversation is None:
        return False
    state = getattr(conversation, "state", None) or conversation
    agent_state = getattr(state, "agent_state", None) or {}
    if agent_state.get("hr_read_only"):
        return True
    tags = getattr(state, "tags", None) or {}
    return str(tags.get("readonly", "")).lower() in ("1", "true", "yes")


def combine_risks(a: SecurityRisk, b: SecurityRisk) -> SecurityRisk:
    """Prefer HIGH; otherwise the concrete risk. UNKNOWN yields to a known level."""
    if a == SecurityRisk.HIGH or b == SecurityRisk.HIGH:
        return SecurityRisk.HIGH
    if a == SecurityRisk.UNKNOWN:
        return b
    if b == SecurityRisk.UNKNOWN:
        return a
    return max(a, b)


def resolve_event_risk(event: object, analyzer: object | None = None) -> SecurityRisk:
    name = str(getattr(event, "tool_name", "") or "")
    event_risk = getattr(event, "security_risk", SecurityRisk.UNKNOWN)
    if not isinstance(event_risk, SecurityRisk):
        try:
            event_risk = SecurityRisk(event_risk)
        except (TypeError, ValueError):
            event_risk = SecurityRisk.UNKNOWN
    if is_forced_high_risk_tool(name):
        event_risk = SecurityRisk.HIGH
    if analyzer is not None:
        try:
            analyzed = analyzer.security_risk(event)  # type: ignore[attr-defined]
            if isinstance(analyzed, SecurityRisk):
                event_risk = combine_risks(event_risk, analyzed)
        except Exception:
            event_risk = SecurityRisk.HIGH
    return event_risk


def should_pause_for_confirmation(
    policy: ConfirmationPolicyBase,
    events: list[object],
    analyzer: object | None = None,
) -> bool:
    """Return True when the agent must enter WAITING_FOR_CONFIRMATION.

    Forced-HIGH tools always pause, including under ``NeverConfirm`` (old chats
    and Settings auto-approve cannot skip email / Slack / DB writes).
    """
    for event in events:
        name = str(getattr(event, "tool_name", "") or "")
        if is_forced_high_risk_tool(name):
            return True
        risk = resolve_event_risk(event, analyzer)
        if policy.should_confirm(risk):
            return True
    return False
