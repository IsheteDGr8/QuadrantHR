"""Notifications API Router for TicketGenie."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.crud import (
    create_notification,
    get_notifications,
    mark_notification_read,
)
from services.jwt_verifier import verify_azure_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreateRequest(BaseModel):
    title: str
    message: str
    user_id: str


def _notification_identities(current_user: dict) -> list[str]:
    return list(
        dict.fromkeys(
            value
            for value in (current_user.get("oid"), current_user.get("email"))
            if value
        )
    )


@router.get("")
def list_notifications(
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    return get_notifications(_notification_identities(current_user), db=db)


@router.post("", status_code=201)
def handle_create_notification(
    req: NotificationCreateRequest,
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    role = (current_user.get("role") or "").lower()
    if not any(value in role for value in ("admin", "super", "operations")):
        raise HTTPException(status_code=403, detail="Admin access required")
    if req.user_id.strip().lower() in {"all", "user"}:
        raise HTTPException(
            status_code=422, detail="A specific user identity is required"
        )
    return create_notification(
        title=req.title,
        message=req.message,
        user_id=req.user_id,
        db=db,
    )


@router.put("/{notif_id}/read")
def handle_mark_notification_read(
    notif_id: str,
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    success = mark_notification_read(
        notif_id, _notification_identities(current_user), db=db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": f"Marked notification {notif_id} as read"}


@router.get("/outbox")
def list_email_outbox(
    current_user: dict = Depends(verify_azure_user),
):
    """Retrieve sent email outbox audit trail."""
    from services.email_service import get_outbox_log

    return get_outbox_log()
