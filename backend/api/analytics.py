"""HR Analytics & Helpdesk Resolution Trends Router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.crud import get_analytics_summary
from services.azure_ai_usage_service import (
    AzureAIUsageUnavailableError,
    get_azure_ai_usage,
    is_ai_usage_admin,
)
from services.department_analytics_service import (
    AnalyticsAccessError,
    get_department_health_analytics,
    resolve_analytics_department,
)
from services.jwt_verifier import verify_azure_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/trends")
def get_analytics_trends(current_user: dict = Depends(verify_azure_user)):
    return get_analytics_summary()


@router.get("/department-health")
def get_department_health(
    department: Optional[str] = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_azure_user),
):
    """Calculated department analytics scoped by the verified JWT identity."""
    try:
        requested_department = resolve_analytics_department(current_user, department)
    except AnalyticsAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
    return get_department_health_analytics(db, requested_department)


@router.get("/ai-usage")
def get_ai_usage(
    days: int = Query(default=30, ge=1, le=90),
    current_user: dict = Depends(verify_azure_user),
):
    """Return Azure-backed LLM usage to verified Admin/Super Admin users."""
    if not is_ai_usage_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI usage statistics require Admin or Super Admin access.",
        )
    try:
        return get_azure_ai_usage(days=days)
    except AzureAIUsageUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
