"""
Persistence layer for the Genie AI full-page chat (conversations + messages).

This is deliberately kept separate from services/chatbot_service.py, whose
handle_message() stays exactly as it was: a pure, stateless function covered
by its own large test suite (tests/test_chatbot.py) that calls it directly.
Persistence is bolted on around that call, at the API route layer, so the
chatbot "brain" is never duplicated or modified.

Ownership is always derived from the verified current_user identity (Azure
oid, falling back to email) - never trusted from the request body - mirroring
the pattern already used for ticket ownership in api/tickets.py.
"""

import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database import crud

DEFAULT_TITLE = "New conversation"
MAX_TITLE_LENGTH = 48
MAX_TITLE_WORDS = 8

_PDF_EXPORT_REQUEST = re.compile(
    r"\b(?:pdf|portable document format)\b.*\b(?:conversation|chat|transcript)\b"
    r"|\b(?:conversation|chat|transcript)\b.*\b(?:pdf|portable document format)\b",
    re.IGNORECASE,
)


def get_owner_id(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not current_user:
        return None
    return current_user.get("oid") or current_user.get("email")


def derive_title(message: str) -> str:
    """Deterministic, GPT-free title derivation from the first user message."""
    cleaned = " ".join((message or "").strip().split())
    if not cleaned:
        return DEFAULT_TITLE

    words = cleaned.split(" ")
    truncated_words = " ".join(words[:MAX_TITLE_WORDS])
    if len(truncated_words) > MAX_TITLE_LENGTH:
        truncated_words = truncated_words[:MAX_TITLE_LENGTH].rstrip()

    is_truncated = len(words) > MAX_TITLE_WORDS or len(cleaned) > len(truncated_words)
    return f"{truncated_words}…" if is_truncated else truncated_words


class ConversationNotFoundError(Exception):
    """Raised when a conversation_id doesn't exist or isn't owned by the caller."""


def is_pdf_export_request(message: str) -> bool:
    """Recognize explicit requests to export the current Genie chat as PDF."""
    return bool(_PDF_EXPORT_REQUEST.search((message or "").strip()))


def persist_turn(
    db: Session,
    *,
    conversation_id: Optional[str],
    owner_id: str,
    user_message: str,
    assistant_message: str,
) -> dict:
    """
    Persists one user/assistant turn. Lazily creates a new conversation when
    conversation_id is None (first message of a new chat) rather than ever
    creating an empty/junk conversation row up front.
    """
    if conversation_id:
        conversation = crud.get_conversation(conversation_id, owner_id, db=db)
        if not conversation:
            raise ConversationNotFoundError(conversation_id)
    else:
        conversation = crud.create_conversation(
            owner_id, derive_title(user_message), db=db
        )

    crud.add_conversation_message(conversation["id"], "user", user_message, db=db)
    crud.add_conversation_message(
        conversation["id"], "assistant", assistant_message, db=db
    )

    return crud.get_conversation(conversation["id"], owner_id, db=db)
