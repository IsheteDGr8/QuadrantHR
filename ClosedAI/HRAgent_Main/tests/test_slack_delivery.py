"""Tests for Slack delivery helpers."""

from __future__ import annotations

import pytest

from mcp_integration.slack_delivery import (
    SlackChannelNotFoundError,
    _parse_mcp_channels,
    _send_mcp_arguments,
    format_channel_digest,
    normalize_channel_name,
    resolve_channel,
)


def test_normalize_channel_name_strips_hash_and_mention():
    assert normalize_channel_name("#all-hr-agent") == "all-hr-agent"
    assert normalize_channel_name("  general  ") == "general"
    assert normalize_channel_name("<#C123|people-ops>") == "C123"


def test_resolve_channel_matches_name_or_id():
    channels = [
        {"id": "C111", "name": "people-ops", "is_private": False, "is_member": True},
        {"id": "C222", "name": "alerts", "is_private": True, "is_member": True},
    ]
    assert resolve_channel("#People-Ops", channels)["id"] == "C111"
    assert resolve_channel("C222", channels)["name"] == "alerts"


def test_resolve_channel_rejects_unknown_names():
    channels = [{"id": "C111", "name": "people-ops"}]
    with pytest.raises(SlackChannelNotFoundError) as exc:
        resolve_channel("#general", channels)
    assert "people-ops" in str(exc.value)
    assert "does not exist" in str(exc.value)


def test_format_channel_digest_lists_real_names():
    text = format_channel_digest(
        [{"id": "C111", "name": "people-ops", "is_private": False, "is_member": True}]
    )
    assert "#people-ops" in text
    assert "send_slack_message" in text or "listed channel" in text.lower()


def test_parse_mcp_channels_from_json_and_hashes():
    json_text = '{"channels": [{"id": "C1", "name": "hr-help"}]}'
    parsed = _parse_mcp_channels(json_text)
    assert parsed[0]["name"] == "hr-help"
    hashed = _parse_mcp_channels("You can post to #benefits and #leave-requests")
    names = {row["name"] for row in hashed}
    assert "benefits" in names
    assert "leave-requests" in names


def test_send_mcp_arguments_prefer_schema_fields():
    args = _send_mcp_arguments(
        "C111",
        "hello",
        {"properties": {"channel_id": {"type": "string"}, "message": {"type": "string"}}},
    )
    assert args == {"channel_id": "C111", "message": "hello"}
