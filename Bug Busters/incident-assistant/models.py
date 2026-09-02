from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, Integer, String, Text

from database import Base


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    # Comma-separated keywords/tags used by the retrieval function's
    # keyword-overlap matching — kept as a single delimited column rather
    # than a join table since this is a small, hand-seeded reference set.
    related_keywords = Column(String, nullable=False, default="")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_summary = Column(Text, nullable=False)
    matched_policy_id = Column(Integer, nullable=True)
    matched_policy_name = Column(String, nullable=True)
    follow_up_question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    # "pending_review" | "no_match" | "error" | "submitted"
    status = Column(String, nullable=False, default="pending_review")
    # Not part of Person B's ticket contract, but useful context to retain
    # on an "error" ticket when it's looked up later via GET /ticket/:id —
    # an extra field beyond the agreed schema doesn't break their build.
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
