"""Explainable matching between proposed tickets and company announcements."""

from __future__ import annotations

import re
from typing import Iterable, Optional

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "already",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "can",
    "cannot",
    "company",
    "could",
    "create",
    "does",
    "employee",
    "from",
    "have",
    "help",
    "into",
    "just",
    "need",
    "not",
    "please",
    "problem",
    "request",
    "some",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "ticket",
    "unable",
    "user",
    "want",
    "with",
    "working",
    "would",
    "your",
}

TERM_ALIASES = {
    "emails": "email",
    "mail": "email",
    "outlook": "email",
    "wireless": "wifi",
    "wi-fi": "wifi",
    "networks": "network",
    "expenses": "expense",
    "reimbursement": "expense",
    "reimbursements": "expense",
    "maintaining": "maintenance",
    "issues": "issue",
    "problems": "issue",
}

INCIDENT_TERMS = {
    "closure",
    "degraded",
    "disruption",
    "down",
    "incident",
    "issue",
    "maintenance",
    "outage",
    "scheduled",
    "unavailable",
    "upgrade",
}

SERVICE_TERMS = {
    "email",
    "network",
    "payroll",
    "teams",
    "vpn",
    "wifi",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (text or "").lower())
    return {
        TERM_ALIASES.get(word, word)
        for word in words
        if len(word) >= 3 and word not in STOP_WORDS
    }


def find_matching_announcement(
    title: str,
    description: str,
    announcements: Iterable[dict],
) -> Optional[dict]:
    """Return the strongest credible announcement match, or ``None``."""
    ticket_terms = _tokens(f"{title} {description}")
    if not ticket_terms:
        return None

    best_match = None
    best_rank = 0.0

    for announcement in announcements:
        title_terms = _tokens(announcement.get("title", ""))
        all_terms = _tokens(
            f"{announcement.get('title', '')} {announcement.get('content', '')} "
            f"{announcement.get('category', '')}"
        )
        overlap = ticket_terms & all_terms
        if not overlap:
            continue

        has_incident_context = bool(all_terms & INCIDENT_TERMS)
        strong_single_term = bool(overlap & SERVICE_TERMS and has_incident_context)
        if len(overlap) < 2 and not strong_single_term:
            continue

        title_overlap = overlap & title_terms
        weighted_overlap = len(overlap) + (2 * len(title_overlap))
        rank = weighted_overlap / max(min(len(ticket_terms), 8), 2)
        if has_incident_context:
            rank += 0.2

        if rank > best_rank:
            best_rank = rank
            best_match = {
                "matched": True,
                "confidence": round(min(0.99, 0.55 + (rank * 0.2)), 2),
                "matched_terms": sorted(overlap),
                "announcement": announcement,
                "message": "This issue may already be addressed in a company announcement.",
            }

    try:
        import os

        from telemetry import record_llm_metrics

        prompt_tokens = max(15, len(ticket_terms) * 4 + 30)
        completion_tokens = 20 if best_match else 5
        record_llm_metrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"),
            agent_name="announcement_matcher",
        )
    except Exception:
        pass

    return best_match
