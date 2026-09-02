"""Client tool Action types must survive additive schema changes in-process."""

from __future__ import annotations

from tools.client_tool import _get_client_action_type


def test_client_tool_schema_can_add_optional_fields():
    name = "send_email_schema_compat_test"
    base = {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    }
    extended = {
        **base,
        "properties": {
            **base["properties"],
            "attachments": {"type": "array", "items": {"type": "string"}},
        },
    }
    first = _get_client_action_type(name, base)
    second = _get_client_action_type(name, extended)
    assert first is second
    action = first.model_validate(
        {
            "to": "a@example.com",
            "subject": "Hi",
            "body": "Hello",
            "attachments": ["outputs/form.pdf"],
        }
    )
    extra = getattr(action, "model_extra", None) or {}
    attachments = getattr(action, "attachments", None) or extra.get("attachments")
    assert attachments == ["outputs/form.pdf"]
