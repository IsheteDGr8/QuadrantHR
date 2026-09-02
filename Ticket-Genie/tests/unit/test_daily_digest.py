"""Unit tests for Daily Admin Summary Email Digest service."""

from backend.services.daily_digest_service import (
    generate_daily_digest_data,
    resolve_admin_recipients,
    send_daily_admin_digest,
)


def test_resolve_admin_recipients(monkeypatch):
    monkeypatch.setenv("ADMIN_DIGEST_EMAILS", "admin1@test.com, admin2@test.com")
    recipients = resolve_admin_recipients()
    emails = [r["email"] for r in recipients]
    assert "admin1@test.com" in emails
    assert "admin2@test.com" in emails


def test_generate_daily_digest_data():
    data = generate_daily_digest_data()
    assert "total_tickets" in data
    assert "open_count" in data
    assert "urgent_count" in data
    assert "needs_review_count" in data
    assert "timestamp" in data


def test_send_daily_admin_digest(monkeypatch):
    monkeypatch.setenv("ADMIN_DIGEST_EMAILS", "testadmin@company.com")
    res = send_daily_admin_digest()
    assert res["status"] in ("success", "failed")
    assert "testadmin@company.com" in res["recipients"]
