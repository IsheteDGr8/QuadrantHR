"""Super Admin & Governance API Router for TicketGenie."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from database.crud import (
    add_department_user,
    create_department,
    get_leave_tickets,
    list_department_users,
    list_departments,
    remove_department_user,
)
from services.jwt_verifier import verify_azure_user
from services.role_service import is_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: dict = Depends(verify_azure_user)):
    """Enforce that only Admin can create/modify roles and department assignments."""
    if not is_admin(current_user.get("role"), current_user.get("is_dev", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Admin can manage department role assignments.",
        )
    return current_user


require_super_admin = require_admin


class DepartmentCreateRequest(BaseModel):
    name: str
    queue_name: str
    description: Optional[str] = None


class DepartmentUserRequest(BaseModel):
    department_name: Optional[str] = None
    department: Optional[str] = None
    azure_object_id: Optional[str] = None
    object_id: Optional[str] = None
    role: Optional[str] = "Employee"
    name: Optional[str] = None
    email: Optional[str] = None
    user_email: Optional[str] = None


class SQLQueryRequest(BaseModel):
    query: str
    role: Optional[str] = None
    user_id: Optional[str] = None


@router.get("/departments")
def get_departments(current_user: dict = Depends(verify_azure_user)):
    return list_departments()


@router.post("/departments", status_code=201)
def handle_create_department(
    req: DepartmentCreateRequest,
    current_user: dict = Depends(verify_azure_user),
):
    require_admin(current_user)
    return create_department(req.name, req.queue_name, req.description)


@router.get("/departments/users")
def get_department_users(
    department_name: Optional[str] = None,
    current_user: dict = Depends(verify_azure_user),
):
    return list_department_users(department_name)


@router.post("/departments/users", status_code=201)
def assign_department_user(
    req: DepartmentUserRequest,
    current_user: dict = Depends(require_super_admin),
):
    oid = req.azure_object_id or req.object_id
    dept = req.department_name or req.department or "IT Engineering"
    user_email = req.user_email or req.email

    if not oid:
        raise HTTPException(
            status_code=400,
            detail="azure_object_id or object_id is required.",
        )

    return add_department_user(
        department_name=dept,
        azure_object_id=oid,
        role=req.role or "Employee",
        user_email=user_email,
    )


@router.delete("/departments/users")
def handle_remove_department_user(
    department_name: str,
    azure_object_id: str,
    current_user: dict = Depends(verify_azure_user),
):
    require_admin(current_user)
    removed = remove_department_user(department_name, azure_object_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Department user mapping not found")
    return {
        "message": f"Removed Azure Object ID {azure_object_id} from {department_name}"
    }


@router.get("/leave-queue")
def get_admin_leave_queue(current_user: dict = Depends(verify_azure_user)):
    return get_leave_tickets()


@router.post("/trigger-daily-digest")
def handle_trigger_daily_digest(current_user: dict = Depends(verify_azure_user)):
    """Trigger daily summary email digest on demand for IT Admins."""
    require_admin(current_user)
    from services.daily_digest_service import send_daily_admin_digest

    result = send_daily_admin_digest()
    return result


class AISettingsPayload(BaseModel):
    primary_model: Optional[str] = "gpt-5.2"
    fallback_model: Optional[str] = "gpt-4o-mini"
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 4096
    confidence_threshold: Optional[float] = 0.70
    top_k_chunks: Optional[int] = 3
    similarity_threshold: Optional[float] = 0.75
    monthly_budget_usd: Optional[float] = 50.0
    telemetry_level: Optional[str] = "verbose"
    feature_auto_triage: Optional[bool] = True
    feature_chatbot_genie: Optional[bool] = True
    feature_suggested_responses: Optional[bool] = True
    feature_rag_grounding: Optional[bool] = True
    feature_sla_scoring: Optional[bool] = True
    feature_issue_clustering: Optional[bool] = True
    feature_prompt_lru_caching: Optional[bool] = True
    feature_semantic_dedup: Optional[bool] = True
    prompt_cache_ttl: Optional[str] = "1h"


_DEFAULT_AI_SETTINGS = {
    "primary_model": "gpt-5.2",
    "fallback_model": "gpt-4o-mini",
    "temperature": 0.2,
    "max_tokens": 4096,
    "confidence_threshold": 0.70,
    "top_k_chunks": 3,
    "similarity_threshold": 0.75,
    "monthly_budget_usd": 50.0,
    "telemetry_level": "verbose",
    "feature_auto_triage": True,
    "feature_chatbot_genie": True,
    "feature_suggested_responses": True,
    "feature_rag_grounding": True,
    "feature_sla_scoring": True,
    "feature_issue_clustering": True,
    "feature_prompt_lru_caching": True,
    "feature_semantic_dedup": True,
    "prompt_cache_ttl": "1h",
}

_CURRENT_AI_SETTINGS = dict(_DEFAULT_AI_SETTINGS)


@router.get("/ai-settings")
def get_ai_settings(current_user: dict = Depends(verify_azure_user)):
    """Return current enterprise AI configuration and feature toggles."""
    require_admin(current_user)
    return dict(_CURRENT_AI_SETTINGS)


@router.post("/ai-settings")
@router.put("/ai-settings")
def update_ai_settings(
    settings: AISettingsPayload,
    current_user: dict = Depends(verify_azure_user),
):
    """Update enterprise AI configuration and granular feature toggles."""
    require_admin(current_user)
    updated_data = settings.model_dump(exclude_unset=True)
    _CURRENT_AI_SETTINGS.update(updated_data)
    return {
        "status": "success",
        "message": "AI settings and feature toggles updated successfully.",
        "settings": dict(_CURRENT_AI_SETTINGS),
    }


@router.get("/prompt-cache/stats")
def get_prompt_cache_statistics(current_user: dict = Depends(verify_azure_user)):
    """Return live prompt cache hit rate, token savings, and active cached prompts."""
    require_admin(current_user)
    from services.prompt_cache_service import prompt_cache

    return prompt_cache.stats()


@router.post("/prompt-cache/purge")
def purge_prompt_cache(current_user: dict = Depends(verify_azure_user)):
    """Flush all entries from the in-memory prompt & response cache."""
    require_admin(current_user)
    from services.prompt_cache_service import prompt_cache

    return prompt_cache.purge()


@router.post("/prompt-cache/warmup")
def warmup_prompt_cache(current_user: dict = Depends(verify_azure_user)):
    """
    Run a set of repeated deterministic AI calls inside the live server process
    to populate the in-process LRU prompt cache with real hits.
    Returns final cache stats after warmup.
    """
    require_admin(current_user)
    from services.prompt_cache_service import prompt_cache

    results = []

    # 1. ticket_classifier — 4 calls (1 miss + 3 hits)
    try:
        from services.ai_service import get_ai_classification

        inputs = [
            (
                "Outlook not loading after Windows 11 update",
                "Outlook freezes on startup.",
            ),
            (
                "VPN Connection Fails with Error 800",
                "Cannot connect to AnyConnect VPN.",
            ),
            (
                "Printer offline on Floor 3",
                "HP LaserJet shows offline after switch replacement.",
            ),
        ]
        for title, desc in inputs:
            get_ai_classification(title, desc)
            get_ai_classification(title, desc)  # second call = cache hit
        results.append({"agent": "ticket_classifier", "calls": 6, "status": "ok"})
    except Exception as e:
        results.append(
            {"agent": "ticket_classifier", "status": "error", "detail": str(e)}
        )

    # 2. announcement_severity — 4 calls (2 misses + 2 hits)
    try:
        from services.announcement_service import classify_announcement_severity

        ann_inputs = [
            (
                "Office 365 Email Outage",
                "Microsoft 365 email services experiencing degradation.",
                "IT Infrastructure",
            ),
            (
                "VPN Gateway Certificate Renewal",
                "Global VPN gateway cert renewal requires restart.",
                "Network",
            ),
        ]
        for title, body, cat in ann_inputs:
            classify_announcement_severity(title, body, category=cat)
            classify_announcement_severity(title, body, category=cat)  # hit
        results.append({"agent": "announcement_severity", "calls": 4, "status": "ok"})
    except Exception as e:
        results.append(
            {"agent": "announcement_severity", "status": "error", "detail": str(e)}
        )

    # 3. structured_TicketSummary — 4 calls (2 misses + 2 hits)
    try:
        from agents.summary_agent import summarize_ticket

        sum_inputs = [
            (
                "Printer Offline Floor 3",
                "HP LaserJet shows offline error after network switch was replaced.",
            ),
            (
                "Dell 4K Monitor Flickering",
                "Green vertical stripes appear after power surge event.",
            ),
        ]
        for title, desc in sum_inputs:
            summarize_ticket(title, desc)
            summarize_ticket(title, desc)  # hit
        results.append(
            {"agent": "structured_TicketSummary", "calls": 4, "status": "ok"}
        )
    except Exception as e:
        results.append(
            {"agent": "structured_TicketSummary", "status": "error", "detail": str(e)}
        )

    return {
        "status": "warmup_complete",
        "agents_exercised": results,
        "cache_stats": prompt_cache.stats(),
    }
