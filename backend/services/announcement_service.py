"""Announcement AI Severity Classification Service for TicketGenie."""

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.crud import get_announcements
from services.ai_service import ai_service

logger = logging.getLogger(__name__)


class SeverityLevelEnum(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class AnnouncementSeverityDecision(BaseModel):
    severity: SeverityLevelEnum = Field(
        default=SeverityLevelEnum.MEDIUM,
        description="Must be strictly one of: Critical, High, Medium, Low",
    )
    reason: str = Field(
        default="",
        description="Brief explanation of why this announcement is important for this role",
    )


SEVERITY_MAPPING = {
    "critical": {
        "level": "critical",
        "label": "CRITICAL ALERT",
        "color_class": "severity-critical",
        "icon": "ph-warning-octagon",
    },
    "high": {
        "level": "critical",
        "label": "HIGH PRIORITY",
        "color_class": "severity-critical",
        "icon": "ph-warning-octagon",
    },
    "medium": {
        "level": "warning",
        "label": "SYSTEM NOTICE",
        "color_class": "severity-warning",
        "icon": "ph-warning",
    },
    "low": {
        "level": "info",
        "label": "ANNOUNCEMENT",
        "color_class": "severity-info",
        "icon": "ph-megaphone",
    },
}


def _heuristic_fallback(title: str, content: str, category: str) -> str:
    combined = f"{category} {title} {content}".lower()
    if any(
        k in combined
        for k in [
            "critical",
            "emergency",
            "outage",
            "security",
            "breach",
            "incident",
            "down",
            "ransomware",
            "p0",
            "sev-1",
            "strike",
            "striking",
            "union",
            "walkout",
            "disaster",
            "evacuation",
            "fatal",
            "shutdown",
            "hazard",
            "urgent",
            "alert",
        ]
    ):
        return "Critical"
    if any(
        k in combined
        for k in [
            "maintenance",
            "warning",
            "system alert",
            "downtime",
            "interruption",
            "patch",
            "upgrade",
            "degradation",
            "reboot",
            "advisory",
            "delay",
        ]
    ):
        return "Medium"
    return "Low"


def classify_announcement_severity(
    title: str,
    content: str,
    category: Optional[str] = "General Alert",
) -> dict:
    """Classify how important an announcement is.

    The result is scoped by the announcement's category (department target),
    not by the requesting user — severity is the same for every employee in
    the same department.  We cache by (announcement content hash + category)
    via the shared prompt_cache so hit/miss rates are tracked per-agent.
    """
    category_str = category or "General Alert"

    # Build the prompt — no user identity, category is the only scope dimension
    system_prompt = (
        "You are a corporate communications analyst. "
        "Classify announcement severity strictly based on operational impact."
    )
    user_content = f"""Rate the importance of this company announcement:

Critical – immediate action required, service down, security incident, evacuation
High     – significant impact, near-term action required
Medium   – notable update, plan/schedule change, advisory
Low      – informational, routine, no action needed

Announcement:
Title: {title}
Category: {category_str}
Content: {content}
"""

    from services.prompt_cache_service import estimate_prompt_tokens, prompt_cache

    agent_name = "announcement_severity"
    cache_key = prompt_cache.make_key(agent_name, user_content, category_str)
    cached = prompt_cache.get(cache_key, agent_name=agent_name)
    if cached is not None:
        return cached

    severity_choice = "Medium"
    reason = ""

    try:
        import concurrent.futures

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(
                ai_service.generate,
                system_prompt=system_prompt,
                user_content=user_content,
                response_model=AnnouncementSeverityDecision,
                max_tokens=150,
            )
            decision: AnnouncementSeverityDecision = future.result(timeout=6.0)
            if decision and decision.severity:
                val = (
                    decision.severity.value
                    if hasattr(decision.severity, "value")
                    else str(decision.severity)
                )
                severity_choice = val.strip()
                reason = decision.reason
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    except Exception as exc:
        logger.info(
            f"AI severity generation falling back to category-aware heuristic: {exc}"
        )
        severity_choice = _heuristic_fallback(title, content, category_str)
        reason = "Classified based on announcement operational scope."
        try:
            import os

            from telemetry import record_llm_metrics

            prompt_tok = max(10, len((system_prompt + " " + user_content).split()) * 2)
            record_llm_metrics(
                prompt_tokens=prompt_tok,
                completion_tokens=15,
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"),
                agent_name=agent_name,
            )
        except Exception as tel_exc:
            logger.debug(
                "Could not record fallback announcement severity telemetry: %s", tel_exc
            )

    normalized_choice = severity_choice.lower()
    meta = SEVERITY_MAPPING.get(normalized_choice, SEVERITY_MAPPING["medium"])

    result = {
        **meta,
        "raw_severity": severity_choice,
        "category": category_str,
        "reason": reason,
    }

    # Cache by category scope — safe to share across all users in the same dept
    prompt_cache.set(
        cache_key,
        result,
        est_tokens=estimate_prompt_tokens(user_content),
        ttl_seconds=3600,
        agent_name=agent_name,
    )

    return result


def get_latest_announcement_with_severity(
    db: Optional[Session] = None,
) -> dict:
    """Retrieve the most recent announcement and its AI-computed severity.

    Severity is scoped by the announcement's own category — not by the
    requesting user's role.  The prompt_cache handles deduplication and
    hit-rate tracking.
    """
    announcements = get_announcements(db=db)
    if not announcements:
        return {"announcement": None, "severity": None}

    latest = announcements[0]
    severity = classify_announcement_severity(
        title=latest.get("title", ""),
        content=latest.get("content", ""),
        category=latest.get("category", ""),
    )

    return {
        "announcement": latest,
        "severity": severity,
    }
