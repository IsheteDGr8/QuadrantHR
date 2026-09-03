"""Deterministic, Ticketer-or-higher Genie announcement workflows."""

from __future__ import annotations

import re
from typing import Optional

from database.crud import create_announcement, delete_announcement, get_announcements
from models.chatbot import ChatIntent, ChatResponse, PendingManagementAction
from services.role_service import is_ticketer

ANNOUNCEMENT_INTENTS = {ChatIntent.CREATE_ANNOUNCEMENT, ChatIntent.DELETE_ANNOUNCEMENT}


def detect_intent(message: str) -> Optional[ChatIntent]:
    text = message.strip().lower()
    if re.search(r"\b(?:create|make|post|publish)\b.*\bannouncement\b", text):
        return ChatIntent.CREATE_ANNOUNCEMENT
    if re.search(r"\b(?:delete|remove)\b.*\bannouncement\b", text):
        return ChatIntent.DELETE_ANNOUNCEMENT
    return None


def _yes(message: str) -> bool:
    return message.strip().lower().rstrip(".!?") in {
        "yes",
        "y",
        "confirm",
        "confirmed",
        "ok",
        "okay",
        "publish",
        "delete",
    }


def _no(message: str) -> bool:
    return message.strip().lower().rstrip(".!?") in {
        "no",
        "n",
        "cancel",
        "stop",
        "never mind",
        "nevermind",
    }


def _initial_subject(message: str, verbs: str) -> Optional[str]:
    match = re.search(
        rf"\b(?:{verbs})\b.*?\bannouncement\b(?:\s+(?:titled|called|named))?\s*[\"']?(.+?)[\"']?\s*$",
        message.strip(),
        re.IGNORECASE,
    )
    value = match.group(1).strip(" \"'.") if match else ""
    return value or None


def _create_turn(
    pending: PendingManagementAction, message: str, user: dict
) -> ChatResponse:
    if not pending.announcement_title:
        pending.announcement_title = (
            message.strip()
            if pending.awaiting == "announcement_title"
            else _initial_subject(message, "create|make|post|publish")
        )
        if not pending.announcement_title:
            pending.awaiting = "announcement_title"
            return ChatResponse(
                message="What should the announcement title be?",
                intent=pending.action_type,
                pending_action=pending,
            )
    if not pending.announcement_content:
        if pending.awaiting == "announcement_content":
            pending.announcement_content = message.strip()
        else:
            pending.awaiting = "announcement_content"
            return ChatResponse(
                message="What details should the announcement include?",
                intent=pending.action_type,
                pending_action=pending,
            )
    if pending.awaiting != "announcement_confirmation":
        pending.awaiting = "announcement_confirmation"
        return ChatResponse(
            message=f"Ready to publish ‘{pending.announcement_title}’:\n{pending.announcement_content}\n\nPublish this announcement? (yes/no)",
            intent=pending.action_type,
            pending_action=pending,
        )
    if _no(message):
        return ChatResponse(
            message="Okay, I won't publish that announcement.",
            intent=pending.action_type,
        )
    if not _yes(message):
        return ChatResponse(
            message="Please confirm whether I should publish it. (yes/no)",
            intent=pending.action_type,
            pending_action=pending,
        )
    created = create_announcement(
        title=pending.announcement_title,
        content=pending.announcement_content,
        category=pending.announcement_category or "General Alert",
        author=user.get("name") or user.get("email") or "Admin",
    )
    return ChatResponse(
        message=f"Published announcement ‘{created['title']}’.",
        intent=pending.action_type,
    )


def _delete_turn(pending: PendingManagementAction, message: str) -> ChatResponse:
    if pending.awaiting == "announcement_confirmation":
        if _no(message):
            return ChatResponse(
                message="Okay, I won't delete that announcement.",
                intent=pending.action_type,
            )
        if not _yes(message):
            return ChatResponse(
                message="Please confirm whether I should delete it. (yes/no)",
                intent=pending.action_type,
                pending_action=pending,
            )
        if not pending.announcement_id or not delete_announcement(
            pending.announcement_id
        ):
            return ChatResponse(
                message="That announcement no longer exists, so nothing was deleted.",
                intent=pending.action_type,
            )
        return ChatResponse(
            message=f"Deleted announcement ‘{pending.announcement_title}’.",
            intent=pending.action_type,
        )
    query = (
        message.strip()
        if pending.awaiting == "announcement_selection"
        else _initial_subject(message, "delete|remove")
    )
    if not query:
        pending.awaiting = "announcement_selection"
        return ChatResponse(
            message="Which announcement should I delete? Tell me its title.",
            intent=pending.action_type,
            pending_action=pending,
        )
    lowered = query.lower()
    matches = [
        item
        for item in get_announcements()
        if lowered == str(item.get("id", "")).lower()
        or lowered in str(item.get("title", "")).lower()
    ]
    if len(matches) != 1:
        pending.awaiting = "announcement_selection"
        titles = "\n".join(f"- {item.get('title')}" for item in matches[:8])
        prompt = (
            "I found more than one match. Which title do you mean?"
            if matches
            else "I couldn't find that announcement. Which title should I delete?"
        )
        return ChatResponse(
            message=f"{prompt}{chr(10) + titles if titles else ''}",
            intent=pending.action_type,
            pending_action=pending,
        )
    pending.announcement_id, pending.announcement_title = (
        matches[0]["id"],
        matches[0]["title"],
    )
    pending.awaiting = "announcement_confirmation"
    return ChatResponse(
        message=f"Delete announcement ‘{pending.announcement_title}’? This cannot be undone. (yes/no)",
        intent=pending.action_type,
        pending_action=pending,
    )


def handle_turn(
    request, intent: ChatIntent, current_user: Optional[dict]
) -> ChatResponse:
    user = current_user or {}
    if not is_ticketer(user.get("role") or "", user.get("is_dev", False)):
        return ChatResponse(
            message="Sorry, only authorized Ticketers and Admins can create or delete announcements.",
            intent=intent,
        )
    pending = request.pending_action
    if pending is None or pending.action_type != intent:
        pending = PendingManagementAction(action_type=intent)
    return (
        _create_turn(pending, request.message.strip(), user)
        if intent == ChatIntent.CREATE_ANNOUNCEMENT
        else _delete_turn(pending, request.message.strip())
    )
