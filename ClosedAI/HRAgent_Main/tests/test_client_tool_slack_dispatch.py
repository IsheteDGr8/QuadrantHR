"""Client Slack tools must dispatch by tool name, not Action.kind."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from tools.client_tool import (
    ClientTool,
    ClientToolExecutor,
    ClientToolSpec,
    _current_client_tool_name,
    _resolve_client_tool_name,
    execute_client_tool,
)


def test_resolve_uses_context_var_when_kind_is_generic():
    token = _current_client_tool_name.set("list_slack_channels")
    try:
        action = SimpleNamespace(kind="Action")
        assert _resolve_client_tool_name(action) == "list_slack_channels"
    finally:
        _current_client_tool_name.reset(token)


def test_execute_list_slack_channels_calls_delivery():
    channels = [{"id": "C123", "name": "all-hr-agent", "is_private": False, "is_member": True}]
    with patch(
        "mcp_integration.slack_delivery.list_slack_channels_sync",
        return_value=channels,
    ) as listed:
        obs = execute_client_tool("list_slack_channels", SimpleNamespace())
    listed.assert_called_once()
    assert obs.is_error is False
    assert "#all-hr-agent" in obs.text
    assert "dispatched to client" not in obs.text.lower()


def test_unhandled_client_tool_is_error_not_stub():
    obs = execute_client_tool("send_teams_message", SimpleNamespace())
    assert obs.is_error is True
    assert "dispatched to client" not in obs.text.lower()


def test_client_tool_call_dispatches_even_with_generic_action_kind():
    spec = ClientToolSpec(
        name="list_slack_channels",
        description="list",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    tool = ClientTool.from_spec(spec)
    action = tool.action_type.model_validate({})
    channels = [{"id": "C123", "name": "all-hr-agent"}]
    with patch(
        "mcp_integration.slack_delivery.list_slack_channels_sync",
        return_value=channels,
    ) as listed:
        obs = tool(action)
    listed.assert_called_once()
    assert "#all-hr-agent" in obs.text


def test_executor_uses_context_name_not_action_kind():
    executor = ClientToolExecutor()
    token = _current_client_tool_name.set("list_slack_channels")
    try:
        with patch(
            "mcp_integration.slack_delivery.list_slack_channels_sync",
            return_value=[{"id": "C1", "name": "ops"}],
        ) as listed:
            obs = executor(SimpleNamespace(kind="Action"))
        listed.assert_called_once()
        assert "#ops" in obs.text
    finally:
        _current_client_tool_name.reset(token)
