"""Google SMTP Email Notification Service for TicketGenie."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import smtplib
import sys
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ticketgenie.email_service")

# In-memory outbox log for unit testing, dev debugging, and API inspection
OUTBOX_LOG: List[Dict[str, Any]] = []


def get_outbox_log() -> List[Dict[str, Any]]:
    """Retrieve in-memory outbox email log."""
    return list(OUTBOX_LOG)


def clear_outbox_log() -> None:
    """Clear in-memory outbox email log (useful for testing)."""
    OUTBOX_LOG.clear()


_EMAIL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def get_smtp_config() -> Dict[str, Any]:
    """Retrieve SMTP, Brevo, SendGrid, and Resend configuration from environment variables."""
    brevo_key = (
        os.getenv("BREVO_API_KEY", "").strip() or os.getenv("BREVO_KEY", "").strip()
    )
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "").strip()

    host = os.getenv(
        "SMTP_HOST",
        "smtp-relay.brevo.com"
        if brevo_key
        else ("smtp.sendgrid.net" if sendgrid_key else "smtp.gmail.com"),
    ).strip()
    port = int(os.getenv("SMTP_PORT", "587").strip() or "587")

    user = (
        ("apikey" if sendgrid_key else "")
        or os.getenv("BREVO_USER", "").strip()
        or os.getenv("SMTP_USER", "").strip()
        or os.getenv("GMAIL_USER", "").strip()
        or os.getenv("GOOGLE_EMAIL", "").strip()
        or os.getenv("GMAIL_EMAIL", "").strip()
    )
    password = (
        brevo_key
        or sendgrid_key
        or os.getenv("SMTP_PASSWORD", "").strip()
        or os.getenv("GMAIL_APP_PASSWORD", "").strip()
        or os.getenv("GOOGLE_APP_PASSWORD", "").strip()
    )
    from_email = (
        os.getenv("BREVO_FROM_EMAIL", "").strip()
        or os.getenv("RESEND_FROM_EMAIL", "").strip()
        or os.getenv("SENDGRID_FROM_EMAIL", "").strip()
        or os.getenv("SMTP_FROM", "").strip()
        or (user if "@" in user else "notifications@ticketgenie.com")
    )
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    enabled = os.getenv("EMAIL_ENABLED", "true").lower() in ("true", "1", "yes")

    return {
        "brevo_key": brevo_key,
        "resend_key": resend_key,
        "sendgrid_key": sendgrid_key,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "use_tls": use_tls,
        "enabled": enabled,
    }


def _send_via_brevo_api(
    config: Dict[str, Any], to_email: str, subject: str, body_html: str
) -> bool:
    """Send email directly using Brevo REST API v3 over HTTPS (brevo.com)."""
    payload = {
        "sender": {"name": "TicketGenie Support", "email": config["from_email"]},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": body_html,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=data,
        headers={
            "api-key": config["brevo_key"],
            "Content-Type": "application/json",
            "User-Agent": "TicketGenie-Backend",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status in (200, 201, 202)


def _send_via_resend_api(
    config: Dict[str, Any], to_email: str, subject: str, body_html: str
) -> bool:
    """Send email directly using Resend Web API over HTTPS (resend.com)."""
    payload = {
        "from": config["from_email"]
        if "@" in config["from_email"]
        else "TicketGenie <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {config['resend_key']}",
            "Content-Type": "application/json",
            "User-Agent": "TicketGenie-Backend",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status in (200, 201, 202)


def _send_via_sendgrid_api(
    config: Dict[str, Any], to_email: str, subject: str, body_html: str
) -> bool:
    """Send email directly using SendGrid Web API v3 over HTTPS."""
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": config["from_email"], "name": "TicketGenie Support"},
        "subject": subject,
        "content": [{"type": "text/html", "value": body_html}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {config['sendgrid_key']}",
            "Content-Type": "application/json",
            "User-Agent": "TicketGenie-Backend",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status in (200, 202)


def _send_email_sync(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> bool:
    """Synchronous core email dispatcher (Brevo API -> Resend API -> SendGrid API -> Google SMTP -> Outbox fallback)."""
    if not to_email or "@" not in to_email:
        logger.warning(f"Invalid email address provided: {to_email}")
        return False

    config = get_smtp_config()
    timestamp = datetime.now().isoformat()

    log_entry: Dict[str, Any] = {
        "timestamp": timestamp,
        "to": to_email,
        "from": config["from_email"],
        "subject": subject,
        "body_html": body_html,
        "body_text": body_text or body_html,
        "status": "pending",
        "error": None,
    }

    if not config["enabled"]:
        log_entry["status"] = "disabled"
        OUTBOX_LOG.append(log_entry)
        return True

    # 1. Try Brevo API if API key is set (300 free emails/day, 0 credit card needed)
    if config["brevo_key"]:
        try:
            success = _send_via_brevo_api(config, to_email, subject, body_html)
            if success:
                log_entry["status"] = "sent_brevo_api"
                OUTBOX_LOG.append(log_entry)
                logger.info(
                    f"Successfully sent Brevo API email to {to_email}: {subject}"
                )
                return True
        except Exception as brevo_err:
            logger.warning(f"Brevo API dispatch failed ({brevo_err}). Trying fallback.")

    # 1. Try Resend API if API key is set (3,000 free emails/month, 0 credit card needed)
    if config["resend_key"]:
        try:
            success = _send_via_resend_api(config, to_email, subject, body_html)
            if success:
                log_entry["status"] = "sent_resend_api"
                OUTBOX_LOG.append(log_entry)
                logger.info(
                    f"Successfully sent Resend API email to {to_email}: {subject}"
                )
                return True
        except Exception as resend_err:
            logger.warning(
                f"Resend API dispatch failed ({resend_err}). Trying fallback."
            )

    # 1. Try SendGrid Web API v3 if API key is set
    if config["sendgrid_key"]:
        try:
            success = _send_via_sendgrid_api(config, to_email, subject, body_html)
            if success:
                log_entry["status"] = "sent_sendgrid_api"
                OUTBOX_LOG.append(log_entry)
                logger.info(
                    f"Successfully sent SendGrid API email to {to_email}: {subject}"
                )
                return True
        except Exception as sg_err:
            logger.warning(
                f"SendGrid API dispatch failed ({sg_err}). Trying SMTP fallback."
            )

    # 2. Try SMTP Dispatch (SendGrid SMTP Relay or Google SMTP)
    if config["user"] and config["password"]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = config["from_email"]
            msg["To"] = to_email

            plain_part = MIMEText(body_text or body_html, "plain")
            html_part = MIMEText(body_html, "html")
            msg.attach(plain_part)
            msg.attach(html_part)

            server = smtplib.SMTP(config["host"], config["port"], timeout=10)
            if config["use_tls"]:
                server.starttls()
            server.login(config["user"], config["password"])
            server.send_message(msg)
            server.quit()

            log_entry["status"] = "sent_smtp"
            OUTBOX_LOG.append(log_entry)
            logger.info(f"Successfully sent SMTP email to {to_email}: {subject}")
            return True
        except Exception as smtp_err:
            err_msg = str(smtp_err)
            logger.warning(
                f"SMTP email dispatch failed ({err_msg}). Recording in outbox log."
            )
            log_entry["status"] = "failed_smtp_fallback_logged"
            log_entry["error"] = err_msg
            OUTBOX_LOG.append(log_entry)
            return False

    # 3. Fallback: Log in-memory outbox
    log_entry["status"] = "logged_offline (no credentials)"
    OUTBOX_LOG.append(log_entry)
    logger.info(f"[Email Logged Offline] To: {to_email} | Subject: {subject}")
    return True


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    async_dispatch: Optional[bool] = None,
) -> bool:
    """
    Public email dispatch function.
    Dispatches asynchronously in a background thread pool by default so web requests return instantly.
    Runs synchronously during unit testing or when async_dispatch is False.
    """
    is_testing = "pytest" in sys.modules or os.getenv("TESTING", "").lower() == "true"
    should_async = not is_testing if async_dispatch is None else async_dispatch

    if should_async:
        _EMAIL_EXECUTOR.submit(
            _send_email_sync, to_email, subject, body_html, body_text
        )
        return True
    return _send_email_sync(to_email, subject, body_html, body_text)


# ---------------------------------------------------------------------------
# High-Level Notification Email Builders
# ---------------------------------------------------------------------------


def get_frontend_url() -> str:
    """Retrieve frontend web app base URL."""
    return os.getenv("FRONTEND_URL", "http://localhost:8080").rstrip("/")


def send_ticket_created_email(ticket: dict, recipient_email: str) -> bool:
    """Send ticket creation confirmation email."""
    ticket_id = ticket.get("id", "HD-1000")
    title = ticket.get("title", "Support Request")
    category = ticket.get("category", "IT Support")
    priority = ticket.get("priority", "Medium")
    dept = ticket.get("department", "IT Team")
    desc = ticket.get("description", "")
    frontend_url = get_frontend_url()
    ticket_url = f"{frontend_url}/tickets/{ticket_id}"

    subject = f"[TicketGenie] Ticket Confirmation - #{ticket_id}: {title}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="border-bottom: 2px solid #7e22ce; padding-bottom: 16px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
          <h2 style="color: #7e22ce; margin: 0; font-size: 22px;">TicketGenie Support</h2>
          <span style="background: #f3e8ff; color: #7e22ce; padding: 4px 12px; border-radius: 16px; font-weight: bold; font-size: 13px;">Confirmed</span>
        </div>

        <p style="font-size: 16px; color: #334155;">Hello,</p>
        <p style="font-size: 15px; color: #334155; line-height: 1.6;">
          Your support request <strong>#{ticket_id}</strong> has been successfully submitted and queued for review.
        </p>

        <div style="background: #f8fafc; border-left: 4px solid #7e22ce; padding: 16px; border-radius: 6px; margin: 20px 0;">
          <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr><td style="padding: 6px 0; color: #64748b; width: 120px;"><strong>Ticket ID:</strong></td><td style="color: #0f172a;">#{ticket_id}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;"><strong>Subject:</strong></td><td style="color: #0f172a;">{title}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;"><strong>Category:</strong></td><td style="color: #0f172a;">{category}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;"><strong>Priority:</strong></td><td style="color: #0f172a;">{priority}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;"><strong>Department:</strong></td><td style="color: #0f172a;">{dept}</td></tr>
            <tr><td style="padding: 6px 0; color: #64748b;"><strong>Status:</strong></td><td style="color: #10b981; font-weight: bold;">Open</td></tr>
          </table>
        </div>

        <div style="margin-top: 20px;">
          <h4 style="margin: 0 0 8px 0; color: #475569; font-size: 14px;">Description:</h4>
          <p style="background: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 14px; color: #334155; margin: 0; line-height: 1.5;">{desc}</p>
        </div>

        <div style="margin-top: 28px; text-align: center;">
          <a href="{ticket_url}" style="display: inline-block; background-color: #7e22ce; color: #ffffff; font-weight: bold; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-size: 15px; box-shadow: 0 2px 4px rgba(126,34,206,0.2);">
            View Ticket in Portal &rarr;
          </a>
        </div>

        <div style="margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 12px; color: #94a3b8; text-align: center;">
          TicketGenie Automated Enterprise Service Desk • <a href="{frontend_url}" style="color: #7e22ce; text-decoration: none;">{frontend_url}</a>
        </div>
      </div>
    </body>
    </html>
    """

    return send_email(to_email=recipient_email, subject=subject, body_html=body_html)


def send_ticket_status_updated_email(
    ticket: dict, old_status: str, new_status: str, recipient_email: str
) -> bool:
    """Send email notification when a ticket's status changes."""
    ticket_id = ticket.get("id", "HD-1000")
    title = ticket.get("title", "Support Request")
    frontend_url = get_frontend_url()
    ticket_url = f"{frontend_url}/tickets/{ticket_id}"

    subject = f"[TicketGenie] Status Update - Ticket #{ticket_id}: {new_status}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="border-bottom: 2px solid #3b82f6; padding-bottom: 16px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
          <h2 style="color: #1e40af; margin: 0; font-size: 22px;">Ticket Status Update</h2>
          <span style="background: #dbeafe; color: #1e40af; padding: 4px 12px; border-radius: 16px; font-weight: bold; font-size: 13px;">{new_status}</span>
        </div>

        <p style="font-size: 16px; color: #334155;">Hello,</p>
        <p style="font-size: 15px; color: #334155; line-height: 1.6;">
          The status of your support ticket <strong>#{ticket_id}</strong> (<em>"{title}"</em>) has been updated.
        </p>

        <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 6px; margin: 20px 0;">
          <p style="margin: 0; font-size: 15px; color: #1e3a8a;">
            <strong>Previous Status:</strong> {old_status}<br>
            <strong>New Status:</strong> <span style="color: #2563eb; font-weight: bold;">{new_status}</span>
          </p>
        </div>

        <div style="margin-top: 28px; text-align: center;">
          <a href="{ticket_url}" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-size: 15px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">
            View Updated Ticket &rarr;
          </a>
        </div>

        <div style="margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 12px; color: #94a3b8; text-align: center;">
          TicketGenie Automated Enterprise Service Desk • <a href="{frontend_url}" style="color: #2563eb; text-decoration: none;">{frontend_url}</a>
        </div>
      </div>
    </body>
    </html>
    """

    return send_email(to_email=recipient_email, subject=subject, body_html=body_html)


def send_ticket_comment_email(
    ticket: dict, comment: dict, recipient_email: str
) -> bool:
    """Send email notification when a new comment/message is added to a ticket."""
    ticket_id = ticket.get("id", "HD-1000")
    title = ticket.get("title", "Support Request")
    sender_role = comment.get("sender_role", "Support Specialist")
    message = comment.get("message", "")
    created_at = comment.get("createdAt", "")
    frontend_url = get_frontend_url()
    ticket_url = f"{frontend_url}/tickets/{ticket_id}"

    subject = f"[TicketGenie] New Message on Ticket #{ticket_id}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="border-bottom: 2px solid #10b981; padding-bottom: 16px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
          <h2 style="color: #065f46; margin: 0; font-size: 22px;">New Ticket Message</h2>
          <span style="background: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 16px; font-weight: bold; font-size: 13px;">#{ticket_id}</span>
        </div>

        <p style="font-size: 16px; color: #334155;">Hello,</p>
        <p style="font-size: 15px; color: #334155; line-height: 1.6;">
          A new message was posted on your ticket <strong>#{ticket_id}</strong> (<em>"{title}"</em>) by <strong>{sender_role}</strong>.
        </p>

        <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; border-radius: 6px; margin: 20px 0;">
          <div style="font-size: 12px; color: #047857; font-weight: bold; margin-bottom: 6px;">
            {sender_role} • {created_at}
          </div>
          <p style="margin: 0; font-size: 14px; color: #0f172a; white-space: pre-wrap; line-height: 1.5;">{message}</p>
        </div>

        <div style="margin-top: 28px; text-align: center;">
          <a href="{ticket_url}" style="display: inline-block; background-color: #10b981; color: #ffffff; font-weight: bold; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-size: 15px; box-shadow: 0 2px 4px rgba(16,185,129,0.2);">
            Reply in Portal &rarr;
          </a>
        </div>

        <div style="margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 12px; color: #94a3b8; text-align: center;">
          TicketGenie Automated Enterprise Service Desk • <a href="{frontend_url}" style="color: #10b981; text-decoration: none;">{frontend_url}</a>
        </div>
      </div>
    </body>
    </html>
    """

    return send_email(to_email=recipient_email, subject=subject, body_html=body_html)
