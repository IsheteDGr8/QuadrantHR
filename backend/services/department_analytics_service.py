"""Calculated department-health analytics over persisted TicketGenie tickets."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models_db import TicketDB
from services.role_service import is_admin

SLA_HOURS = {"critical": 4, "high": 8, "medium": 24, "low": 72}
OPEN_STATUSES = {"open", "pending", "in progress", "in_progress"}
RESOLVED_STATUSES = {"resolved", "closed", "approved"}
DEPARTMENT_ALIASES = {
    "it operations": "IT Team",
    "it & technology": "IT Team",
    "hr & workplace operations": "HR Team",
    "finance & accounting": "Accounting Team",
    "upper executive management": "Upper Management",
    "executive governance": "Upper Management",
}


class AnalyticsAccessError(PermissionError):
    """Raised when a verified identity cannot access the requested scope."""


def resolve_analytics_department(
    current_user: dict, requested_department: Optional[str]
) -> Optional[str]:
    """Resolve analytics scope exclusively from the verified identity."""
    role = (current_user.get("role") or "").strip()
    is_admin_user = is_admin(role, current_user.get("is_dev", False))
    is_ticketer_user = role.casefold() == "ticketer"
    if not (is_admin_user or is_ticketer_user):
        raise AnalyticsAccessError(
            "Admin or Ticketer access is required for department analytics."
        )

    requested_department = normalize_department(requested_department)
    user_department = normalize_department(current_user.get("department"))
    if is_ticketer_user and not user_department:
        raise AnalyticsAccessError(
            "Ticketer accounts require a verified department assignment."
        )
    if not user_department or user_department == "Upper Management":
        return requested_department
    if requested_department and requested_department != user_department:
        raise AnalyticsAccessError(
            "Users may only view analytics for their assigned department."
        )
    return user_department


def normalize_department(department: Optional[str]) -> Optional[str]:
    value = (department or "").strip()
    if not value:
        return None
    return DEPARTMENT_ALIASES.get(value.lower(), value)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _ticket_duration_hours(ticket: TicketDB, now: datetime) -> float:
    created = _parse_datetime(ticket.createdAt) or now
    finished = _parse_datetime(ticket.updatedAt) if _is_resolved(ticket) else now
    return max(0.0, ((finished or now) - created).total_seconds() / 3600)


def _is_open(ticket: TicketDB) -> bool:
    return (ticket.status or "").strip().lower() in OPEN_STATUSES


def _is_resolved(ticket: TicketDB) -> bool:
    return (ticket.status or "").strip().lower() in RESOLVED_STATUSES


def _sla_target(ticket: TicketDB) -> int:
    return SLA_HOURS.get((ticket.priority or "medium").lower(), 24)


def _attention_score(ticket: TicketDB, now: datetime) -> tuple[float, list[str]]:
    priority = (ticket.priority or "Medium").lower()
    base = {"critical": 70, "high": 48, "medium": 24, "low": 10}.get(priority, 20)
    age_hours = _ticket_duration_hours(ticket, now)
    target = _sla_target(ticket)
    score = float(base) + min(35, (age_hours / target) * 22)
    reasons = [f"{ticket.priority or 'Medium'} priority"]

    if age_hours > target:
        score += 24
        reasons.append(f"SLA overdue by {round(age_hours - target)}h")
    elif age_hours > target * 0.75:
        score += 12
        reasons.append("SLA deadline approaching")
    if ticket.needs_human_review:
        score += 10
        reasons.append("AI requested human review")
    confidence = float(ticket.classification_confidence or 1)
    if confidence < 0.8:
        score += 6
        reasons.append("low routing confidence")
    return score, reasons


def get_department_health_analytics(
    db: Session,
    department: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Return grounded KPIs, trend series, issue signals, and attention ranking."""
    now = now or datetime.now().replace(microsecond=0)
    department = normalize_department(department)
    query = db.query(TicketDB)
    if department:
        query = query.filter(func.lower(TicketDB.department) == department.lower())
    tickets = query.all()

    open_tickets = [ticket for ticket in tickets if _is_open(ticket)]
    resolved_tickets = [ticket for ticket in tickets if _is_resolved(ticket)]
    recent_start = now - timedelta(days=30)
    previous_start = now - timedelta(days=60)
    recent = [
        ticket
        for ticket in tickets
        if (_parse_datetime(ticket.createdAt) or datetime.min) >= recent_start
    ]
    previous = [
        ticket
        for ticket in tickets
        if previous_start
        <= (_parse_datetime(ticket.createdAt) or datetime.min)
        < recent_start
    ]

    volume_change = round(
        ((len(recent) - len(previous)) / max(len(previous), 1)) * 100, 1
    )
    sla_population = [
        ticket for ticket in tickets if _is_open(ticket) or _is_resolved(ticket)
    ]
    sla_compliant = sum(
        1
        for ticket in sla_population
        if _ticket_duration_hours(ticket, now) <= _sla_target(ticket)
    )
    sla_rate = round((sla_compliant / max(len(sla_population), 1)) * 100, 1)
    resolution_hours = [
        _ticket_duration_hours(ticket, now) for ticket in resolved_tickets
    ]
    mttr = round(mean(resolution_hours), 1) if resolution_hours else 0.0
    critical_open = sum(
        1 for ticket in open_tickets if (ticket.priority or "").lower() == "critical"
    )
    overdue = sum(
        1
        for ticket in open_tickets
        if _ticket_duration_hours(ticket, now) > _sla_target(ticket)
    )
    backlog_ratio = len(open_tickets) / max(len(tickets), 1)
    health_score = round(
        max(
            0,
            min(
                100,
                sla_rate - (backlog_ratio * 24) - (critical_open * 3) - (overdue * 1.5),
            ),
        )
    )
    health_label = (
        "Healthy"
        if health_score >= 85
        else "Watch"
        if health_score >= 70
        else "At Risk"
    )

    trend_start = (now - timedelta(weeks=11)).date()
    trend_start -= timedelta(days=trend_start.weekday())
    weekly = defaultdict(lambda: {"created": 0, "resolved": 0})
    for ticket in tickets:
        created = _parse_datetime(ticket.createdAt)
        if created and created.date() >= trend_start:
            week = created.date() - timedelta(days=created.weekday())
            weekly[week.isoformat()]["created"] += 1
        resolved_at = (
            _parse_datetime(ticket.updatedAt) if _is_resolved(ticket) else None
        )
        if resolved_at and resolved_at.date() >= trend_start:
            week = resolved_at.date() - timedelta(days=resolved_at.weekday())
            weekly[week.isoformat()]["resolved"] += 1
    ticket_trends = []
    for offset in range(12):
        week = trend_start + timedelta(weeks=offset)
        values = weekly[week.isoformat()]
        ticket_trends.append(
            {
                "week": week.isoformat(),
                "label": week.strftime("%b %d"),
                "created": values["created"],
                "resolved": values["resolved"],
            }
        )

    current_issue_start = now - timedelta(days=14)
    prior_issue_start = now - timedelta(days=28)
    current_categories = Counter(
        ticket.category or "Other"
        for ticket in tickets
        if (_parse_datetime(ticket.createdAt) or datetime.min) >= current_issue_start
    )
    prior_categories = Counter(
        ticket.category or "Other"
        for ticket in tickets
        if prior_issue_start
        <= (_parse_datetime(ticket.createdAt) or datetime.min)
        < current_issue_start
    )
    open_categories = Counter(ticket.category or "Other" for ticket in open_tickets)
    emerging_issues = []
    for category, current_count in current_categories.most_common():
        prior_count = prior_categories.get(category, 0)
        change = round(((current_count - prior_count) / max(prior_count, 1)) * 100)
        if current_count >= 2 and (change > 0 or open_categories.get(category, 0) >= 2):
            emerging_issues.append(
                {
                    "category": category,
                    "current_count": current_count,
                    "previous_count": prior_count,
                    "change_pct": change,
                    "open_count": open_categories.get(category, 0),
                    "signal": "Rising" if change >= 25 else "Persistent",
                }
            )
    emerging_issues = emerging_issues[:5]

    ranked_attention = []
    for ticket in open_tickets:
        score, reasons = _attention_score(ticket, now)
        ranked_attention.append((score, ticket, reasons))
    ranked_attention.sort(key=lambda item: item[0], reverse=True)
    attention_queue = [
        {
            "id": ticket.id,
            "title": ticket.title,
            "priority": ticket.priority,
            "status": ticket.status,
            "category": ticket.category,
            "department": ticket.department,
            "age_hours": round(_ticket_duration_hours(ticket, now), 1),
            "attention_score": round(score),
            "reason": "; ".join(reasons),
            "is_synthetic": bool(ticket.is_synthetic),
        }
        for score, ticket, reasons in ranked_attention[:7]
    ]

    top_issue = (
        emerging_issues[0]["category"]
        if emerging_issues
        else "No dominant issue cluster"
    )
    brief = {
        "headline": f"{department or 'Enterprise'} is {health_label.lower()} with a health score of {health_score}.",
        "summary": (
            f"The queue received {len(recent)} tickets in the last 30 days ({volume_change:+.1f}% versus the prior period). "
            f"SLA compliance is {sla_rate:.1f}% with {len(open_tickets)} open tickets, {overdue} overdue, "
            f"and {critical_open} critical. The strongest emerging signal is {top_issue}."
        ),
        "recommendations": [
            recommendation
            for recommendation in [
                f"Resolve {attention_queue[0]['id']} first: {attention_queue[0]['reason']}."
                if attention_queue
                else None,
                f"Investigate the {top_issue} cluster and publish a proactive update."
                if emerging_issues
                else None,
                f"Rebalance ownership for {overdue} overdue tickets."
                if overdue
                else "Maintain the current SLA response cadence.",
            ]
            if recommendation
        ],
        "generated_at": now.isoformat(),
        "method": "Calculated from queue volume, SLA exposure, issue velocity, and ticket attention scores.",
    }

    synthetic_count = sum(1 for ticket in tickets if ticket.is_synthetic)
    data_mode = (
        "synthetic"
        if tickets and synthetic_count == len(tickets)
        else "mixed"
        if synthetic_count
        else "live"
    )
    return {
        "department": department or "All Departments",
        "data_mode": data_mode,
        "record_count": len(tickets),
        "synthetic_record_count": synthetic_count,
        "kpis": {
            "health_score": health_score,
            "health_label": health_label,
            "tickets_30d": len(recent),
            "volume_change_pct": volume_change,
            "open_backlog": len(open_tickets),
            "critical_open": critical_open,
            "overdue_open": overdue,
            "sla_compliance_pct": sla_rate,
            "mttr_hours": mttr,
        },
        "brief": brief,
        "ticket_trends": ticket_trends,
        "emerging_issues": emerging_issues,
        "attention_queue": attention_queue,
    }
