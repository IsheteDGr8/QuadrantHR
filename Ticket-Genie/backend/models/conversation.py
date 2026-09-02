from typing import List

from pydantic import BaseModel


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationDetail(ConversationSummary):
    messages: List[MessageOut]
