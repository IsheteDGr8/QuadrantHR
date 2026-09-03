"""Announcements API Router for TicketGenie."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database.crud import (
    create_announcement,
    delete_announcement,
    get_announcements,
)
from services.announcement_match_service import find_matching_announcement
from services.announcement_service import (
    classify_announcement_severity,
    get_latest_announcement_with_severity,
)
from services.jwt_verifier import verify_azure_user
from services.role_service import is_ticketer

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    category: Optional[str] = Field(default="General Alert", max_length=100)


class AnnouncementMatchRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)


class AnnouncementSeverityRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    category: Optional[str] = Field(default="General Alert", max_length=100)


def require_announcement_admin(
    current_user: dict = Depends(verify_azure_user),
) -> dict:
    """Allow announcement mutations for verified Ticketer-or-higher roles."""
    role = current_user.get("role") or ""
    if not is_ticketer(role, current_user.get("is_dev", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Ticketers and Admins can manage announcements.",
        )
    return current_user


@router.get("")
def list_announcements(current_user: dict = Depends(verify_azure_user)):
    return get_announcements()


@router.get("/latest")
def get_latest_announcement(current_user: dict = Depends(verify_azure_user)):
    """Retrieve the most recent announcement with AI-evaluated severity metadata."""
    return get_latest_announcement_with_severity()


@router.post("/severity")
def evaluate_announcement_severity(
    req: AnnouncementSeverityRequest,
    current_user: dict = Depends(verify_azure_user),
):
    """Classify the severity of an announcement via AI backend method."""
    return classify_announcement_severity(
        title=req.title,
        content=req.content,
        category=req.category,
    )


@router.post("/match")
def match_ticket_to_announcement(
    req: AnnouncementMatchRequest,
    current_user: dict = Depends(verify_azure_user),
):
    match = find_matching_announcement(
        title=req.title,
        description=req.description,
        announcements=get_announcements(),
    )
    return match or {"matched": False}


@router.post("", status_code=201)
def handle_create_announcement(
    req: AnnouncementCreateRequest,
    current_user: dict = Depends(require_announcement_admin),
):
    return create_announcement(
        title=req.title,
        content=req.content,
        category=req.category or "General Alert",
        author=current_user.get("name") or current_user.get("email") or "Admin",
    )


@router.delete("/{anc_id}")
def handle_delete_announcement(
    anc_id: str,
    current_user: dict = Depends(require_announcement_admin),
):
    removed = delete_announcement(anc_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": f"Deleted announcement {anc_id}"}
