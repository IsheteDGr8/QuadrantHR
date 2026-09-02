"""Role & Department Scoped AI-Visual Generated Daily Summary Email Digest Service."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models_db import DepartmentUserDB, TicketDB, UserProfileDB
from services.email_service import get_frontend_url, get_smtp_config, send_email

logger = logging.getLogger("ticketgenie.daily_digest")
tracer = trace.get_tracer("ticketgenie.daily_digest")


def resolve_admin_recipients(session: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Resolve admin recipients with their respective department scope & role.
    Returns list of dicts:
    [
        {"email": "HR1@tenant.com", "role": "HR Admin", "department": "HR Team"},
        {"email": "IT1@tenant.com", "role": "IT Admin", "department": "IT Team"},
        {"email": "Admin1@tenant.com", "role": "Admin", "department": None} # None = Organization-wide
    ]
    """
    env_emails = os.getenv("ADMIN_DIGEST_EMAILS", "").strip()
    if env_emails:
        recipients = []
        for raw in env_emails.split(","):
            part = raw.strip()
            if not part:
                continue
            if ":" in part:
                email, dept = part.split(":", 1)
                recipients.append(
                    {
                        "email": email.strip(),
                        "role": "Admin",
                        "department": dept.strip(),
                    }
                )
            elif "@" in part:
                recipients.append({"email": part, "role": "Admin", "department": None})
        if recipients:
            return recipients

    should_close = False
    if session is None:
        session = SessionLocal()
        should_close = True

    recipients_map: Dict[str, Dict[str, Any]] = {}
    try:
        # 1. Query department_users with admin / lead roles
        dept_admins = (
            session.query(DepartmentUserDB)
            .filter(
                or_(
                    func.lower(DepartmentUserDB.role).contains("admin"),
                    func.lower(DepartmentUserDB.role).contains("super"),
                    func.lower(DepartmentUserDB.role).contains("lead"),
                    func.lower(DepartmentUserDB.role).contains("operations"),
                    func.lower(DepartmentUserDB.role).contains("management"),
                )
            )
            .all()
        )
        for u in dept_admins:
            email = (u.user_email or "").strip()
            if email and "@" in email:
                role = u.role or "Admin"
                dept = u.department_name
                # Super admins or upper executive management get full organization digest (department = None)
                if (
                    "super" in role.lower()
                    or "executive" in (dept or "").lower()
                    or "upper" in (dept or "").lower()
                ):
                    dept = None

                recipients_map[email.lower()] = {
                    "email": email,
                    "role": role,
                    "department": dept,
                }

        # 2. Query user_profiles for additional admins
        user_admins = (
            session.query(UserProfileDB)
            .filter(
                or_(
                    func.lower(UserProfileDB.role).contains("admin"),
                    func.lower(UserProfileDB.role).contains("super"),
                    func.lower(UserProfileDB.role).contains("operations"),
                )
            )
            .all()
        )
        for prof in user_admins:
            email = (prof.email or "").strip()
            if email and "@" in email and email.lower() not in recipients_map:
                role = prof.role or "Admin"
                dept = prof.department
                if (
                    "super" in role.lower()
                    or "executive" in (dept or "").lower()
                    or "upper" in (dept or "").lower()
                ):
                    dept = None

                recipients_map[email.lower()] = {
                    "email": email,
                    "role": role,
                    "department": dept,
                }

    except Exception as err:
        logger.warning(f"Error querying admin recipients from database: {err}")
    finally:
        if should_close:
            session.close()

    result = list(recipients_map.values())

    # Fallback to configured SMTP user if no admin recipients found
    if not result:
        smtp_cfg = get_smtp_config()
        fallback = smtp_cfg.get("from_email") or smtp_cfg.get("user")
        if fallback and "@" in fallback:
            result.append({"email": fallback, "role": "Admin", "department": None})

    return result


def generate_ai_shift_summary(
    tickets: List[Dict[str, Any]], department: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use Azure OpenAI / LLM to analyze active tickets in SQL DB and generate an AI-Visual Shift Analysis.
    The AI model dynamically determines visual theme colors, status badges, progress bar ratios, and spotlight insights.
    """
    endpoint = os.getenv("GROUP1OPENAIENDPOINT", "").strip()
    api_key = os.getenv("GROUP1OPENAIAPIKEY", "").strip()

    dept_label = f"[{department}]" if department else "[Organization-Wide]"
    open_tickets = [
        t
        for t in tickets
        if (t.get("status") or "").strip().lower() in ("open", "in progress", "pending")
    ]

    if not open_tickets:
        return {
            "executive_brief": f"All {dept_label} service desk queues are currently clear with zero pending open tickets.",
            "recommendations": [
                "Routine queue health monitoring",
                "Knowledge base article review",
            ],
            "risk_alert": f"Low risk - zero {dept_label} backlog.",
            "visual_theme": "emerald_clean",
            "visual_badge": "🟢 QUEUE CLEAR",
            "visual_progress_urgent_pct": 0,
            "visual_progress_medium_pct": 0,
            "visual_progress_low_pct": 100,
            "ai_spotlight_callout": "✨ AI System Report: All support queues are operating at peak efficiency with zero active backlog.",
        }

    # Prepare lightweight payload for AI prompt
    ticket_summaries = []
    for t in open_tickets[:15]:
        ticket_summaries.append(
            f"#{t.get('id')}: [{t.get('priority')}] {t.get('title')} (Dept: {t.get('department')}, Category: {t.get('category')})"
        )
    tickets_text = "\n".join(ticket_summaries)

    prompt_messages = [
        {
            "role": "system",
            "content": (
                f"You are TicketGenie AI Operations Analyst & Visual Controller for {dept_label}. "
                "Analyze today's support tickets from the database and generate an AI-Visual Shift Report. "
                "Return strictly valid JSON with keys:\n"
                "- 'executive_brief': A 2-sentence executive summary of today's workload and main issue clusters.\n"
                "- 'recommendations': A list of 3 short actionable recommendations for the team lead today.\n"
                "- 'risk_alert': A 1-sentence risk warning highlighting bottlenecks or urgent outages.\n"
                "- 'visual_theme': One of ['critical_red', 'warning_amber', 'purple_gradient', 'emerald_clean'] based on overall workload threat level.\n"
                "- 'visual_badge': Short status pill text with emoji (e.g. '🔥 HIGH QUEUE CONGESTION', '⚠️ ATTENTION REQUIRED', '⚡ OPTIMAL FLOW').\n"
                "- 'visual_progress_urgent_pct': Integer 0-100 representing calculated % width of urgent priority work.\n"
                "- 'visual_progress_medium_pct': Integer 0-100 representing calculated % width of medium priority work.\n"
                "- 'visual_progress_low_pct': Integer 0-100 representing calculated % width of low priority work.\n"
                "- 'ai_spotlight_callout': A 1-2 sentence AI insight highlighting an interesting pattern, category spike, or automation recommendation detected in this SQL dataset."
            ),
        },
        {
            "role": "user",
            "content": f"Active {dept_label} Tickets ({len(open_tickets)} total):\n{tickets_text}",
        },
    ]

    if endpoint and api_key:
        try:
            url = endpoint.rstrip("/")
            if not url.endswith("/chat/completions") and not url.endswith("/responses"):
                url = f"{url}/chat/completions"

            req_body = json.dumps(
                {
                    "messages": prompt_messages,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=req_body,
                headers={
                    "Content-Type": "application/json",
                    "api-key": api_key,
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # Record LLM Token & Cost Telemetry
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                if prompt_tokens or completion_tokens:
                    try:
                        from telemetry import record_llm_metrics

                        record_llm_metrics(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            model="azure-openai-gpt-4o",
                            agent_name=f"daily_digest_{department or 'org'}",
                        )
                    except Exception as t_err:
                        logger.warning(
                            f"Failed to record daily digest LLM metrics: {t_err}"
                        )

                logger.info(
                    f"Successfully generated AI Shift Summary & Visuals for {dept_label} via Azure OpenAI."
                )
                return parsed
        except Exception as err:
            logger.warning(
                f"Azure OpenAI call failed for daily digest ({err}). Using fallback AI summary & visuals."
            )

    # Rule-based fallback summary & visual generation
    urgent_count = len(
        [t for t in open_tickets if t.get("priority") in ("High", "Urgent", "Critical")]
    )
    total_open = max(len(open_tickets), 1)
    urgent_pct = min(100, int((urgent_count / total_open) * 100))
    medium_pct = min(100 - urgent_pct, 60)
    low_pct = max(0, 100 - urgent_pct - medium_pct)

    theme = (
        "critical_red"
        if urgent_count >= 3
        else ("warning_amber" if urgent_count > 0 else "purple_gradient")
    )
    badge = (
        "🔥 HIGH QUEUE CONGESTION"
        if urgent_count >= 3
        else ("⚠️ ATTENTION REQUIRED" if urgent_count > 0 else "⚡ ACTIVE QUEUE")
    )

    return {
        "executive_brief": f"Active {dept_label} workload consists of {len(open_tickets)} open tickets, with {urgent_count} high-priority issues requiring immediate attention.",
        "recommendations": [
            f"Prioritize the {urgent_count} urgent ticket(s) in the {dept_label} queue.",
            "Review AI-flagged tickets requiring human triage.",
            "Ensure ticket status updates are logged before end-of-shift.",
        ],
        "risk_alert": f"{dept_label} high priority workload is at {urgent_count} item(s)."
        if urgent_count > 0
        else f"Normal {dept_label} queue operations.",
        "visual_theme": theme,
        "visual_badge": badge,
        "visual_progress_urgent_pct": urgent_pct,
        "visual_progress_medium_pct": medium_pct,
        "visual_progress_low_pct": low_pct,
        "ai_spotlight_callout": f"✨ AI Pattern Analysis: {urgent_count} out of {len(open_tickets)} open tasks require urgent technician response today.",
    }


def generate_daily_digest_data(
    department: Optional[str] = None, session: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Compile tickets summary, AI analysis, and visual metrics scoped for a specific department or full organization.
    """
    should_close = False
    if session is None:
        session = SessionLocal()
        should_close = True

    try:
        # All tickets from SQL DB
        all_tickets = session.query(TicketDB).all()
        tickets_dicts = [t.to_dict() for t in all_tickets]

        # Filter by department if specified
        if department:
            dept_lower = department.lower().strip()
            tickets_dicts = [
                t
                for t in tickets_dicts
                if dept_lower in (t.get("department") or "").lower()
            ]

        # Filter strictly by status
        open_tickets = [
            t
            for t in tickets_dicts
            if (t.get("status") or "").strip().lower() == "open"
        ]
        in_progress_tickets = [
            t
            for t in tickets_dicts
            if (t.get("status") or "").strip().lower() == "in progress"
        ]
        resolved_tickets = [
            t
            for t in tickets_dicts
            if (t.get("status") or "").strip().lower() in ("resolved", "closed")
        ]

        urgent_tickets = [
            t
            for t in open_tickets
            if t.get("priority") in ("High", "Urgent", "Critical")
        ]
        needs_review = [t for t in open_tickets if t.get("needs_human_review") is True]

        # Calculate newly created tickets in the last 24h
        now = datetime.now()
        yesterday_iso = (now - timedelta(hours=24)).isoformat()
        new_tickets = [
            t for t in open_tickets if (t.get("createdAt") or "") >= yesterday_iso
        ]

        # Department breakdown
        dept_counts: Dict[str, int] = {}
        for t in open_tickets:
            dept = t.get("department") or "General IT"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

        # Priority breakdown
        priority_counts: Dict[str, int] = {
            "Critical/Urgent": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
        }
        for t in open_tickets:
            p = t.get("priority") or "Medium"
            if p in ("Critical", "Urgent", "High"):
                priority_counts["Critical/Urgent"] += 1
            elif p == "Medium":
                priority_counts["Medium"] += 1
            else:
                priority_counts["Low"] += 1

        # AI Shift & Visual Analysis scoped for this department
        ai_summary = generate_ai_shift_summary(open_tickets, department=department)

        return {
            "timestamp": now.strftime("%B %d, %Y - %I:%M %p"),
            "department": department or "Organization-Wide",
            "total_tickets": len(tickets_dicts),
            "open_count": len(open_tickets),
            "in_progress_count": len(in_progress_tickets),
            "resolved_count": len(resolved_tickets),
            "urgent_count": len(urgent_tickets),
            "needs_review_count": len(needs_review),
            "new_24h_count": len(new_tickets),
            "dept_counts": dept_counts,
            "priority_counts": priority_counts,
            "urgent_tickets": urgent_tickets[:5],
            "needs_review_tickets": needs_review[:5],
            "ai_summary": ai_summary,
        }
    finally:
        if should_close:
            session.close()


def send_daily_admin_digest() -> Dict[str, Any]:
    """
    Generate and dispatch AI-Visual role & department scoped daily summary email digests to all IT/HR/Executive Admins.
    Returns result metadata dictionary.
    """
    with tracer.start_as_current_span("daily_digest.send_daily_admin_digest") as span:
        logger.info(
            "Starting AI-Visual Role & Department Scoped Daily Admin Digest generation..."
        )
        recipients = resolve_admin_recipients()
        if not recipients:
            logger.warning("No admin recipients resolved for daily digest.")
            span.set_attribute("digest.status", "skipped")
            return {
                "status": "skipped",
                "reason": "No admin recipients found",
                "recipients": [],
            }

        frontend_url = get_frontend_url()
        admin_dashboard_url = f"{frontend_url}/admin"

        dispatched_count = 0
        errors: List[str] = []

        # Cache digest data by department scope to avoid duplicate DB/AI queries
        digest_cache: Dict[str, Dict[str, Any]] = {}

        for rec in recipients:
            recipient_email = rec["email"]
            dept_scope = rec.get("department")  # None = Full Org

            cache_key = dept_scope or "org"
            if cache_key not in digest_cache:
                digest_cache[cache_key] = generate_daily_digest_data(
                    department=dept_scope
                )

            digest_data = digest_cache[cache_key]
            dept_display = digest_data["department"]
            formatted_date = digest_data["timestamp"]
            open_count = digest_data["open_count"]
            urgent_count = digest_data["urgent_count"]
            needs_review_count = digest_data["needs_review_count"]
            new_24h_count = digest_data["new_24h_count"]
            ai_summary = digest_data["ai_summary"]

            # AI-driven visual parameters
            ai_badge = ai_summary.get("visual_badge", f"✨ {dept_display}")
            urgent_pct = ai_summary.get("visual_progress_urgent_pct", 30)
            medium_pct = ai_summary.get("visual_progress_medium_pct", 50)
            low_pct = ai_summary.get("visual_progress_low_pct", 20)
            ai_spotlight = ai_summary.get("ai_spotlight_callout", "")

            subject = f"✨ [TicketGenie] {dept_display} Digest - {open_count} Active Tasks ({urgent_count} Urgent)"

            # AI Recommendations HTML Bullet Points
            recommendations_html = ""
            for rec_item in ai_summary.get("recommendations", []):
                recommendations_html += (
                    f"<li style='margin-bottom: 6px; color: #334155;'>{rec_item}</li>"
                )

            # Build Urgent Tickets HTML rows
            urgent_rows_html = ""
            if digest_data["urgent_tickets"]:
                for t in digest_data["urgent_tickets"]:
                    t_id = t.get("id")
                    t_title = t.get("title")
                    t_dept = t.get("department", "IT")
                    t_url = f"{frontend_url}/tickets/{t_id}"
                    urgent_rows_html += f"""
                    <tr>
                      <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #dc2626;">#{t_id}</td>
                      <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{t_title}</td>
                      <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; color: #64748b;">{t_dept}</td>
                      <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">
                        <a href="{t_url}" style="color: #7e22ce; font-weight: bold; text-decoration: none; font-size: 13px;">View &rarr;</a>
                      </td>
                    </tr>
                    """
            else:
                urgent_rows_html = """
                <tr>
                  <td colspan="4" style="padding: 12px; text-align: center; color: #10b981; font-weight: bold;">
                    🎉 Zero High/Urgent priority tickets pending in this queue!
                  </td>
                </tr>
                """

            body_html = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px;">
              <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 36px; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
                
                <!-- Header Banner -->
                <div style="border-bottom: 3px solid #7e22ce; padding-bottom: 20px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;">
                  <div>
                    <h2 style="color: #7e22ce; margin: 0; font-size: 24px; font-weight: 800;">TicketGenie Daily Summary</h2>
                    <span style="font-size: 13px; color: #64748b;">{formatted_date}</span>
                  </div>
                  <span style="background: linear-gradient(135deg, #7e22ce, #9333ea); color: #ffffff; padding: 6px 16px; border-radius: 20px; font-weight: bold; font-size: 13px; box-shadow: 0 2px 6px rgba(126,34,206,0.3);">
                    {ai_badge}
                  </span>
                </div>

                <!-- AI Executive Briefing Callout Card -->
                <div style="background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%); border: 1px solid #d8b4fe; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                  <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 18px; margin-right: 8px;">🤖</span>
                    <strong style="color: #6b21a8; font-size: 15px;">AI {dept_display} Workload Analysis</strong>
                  </div>
                  <p style="margin: 0 0 12px 0; font-size: 14px; color: #4c1d95; line-height: 1.6;">
                    {ai_summary.get("executive_brief")}
                  </p>
                  
                  <!-- AI Generated Spotlight Callout -->
                  <div style="background: #ffffff; border-radius: 8px; padding: 12px 16px; border-left: 4px solid #7e22ce; margin-bottom: 12px; font-size: 13px; color: #581c87;">
                    {ai_spotlight}
                  </div>

                  <div style="background: #ffffff; border-radius: 8px; padding: 12px 16px; border-left: 4px solid #9333ea;">
                    <div style="font-size: 12px; font-weight: bold; color: #7e22ce; text-transform: uppercase; margin-bottom: 6px;">Recommended Focus Areas:</div>
                    <ul style="margin: 0; padding-left: 18px; font-size: 13px;">
                      {recommendations_html}
                    </ul>
                  </div>
                  <div style="margin-top: 10px; font-size: 12px; color: #991b1b; background: #fef2f2; padding: 8px 12px; border-radius: 6px; border: 1px solid #fecaca;">
                    ⚠️ <strong>Queue Status:</strong> {ai_summary.get("risk_alert")}
                  </div>
                </div>

                <!-- AI Generated Visual Progress Bar for Workload Distribution -->
                <div style="margin-bottom: 28px;">
                  <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; color: #475569; margin-bottom: 6px;">
                    <span>AI Visual Progress Bar ({dept_display})</span>
                    <span>{open_count} Active Open Tasks</span>
                  </div>
                  <div style="height: 16px; width: 100%; background: #e2e8f0; border-radius: 8px; overflow: hidden; display: flex; box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);">
                    <div style="width: {urgent_pct}%; background: linear-gradient(90deg, #ef4444, #f87171);" title="Urgent ({urgent_pct}%)"></div>
                    <div style="width: {medium_pct}%; background: linear-gradient(90deg, #f59e0b, #fbbf24);" title="Medium ({medium_pct}%)"></div>
                    <div style="width: {low_pct}%; background: linear-gradient(90deg, #10b981, #34d399);" title="Low ({low_pct}%)"></div>
                  </div>
                  <div style="display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-top: 6px;">
                    <span>🔴 Urgent ({urgent_pct}%)</span>
                    <span>🟡 Medium ({medium_pct}%)</span>
                    <span>🟢 Low ({low_pct}%)</span>
                  </div>
                </div>

                <!-- KPI Metric Cards Grid -->
                <div style="margin: 20px 0;">
                  <table style="width: 100%; border-collapse: separate; border-spacing: 10px 0;">
                    <tr>
                      <td style="width: 50%; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 10px; padding: 16px; text-align: center;">
                        <div style="font-size: 30px; font-weight: 800; color: #7e22ce;">{open_count}</div>
                        <div style="font-size: 12px; font-weight: bold; color: #6b21a8; text-transform: uppercase;">Active Open Tasks</div>
                      </td>
                      <td style="width: 50%; background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 16px; text-align: center;">
                        <div style="font-size: 30px; font-weight: 800; color: #dc2626;">{urgent_count}</div>
                        <div style="font-size: 12px; font-weight: bold; color: #991b1b; text-transform: uppercase;">Urgent Priority</div>
                      </td>
                    </tr>
                    <tr style="height: 10px;"></tr>
                    <tr>
                      <td style="width: 50%; background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 16px; text-align: center;">
                        <div style="font-size: 30px; font-weight: 800; color: #d97706;">{needs_review_count}</div>
                        <div style="font-size: 12px; font-weight: bold; color: #92400e; text-transform: uppercase;">Pending Human Review</div>
                      </td>
                      <td style="width: 50%; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 16px; text-align: center;">
                        <div style="font-size: 30px; font-weight: 800; color: #16a34a;">+{new_24h_count}</div>
                        <div style="font-size: 12px; font-weight: bold; color: #166534; text-transform: uppercase;">New in Last 24 Hours</div>
                      </td>
                    </tr>
                  </table>
                </div>

                <!-- High/Urgent Tickets Table -->
                <div style="margin-top: 28px;">
                  <h3 style="color: #0f172a; font-size: 16px; margin: 0 0 12px 0; border-left: 4px solid #dc2626; padding-left: 10px;">
                    🚨 Urgent Action Items ({urgent_count})
                  </h3>
                  <table style="width: 100%; border-collapse: collapse; font-size: 14px; background: #fafafa; border-radius: 8px;">
                    <thead>
                      <tr style="background: #f1f5f9; color: #475569; text-align: left; font-size: 12px;">
                        <th style="padding: 10px 12px; border-bottom: 1px solid #cbd5e1;">ID</th>
                        <th style="padding: 10px 12px; border-bottom: 1px solid #cbd5e1;">Title</th>
                        <th style="padding: 10px 12px; border-bottom: 1px solid #cbd5e1;">Department</th>
                        <th style="padding: 10px 12px; border-bottom: 1px solid #cbd5e1; text-align: right;">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {urgent_rows_html}
                    </tbody>
                  </table>
                </div>

                <!-- Call to Action Button -->
                <div style="margin-top: 36px; text-align: center;">
                  <a href="{admin_dashboard_url}" style="display: inline-block; background-color: #7e22ce; color: #ffffff; font-weight: bold; padding: 14px 36px; border-radius: 10px; text-decoration: none; font-size: 16px; box-shadow: 0 4px 12px rgba(126,34,206,0.3);">
                    Open {dept_display} Dashboard &rarr;
                  </a>
                </div>

                <!-- Footer -->
                <div style="margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 12px; color: #94a3b8; text-align: center;">
                  TicketGenie Automated AI Service Desk • <a href="{frontend_url}" style="color: #7e22ce; text-decoration: none;">{frontend_url}</a>
                </div>
              </div>
            </body>
            </html>
            """

            try:
                success = send_email(
                    to_email=recipient_email, subject=subject, body_html=body_html
                )
                if success:
                    dispatched_count += 1
                else:
                    errors.append(f"Failed to dispatch to {recipient_email}")
            except Exception as e:
                err_msg = str(e)
                logger.error(
                    f"Error sending daily digest to {recipient_email}: {err_msg}"
                )
                errors.append(f"{recipient_email}: {err_msg}")

        span.set_attribute("digest.dispatched_count", dispatched_count)
        return {
            "status": "success" if dispatched_count > 0 else "failed",
            "dispatched_count": dispatched_count,
            "recipients": [r["email"] for r in recipients],
            "recipient_details": recipients,
            "errors": errors,
        }
