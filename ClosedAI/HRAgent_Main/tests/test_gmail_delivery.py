"""Tests for Gmail delivery helpers."""

from __future__ import annotations

import json

import pytest

from mcp_integration.gmail_delivery import (
    _build_raw_message,
    extract_draft_id,
    format_email_digest,
)


def test_extract_draft_id_from_json_object():
    payload = {"id": "r-123456", "message": {"id": "m-789"}}
    assert extract_draft_id(json.dumps(payload)) == "r-123456"


def test_extract_draft_id_from_embedded_text():
    text = 'Draft created: {"id": "draft-abc"}'
    assert extract_draft_id(text) == "draft-abc"


def test_build_raw_message_base64_decodes():
    raw = _build_raw_message(
        to="user@example.com",
        subject="Hello",
        body="Happy birthday!",
    )
    assert isinstance(raw, str)
    assert len(raw) > 20


def test_build_raw_message_with_attachment(tmp_path, monkeypatch):
    pdf = tmp_path / "workspace" / "outputs" / "form.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setenv("HRAGENT_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setattr(
        "mcp_integration.gmail_delivery.hragent_main",
        lambda: tmp_path,
    )
    raw = _build_raw_message(
        to="user@example.com",
        subject="I-9",
        body="Please see attached.",
        attachments=["outputs/form.pdf"],
    )
    decoded = __import__("base64").urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    assert b"form.pdf" in decoded
    assert b"JVBERi0xLjQgdGVzdA==" in decoded


def test_format_email_digest_empty():
    assert format_email_digest([]) == "No emails matched the query."


def test_format_email_digest_rows():
    text = format_email_digest(
        [
            {
                "subject": "PTO request",
                "from": "alex@example.com",
                "date": "Mon, 1 Jan 2026",
                "to": "hr@example.com",
                "snippet": "I'd like Friday off",
                "body": "Please approve Friday PTO.",
            }
        ]
    )
    assert "Fetched 1 email(s)" in text
    assert "PTO request" in text
    assert "alex@example.com" in text
