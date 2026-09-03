"""
Ticket Drafting: deterministic validation + merge layer.

Semantic extraction (what the user meant, what fields that implies) is
GPT-5.2's job (backend/agents/chatbot_agent.py). This module never guesses
meaning from the message text - it only validates what the model
extracted against the schema TicketCreate/the Standard/Anonymous Request
form actually allows, and merges it into the running TicketDraft.
`priority` is never set here - that's an internal routing field owned by
Saketh's classification agents (backend/agents/*), not something the
chatbot should guess. `department` is only ever set here for the one hard
business rule that isn't a guess: every Leave Management request routes
deterministically to LEAVE_DEPARTMENT, never through classification.
"""

import re
from datetime import datetime
from typing import List, Optional, Tuple

from agents.category_agent import is_valid_department
from agents.chatbot_agent import ExtractedTicketFields
from agents.orchestrator import classify_ticket as default_classify_ticket
from models.chatbot import ChatIntent, RequestType, TicketDraft

STANDARD_CATEGORIES = [
    "HR & Workforce Operations",
    "IT & Technology",
    "Account Management",
    "Upper Executive Management",
    "Other",
]

LEAVE_TYPES = [
    "Paid Time Off (PTO)",
    "Medical Leave",
    "Parental Leave",
    "Bereavement",
    "Unpaid Leave",
    "Other",
]

# Hard business rule: every Leave Management request routes directly to
# this department, deterministically, skipping normal classification.
# Reused straight from agents/category_agent.ALLOWED_DEPARTMENTS (the
# single source of truth Saketh's classifier also uses, and the exact
# spelling models.ticket.TicketCreate.department accepts) rather than a
# second hardcoded vocabulary - see also services/ticket_service.py's
# department_override, which is what makes this rule hold at submission
# time too (classify_ticket() would otherwise silently overwrite it).
LEAVE_DEPARTMENT = "Upper Management"
assert is_valid_department(LEAVE_DEPARTMENT)

# Deterministic map from the classifier's department taxonomy onto the
# Standard/Anonymous Request form's own (coarser) category dropdown, used
# only to fix up a draft that landed on "Other". "Workplace Operations
# Team" has no equivalent bucket in that dropdown, so it intentionally has
# no entry here - reclassify_other_category() falls back to leaving the
# draft at "Other" (a real, valid value) rather than inventing one.
_DEPARTMENT_TO_STANDARD_CATEGORY = {
    "HR Team": "HR & Workforce Operations",
    "IT Team": "IT & Technology",
    "Accounting Team": "Account Management",
    "Upper Management": "Upper Executive Management",
}

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TICKET_ID_PATTERN = re.compile(r"^HD-\d+$", re.IGNORECASE)
# Accepts the same "HD-1024" id with a space or no separator instead of a
# dash (e.g. "HD 1024", "HD1024") - the exact same ticket number, just
# typed differently. Still anchored on the literal "HD" prefix plus
# digits only, so it can never grab an unrelated number out of the
# message the way a bare \d+ scan would.
_TICKET_ID_LOOSE_PATTERN = re.compile(r"^HD[\s-]*(\d+)$", re.IGNORECASE)

_MISSING_TITLE_MARKERS = ("title", "subject")
_MISSING_DESCRIPTION_MARKERS = ("description", "detail", "reason", "what happened")
_MISSING_CATEGORY_MARKERS = ("categ", "leave type", "type of leave")
_MISSING_DATE_MARKERS = ("date",)

_EXPLICIT_LEAVE_TYPES = (
    (re.compile(r"\bunpaid(?:\s+leave)?\b", re.IGNORECASE), "Unpaid Leave"),
    (
        re.compile(
            r"\b(?:paid\s+time\s+off|pto|vacation)(?:\s+leave)?\b", re.IGNORECASE
        ),
        "Paid Time Off (PTO)",
    ),
    (re.compile(r"\b(?:medical|sick)(?:\s+leave)?\b", re.IGNORECASE), "Medical Leave"),
    (
        re.compile(r"\b(?:parental|maternity|paternity)(?:\s+leave)?\b", re.IGNORECASE),
        "Parental Leave",
    ),
    (re.compile(r"\bbereavement(?:\s+leave)?\b", re.IGNORECASE), "Bereavement"),
)


def explicit_leave_type(message: Optional[str]) -> Optional[str]:
    """Return a leave type only when the user's words name it unambiguously."""
    if not message:
        return None
    for pattern, leave_type in _EXPLICIT_LEAVE_TYPES:
        if pattern.search(message):
            return leave_type
    return None


def _leave_date_missing_label(draft: TicketDraft) -> Optional[str]:
    """
    Leave's start/end dates are tracked independently - never use
    preferredDate as proof the whole range is known. Returns the precise
    ask (only what's actually missing), or None once both are known.
    """

    if draft.startDate and draft.endDate:
        return None
    if draft.startDate and not draft.endDate:
        return "the end date"
    if draft.endDate and not draft.startDate:
        return "the start date"
    return "the start and end dates"


def validate_category(value: Optional[str], allowed: List[str]) -> Optional[str]:
    """Snap a model-proposed category to the exact allowed value, or reject it."""

    if not value:
        return None
    normalized = value.strip().lower()
    for option in allowed:
        if option.lower() == normalized:
            return option
    return None


def validate_iso_date(value: Optional[str]) -> Optional[str]:
    """Accept only a well-formed, real calendar date in YYYY-MM-DD."""

    if not value:
        return None
    value = value.strip()
    if not _ISO_DATE_PATTERN.match(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


def validate_ticket_id(value: Optional[str]) -> Optional[str]:
    """
    Normalize a model-extracted ticket reference to the canonical "HD-####"
    form, or reject it. Accepts the bare number ("2005"), the canonical
    dash form ("HD-2005"), and the space-separated form users actually type
    ("HD 2005") - all three are the same ticket ID, just formatted
    differently by the user or by GPT's "exactly as given" extraction.
    Never loosely scans for digits anywhere in free text - only these
    specific, already-ticket-shaped forms.
    """
    if not value:
        return None
    value = value.strip().upper()
    if value.isdigit():
        value = f"HD-{value}"
    else:
        loose = _TICKET_ID_LOOSE_PATTERN.match(value)
        if loose:
            value = f"HD-{loose.group(1)}"
    return value if _TICKET_ID_PATTERN.match(value) else None


def _fallback_title(description: str, *, max_words: int = 10) -> str:
    words = description.strip().split()
    if not words:
        return "Support Request"
    title = " ".join(words[:max_words])
    return title[:1].upper() + title[1:]


def _merge_description(
    existing: Optional[str], extracted: Optional[str]
) -> Optional[str]:
    """
    The model is shown the full conversation and the current draft every
    turn and is instructed to return the complete, up-to-date summary in
    `description` (not just this turn's new sentence) - so a fresh
    non-empty extraction replaces the running draft's description rather
    than being appended to it. Appending here is what previously produced
    transcript-style, ever-growing descriptions.
    """
    return extracted if extracted else existing


def _filter_missing_fields(
    gpt_missing: List[str], draft: TicketDraft, intent: ChatIntent
) -> List[str]:
    """
    Hard backstop: never re-ask for something the draft already has, even
    if the model's own missing_fields list forgot to drop it.
    """

    is_leave = intent == ChatIntent.LEAVE_MANAGEMENT
    kept = []
    for field in gpt_missing:
        lowered = field.lower()
        if draft.title and any(marker in lowered for marker in _MISSING_TITLE_MARKERS):
            continue
        if draft.description and any(
            marker in lowered for marker in _MISSING_DESCRIPTION_MARKERS
        ):
            continue
        if draft.category and any(
            marker in lowered for marker in _MISSING_CATEGORY_MARKERS
        ):
            continue
        if is_leave:
            # Leave tracks start/end independently (_leave_date_missing_label)
            # - drop GPT's own free-text date mention unconditionally here
            # and let merge_extracted_fields append the precise, deterministic
            # ask below, so wording never depends on GPT's phrasing and
            # preferredDate is never used as proof the whole range is known.
            if any(marker in lowered for marker in _MISSING_DATE_MARKERS):
                continue
        elif draft.preferredDate and any(
            marker in lowered for marker in _MISSING_DATE_MARKERS
        ):
            continue
        kept.append(field)
    return kept


def merge_extracted_fields(
    extracted: Optional[ExtractedTicketFields],
    *,
    existing_draft: Optional[TicketDraft],
    gpt_missing_fields: List[str],
    intent: ChatIntent,
    request_type: Optional[RequestType] = None,
    user_message: Optional[str] = None,
) -> Tuple[TicketDraft, List[str]]:
    """
    Deterministically fold the model's extraction into the running draft,
    validating category/date against the schema's exact allowed values.
    Returns (draft, missing_fields).
    """

    extracted = extracted or ExtractedTicketFields()
    draft = existing_draft.model_copy() if existing_draft else TicketDraft()

    draft.description = _merge_description(draft.description, extracted.description)

    is_leave = intent == ChatIntent.LEAVE_MANAGEMENT
    named_leave_type = explicit_leave_type(user_message) if is_leave else None
    if named_leave_type:
        # The user's explicit wording outranks both an omitted model field and
        # a stale category carried from an earlier draft turn.
        draft.category = named_leave_type
    elif not draft.category:
        allowed = LEAVE_TYPES if is_leave else STANDARD_CATEGORIES
        draft.category = validate_category(extracted.category, allowed)

    if intent == ChatIntent.LEAVE_MANAGEMENT:
        if not draft.startDate:
            # Defensive fallback: prefer the dedicated start_date field,
            # but also accept preferred_date in case GPT extracts a leave
            # date there instead - never invented, still validated.
            draft.startDate = validate_iso_date(
                extracted.start_date
            ) or validate_iso_date(extracted.preferred_date)
        if not draft.endDate:
            draft.endDate = validate_iso_date(extracted.end_date)
        # Backward-compat alias only - draft.startDate/draft.endDate are
        # the source of truth for a leave range; preferredDate just keeps
        # mirroring startDate for any older code path that still reads it.
        if not draft.preferredDate and draft.startDate:
            draft.preferredDate = draft.startDate
    elif not draft.preferredDate:
        draft.preferredDate = validate_iso_date(extracted.preferred_date)

    if not draft.title:
        if extracted.title:
            draft.title = extracted.title[:200]
        elif draft.description:
            draft.title = _fallback_title(draft.description)

    if request_type == RequestType.ANONYMOUS:
        draft.is_anonymous = True

    if intent == ChatIntent.LEAVE_MANAGEMENT:
        # Deterministic, never GPT-controlled - see LEAVE_DEPARTMENT.
        draft.department = LEAVE_DEPARTMENT

    missing = _filter_missing_fields(gpt_missing_fields, draft, intent)

    if not draft.description and not any(
        m in field.lower() for field in missing for m in _MISSING_DESCRIPTION_MARKERS
    ):
        missing.append("more detail about what's going on")

    if not draft.category and not any(
        m in field.lower() for field in missing for m in _MISSING_CATEGORY_MARKERS
    ):
        label = "leave type" if intent == ChatIntent.LEAVE_MANAGEMENT else "category"
        missing.append(label)

    if intent == ChatIntent.LEAVE_MANAGEMENT:
        leave_date_label = _leave_date_missing_label(draft)
        if leave_date_label:
            missing.append(leave_date_label)

    return draft, missing


def reclassify_other_category(
    title: str,
    description: str,
    *,
    classify_ticket=default_classify_ticket,
) -> Optional[str]:
    """
    A Standard/Anonymous draft landed on "Other". Reuse Saketh's existing,
    already-wired-into-real-ticket-submission classifier
    (agents.orchestrator.classify_ticket) - the same one
    services/ticket_service.py calls at actual submission time - rather
    than building a second classifier inside the chatbot. classify_ticket
    never raises, so this only guards against it returning something that
    doesn't map onto the Standard Request form's own category vocabulary.
    Returns None (safe fallback - leave the draft at "Other", a real
    allowed value) when nothing confidently maps.
    """

    try:
        classification = classify_ticket(title, description)
    except Exception:
        return None
    return _DEPARTMENT_TO_STANDARD_CATEGORY.get(classification.department)
