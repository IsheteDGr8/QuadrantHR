"""closedai-hr physical layout + logical entity aliases.

Skills and prompts often name logical entities (leave_requests, policies).
Those live inside a smaller set of physical Cosmos containers, distinguished
by `recordType`. This module maps names so query_cosmos still works either way.
"""

from __future__ import annotations

import re
from typing import Optional

PHYSICAL_CONTAINERS = frozenset({
    "employees",
    "employee_records",
    "org",
    "reference",
    "recruiting",
    "candidates",
    "operations",
    "governance_logs",
    "analytics",
    "survey_responses",
})

# entity name -> physical container
ENTITY_TO_PHYSICAL: dict[str, str] = {
    "employees": "employees",
    "pay_statements": "employee_records",
    "compensation_records": "employee_records",
    "bonus_payouts": "employee_records",
    "equity_grants": "employee_records",
    "benefits_elections": "employee_records",
    "leave_requests": "employee_records",
    "leave_balances": "employee_records",
    "timesheets": "employee_records",
    "performance_reviews": "employee_records",
    "goals": "employee_records",
    "feedback": "employee_records",
    "pips": "employee_records",
    "recognition_awards": "employee_records",
    "employee_skills": "employee_records",
    "course_enrollments": "employee_records",
    "development_plans": "employee_records",
    "policy_acknowledgments": "employee_records",
    "work_authorizations": "employee_records",
    "assets": "employee_records",
    "documents": "employee_records",
    "consent_records": "employee_records",
    "er_cases": "employee_records",
    "disciplinary_actions": "employee_records",
    "accommodation_requests": "employee_records",
    "internal_mobility": "employee_records",
    "onboarding_checklists": "employee_records",
    "offboarding_checklists": "employee_records",
    "exit_interviews": "employee_records",
    "hr_tickets": "employee_records",
    "departments": "org",
    "locations": "org",
    "job_families": "org",
    "jobs": "org",
    "compensation_bands": "org",
    "positions": "org",
    "succession_plans": "org",
    "policies": "reference",
    "leave_policies": "reference",
    "benefits_plans": "reference",
    "pay_groups": "reference",
    "skills_taxonomy": "reference",
    "learning_courses": "reference",
    "document_templates": "reference",
    "vendors": "reference",
    "review_cycles": "reference",
    "surveys": "reference",
    "compliance_requirements": "reference",
    "data_governance_policies": "reference",
    "data_retention_schedules": "reference",
    "knowledge_articles": "reference",
    "ai_model_registry": "reference",
    "data_asset_catalog": "reference",
    "job_requisitions": "recruiting",
    "applications": "recruiting",
    "interviews": "recruiting",
    "offers": "recruiting",
    "candidates": "candidates",
    "payroll_runs": "operations",
    "compliance_audits": "operations",
    "background_checks": "operations",
    "dsar_requests": "operations",
    "integrations": "operations",
    "data_access_logs": "governance_logs",
    "ai_usage_logs": "governance_logs",
    "data_quality_issues": "governance_logs",
    "org_snapshots": "analytics",
    "engagement_snapshots": "analytics",
    "workforce_plans": "analytics",
    "survey_responses": "survey_responses",
}

# Old closedai-db names that still show up in skills/prompts.
LEGACY_ALIASES: dict[str, str] = {
    "applicants": "candidates",
    "payroll_cases": "payroll_runs",
    "benefits_catalog": "benefits_plans",
    "asset_policies": "policies",
}


def resolve_container(name: Optional[str], default: str = "employees") -> tuple[str, Optional[str]]:
    """Return (physical_container, recordType_filter_or_None)."""
    raw = (name or default or "employees").strip()
    raw = LEGACY_ALIASES.get(raw, raw)
    if raw in PHYSICAL_CONTAINERS:
        return raw, None
    physical = ENTITY_TO_PHYSICAL.get(raw)
    if physical:
        # employees/candidates physical containers hold a single entity type
        if physical == raw:
            return physical, None
        return physical, raw
    return raw, None


def inject_record_type(query: str, record_type: Optional[str]) -> str:
    if not record_type:
        return query
    if re.search(r"recordType", query, re.I):
        return query
    q = query.strip().rstrip(";")
    if re.search(r"\bWHERE\b", q, re.I):
        return re.sub(r"\bWHERE\b", f"WHERE c.recordType = '{record_type}' AND ", q, count=1, flags=re.I)
    if re.search(r"\bFROM\s+c\b", q, re.I):
        return re.sub(r"(\bFROM\s+c\b)", rf"\1 WHERE c.recordType = '{record_type}'", q, count=1, flags=re.I)
    return q


def layout_help_text() -> str:
    by_phys: dict[str, list[str]] = {p: [] for p in sorted(PHYSICAL_CONTAINERS)}
    for entity, phys in ENTITY_TO_PHYSICAL.items():
        if entity != phys:
            by_phys.setdefault(phys, []).append(entity)
    lines = [
        "Physical containers in closedai-hr:",
        *[f"- {p}" for p in sorted(PHYSICAL_CONTAINERS)],
        "",
        "Logical entity names still work as container_name; they map to a physical",
        "container and filter c.recordType automatically. Examples:",
        "- leave_requests -> employee_records (recordType=leave_requests)",
        "- policies -> reference (recordType=policies)",
        "- payroll_runs -> operations (recordType=payroll_runs)",
        "- job_requisitions -> recruiting (recordType=job_requisitions)",
        "",
        "Entities per physical container:",
    ]
    for phys in sorted(by_phys):
        ents = by_phys[phys] or [phys]
        lines.append(f"- {phys}: {', '.join(ents)}")
    return "\n".join(lines)
