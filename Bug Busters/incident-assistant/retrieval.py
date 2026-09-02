import re

from sqlalchemy.orm import Session

from models import Policy

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def find_matching_policy(db: Session, incident_text: str) -> Policy | None:
    """Keyword-overlap match: tokenizes the incident text and each policy's
    name/category/related_keywords, scores by token overlap, and returns the
    highest-scoring policy — or None if nothing overlaps at all.

    Deliberately simple (no embeddings/LLM call here) — retrieval and
    follow-up-question generation are separate concerns; see agent.py for
    the LLM-based part.
    """
    incident_tokens = _tokenize(incident_text)

    if not incident_tokens:
        return None

    best_policy: Policy | None = None
    best_score = 0

    for policy in db.query(Policy).all():
        policy_tokens = _tokenize(
            f"{policy.name} {policy.category} {policy.related_keywords}"
        )

        score = len(incident_tokens & policy_tokens)

        if score > best_score:
            best_score = score
            best_policy = policy

    return best_policy
