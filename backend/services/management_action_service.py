"""
Deterministic state machine for Genie's management write actions
(reassign_ticket / change_priority / create_portal_employee).

GPT (agents/chatbot_agent.py) only extracts meaning into
ManagementActionFields. Everything that must be trustworthy lives here in
plain Python: authorization (against the verified role from
services.jwt_verifier, never a client-supplied one), canonical value
validation, ticket-ambiguity resolution, and the ask/confirm/execute
sequencing. Mutations are executed through the existing ReAct tool registry
(agents.tool_registry.execute_tool) and database.crud.add_department_user -
this module never talks to the database directly for writes, only for the
read-side ticket-candidate lookups needed to disambiguate a target ticket.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

from agents.chatbot_agent import ManagementActionFields
from agents.tool_registry import execute_tool
from database.crud import add_department_user, get_all_tickets, list_departments
from models.chatbot import (
    ChatAction,
    ChatIntent,
    ChatResponse,
    PendingManagementAction,
    TicketCandidate,
)
from models.ticket import TICKET_DEPARTMENTS, TICKET_PRIORITIES
from services.role_service import (
    EMPLOYEE_ASSIGNMENT_ROLES,
    VisibilityScope,
    is_admin,
    is_ticket_mutation_authorized,
    resolve_visibility_scope,
)

SCOPE_UNRESOLVED_MESSAGE = (
    "I couldn't determine your ticket scope, so I can't modify a ticket from Genie."
)
UNAUTHORIZED_TICKET_MESSAGE = "I couldn't verify you're authorized to manage that ticket, so I won't make this change."

_AFFIRMATIVE_WORDS = {
    "yes",
    "y",
    "yeah",
    "yep",
    "yup",
    "confirm",
    "confirmed",
    "correct",
    "sure",
    "ok",
    "okay",
    "create",
    "approve",
    "approved",
    "right",
}
_NEGATIVE_WORDS = {
    "no",
    "n",
    "nope",
    "cancel",
    "stop",
    "dont",
    "never",
    "incorrect",
    "wrong",
}
_STOPWORDS = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "to",
    "for",
    "please",
    "can",
    "you",
    "move",
    "reassign",
    "change",
    "make",
    "set",
    "update",
    "ticket",
    "request",
    "it",
    "priority",
    "department",
    "low",
    "medium",
    "high",
    "critical",
    "from",
    "into",
    "of",
    "one",
    "and",
}

EMPLOYEE_FIELD_ORDER = [
    "employee_name",
    "employee_email",
    "employee_object_id",
    "employee_department",
    "employee_role",
]


def _is_affirmative(message: str) -> bool:
    normalized = re.sub(r"[^\w\s']", "", message.strip().lower())
    if normalized in _AFFIRMATIVE_WORDS:
        return True
    first_word = normalized.split(" ")[0] if normalized else ""
    return first_word in _AFFIRMATIVE_WORDS


def _is_negative(message: str) -> bool:
    normalized = re.sub(r"[^\w\s']", "", message.strip().lower())
    if normalized in _NEGATIVE_WORDS:
        return True
    first_word = normalized.split(" ")[0] if normalized else ""
    return first_word in _NEGATIVE_WORDS


def _match_option(message: str, options: Sequence[str]) -> Optional[str]:
    """
    Deterministic canonical-value matcher. Exact (case-insensitive) match
    always wins outright. Otherwise a whole-word match on the option's
    first token - case-sensitive for <=2 char tokens (e.g. "IT", "HR") so
    the pronoun "it" never false-positive matches "IT Team". Returns the
    single matching option, or None if zero or more-than-one option
    matches - ambiguity is never resolved by guessing.
    """
    stripped = message.strip()
    lowered = stripped.lower()
    matches: List[str] = []
    for opt in options:
        opt_lower = opt.lower()
        if opt_lower == lowered:
            return opt
        first_word = opt.split(" ", 1)[0]
        if opt_lower in lowered:
            matches.append(opt)
            continue
        if len(first_word) <= 2:
            if re.search(rf"\b{re.escape(first_word)}\b", stripped):
                matches.append(opt)
        elif re.search(rf"\b{re.escape(first_word.lower())}\b", lowered):
            matches.append(opt)
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def _to_candidate(t: dict) -> TicketCandidate:
    return TicketCandidate(
        id=t.get("id", ""),
        title=t.get("title", ""),
        department=t.get("department", ""),
        priority=t.get("priority", ""),
        status=t.get("status", ""),
    )


def _extract_keywords(message: str) -> List[str]:
    words = re.findall(r"[a-zA-Z]{3,}", message.lower())
    return [w for w in words if w not in _STOPWORDS]


def _find_candidate_tickets(
    scope: VisibilityScope, message: str, ticket_id_hint: Optional[str] = None
) -> List[TicketCandidate]:
    """
    Retrieve only tickets `scope` authorizes, THEN optionally narrow by
    keyword/id within that already-authorized set. Never the other way
    around - `scope` must come from role_service.resolve_visibility_scope()
    and callers must fail closed (never call this) when that returned None.
    `scope.unrestricted` is only ever True for a verified Super Admin.
    """
    dept_filter = None if scope.unrestricted else scope.department
    tickets = (
        get_all_tickets(department=dept_filter) if dept_filter else get_all_tickets()
    )

    if ticket_id_hint:
        tid = ticket_id_hint.strip().upper()
        return [_to_candidate(t) for t in tickets if (t.get("id") or "").upper() == tid]

    keywords = _extract_keywords(message)
    if keywords:
        narrowed = [
            t
            for t in tickets
            if any(
                k
                in ((t.get("title") or "") + " " + (t.get("description") or "")).lower()
                for k in keywords
            )
        ]
        if narrowed:
            return [_to_candidate(t) for t in narrowed[:8]]

    return [_to_candidate(t) for t in tickets[:8]]


def _ticket_in_scope(scope: VisibilityScope, ticket_id: Optional[str]) -> bool:
    """
    Final re-check, right before a mutation executes, that `ticket_id`
    genuinely falls within `scope`. `pending_action` is client-echoed
    state - defense in depth against a caller constructing/replaying a
    pending_action whose ticket_id/ticket_title were never actually
    validated against this turn's scope (e.g. a forged request that skips
    straight to an already-"resolved" ticket).
    """
    if not ticket_id:
        return False
    found = _find_candidate_tickets(scope, "", ticket_id_hint=ticket_id)
    return len(found) == 1


def _match_candidate(
    message: str, candidates: List[TicketCandidate]
) -> Optional[TicketCandidate]:
    stripped = message.strip()
    m = re.search(r"\bhd-?\s*(\d+)\b", stripped, re.IGNORECASE)
    if m:
        tid = f"HD-{m.group(1)}".upper()
        for c in candidates:
            if c.id.upper() == tid:
                return c

    ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
    lowered = stripped.lower()
    for word, idx in ordinals.items():
        if re.search(rf"\b{word}\b", lowered) and idx < len(candidates):
            return candidates[idx]

    keywords = set(_extract_keywords(stripped))
    if keywords:
        matches = [c for c in candidates if keywords & set(_extract_keywords(c.title))]
        if len(matches) == 1:
            return matches[0]
    return None


def _set_ticket(pending: PendingManagementAction, candidate: TicketCandidate) -> None:
    pending.ticket_id = candidate.id
    pending.ticket_title = candidate.title
    pending.current_department = candidate.department
    pending.current_priority = candidate.priority
    pending.candidate_tickets = []
    pending.awaiting = None


def _format_candidate_line(c: TicketCandidate, intent: ChatIntent) -> str:
    if intent == ChatIntent.CHANGE_PRIORITY:
        return f"{c.id} — {c.title} — {c.priority}"
    return f"{c.id} — {c.title}"


def _ask_ticket_selection(
    pending: PendingManagementAction,
    candidates: List[TicketCandidate],
    intent: ChatIntent,
) -> ChatResponse:
    lines = "\n".join(_format_candidate_line(c, intent) for c in candidates)
    verb = "move" if intent == ChatIntent.REASSIGN_TICKET else "reprioritize"
    return ChatResponse(
        message=f"Which ticket do you want to {verb}?\n{lines}",
        intent=intent,
        pending_action=pending,
        ticket_candidates=candidates,
    )


def _ask_ticket_confirmation(
    pending: PendingManagementAction, candidate: TicketCandidate, intent: ChatIntent
) -> ChatResponse:
    return ChatResponse(
        message=f"Do you mean {_format_candidate_line(candidate, intent)}?",
        intent=intent,
        pending_action=pending,
        ticket_candidates=[candidate],
    )


def _resolve_ticket_step(
    pending: PendingManagementAction,
    scope: VisibilityScope,
    message: str,
    intent: ChatIntent,
) -> Optional[ChatResponse]:
    if pending.ticket_id and pending.ticket_title:
        return None

    if pending.ticket_id and not pending.ticket_title:
        # An explicit ticket id (typed by the user, or carried over from a
        # prior turn's client-echoed state) is NEVER trusted outright - it
        # still has to come back out of the already-scoped lookup below,
        # so someone can't bypass candidate filtering by just naming an
        # out-of-scope HD-#### id.
        found = _find_candidate_tickets(
            scope, message, ticket_id_hint=pending.ticket_id
        )
        if len(found) == 1:
            _set_ticket(pending, found[0])
            return None
        pending.ticket_id = None

    if pending.awaiting == "ticket_confirmation" and pending.candidate_tickets:
        candidate = pending.candidate_tickets[0]
        if _is_affirmative(message):
            _set_ticket(pending, candidate)
            return None
        if not _is_negative(message):
            matched = _match_candidate(message, pending.candidate_tickets)
            if matched:
                _set_ticket(pending, matched)
                return None
            return _ask_ticket_confirmation(pending, candidate, intent)
        pending.candidate_tickets = []
        pending.awaiting = None

    if pending.awaiting == "ticket_selection" and pending.candidate_tickets:
        matched = _match_candidate(message, pending.candidate_tickets)
        if matched:
            _set_ticket(pending, matched)
            return None
        return _ask_ticket_selection(pending, pending.candidate_tickets, intent)

    found = _find_candidate_tickets(scope, message)
    if len(found) == 1:
        pending.candidate_tickets = found
        pending.awaiting = "ticket_confirmation"
        return _ask_ticket_confirmation(pending, found[0], intent)
    if len(found) > 1:
        pending.candidate_tickets = found[:8]
        pending.awaiting = "ticket_selection"
        return _ask_ticket_selection(pending, pending.candidate_tickets, intent)

    pending.candidate_tickets = []
    pending.awaiting = "ticket_selection"
    return ChatResponse(
        message="I couldn't find any tickets you're authorized to manage right now.",
        intent=intent,
        pending_action=pending,
    )


def _resolve_department_step(
    pending: PendingManagementAction, message: str, intent: ChatIntent
) -> Optional[ChatResponse]:
    if pending.target_department:
        return None
    matched = _match_option(message, TICKET_DEPARTMENTS)
    if matched:
        pending.target_department = matched
        return None
    label = f"{pending.ticket_id} — {pending.ticket_title}"
    options = ", ".join(TICKET_DEPARTMENTS)
    return ChatResponse(
        message=f"Which department should I move {label} to? ({options})",
        intent=intent,
        pending_action=pending,
    )


def _resolve_priority_step(
    pending: PendingManagementAction, message: str, intent: ChatIntent
) -> Optional[ChatResponse]:
    if pending.target_priority:
        return None
    matched = _match_option(message, TICKET_PRIORITIES)
    if matched:
        pending.target_priority = matched
        return None
    label = f"{pending.ticket_id} — {pending.ticket_title}"
    options = ", ".join(TICKET_PRIORITIES)
    return ChatResponse(
        message=(
            f"What priority should {label} be changed to? ({options}) "
            f"It's currently {pending.current_priority}."
        ),
        intent=intent,
        pending_action=pending,
    )


def _execute_ticket_mutation(
    pending: PendingManagementAction, role: str, user_id: str, intent: ChatIntent
) -> ChatResponse:
    if intent == ChatIntent.REASSIGN_TICKET:
        field, value, before = (
            "department",
            pending.target_department,
            pending.current_department,
        )
    else:
        field, value, before = (
            "priority",
            pending.target_priority,
            pending.current_priority,
        )

    result = execute_tool(
        "update_ticket_tool",
        {"ticket_id": pending.ticket_id, "field": field, "value": value},
        role=role,
        user_id=user_id,
    )
    if not result.startswith("Success"):
        return ChatResponse(
            message=f"I couldn't make that change: {result}",
            intent=intent,
            pending_action=None,
        )

    label = f"{pending.ticket_id} — {pending.ticket_title}"
    verb = "was moved" if intent == ChatIntent.REASSIGN_TICKET else "changed"
    return ChatResponse(
        message=f"Done. {label} {verb} from {before} to {value}.",
        intent=intent,
        action=ChatAction(type="refresh_ticket", ticket_id=pending.ticket_id),
        pending_action=None,
    )


def _live_employee_departments() -> List[str]:
    return [d["name"] for d in list_departments()]


def _employee_field_prompt(field: str, dept_options: List[str]) -> str:
    prompts = {
        "employee_name": "Sure. What is the employee's name?",
        "employee_email": "What is their company email address?",
        "employee_object_id": "What is their Entra ID / Azure Object ID?",
        "employee_department": f"Which department should they be assigned to? ({', '.join(dept_options)})",
        "employee_role": f"What role should they have? ({', '.join(EMPLOYEE_ASSIGNMENT_ROLES)})",
    }
    return prompts[field]


def _review_message(pending: PendingManagementAction) -> str:
    return (
        "Ready to create this portal assignment:\n"
        f"Name: {pending.employee_name}\n"
        f"Email: {pending.employee_email}\n"
        f"Department: {pending.employee_department}\n"
        f"Role: {pending.employee_role}\n"
        f"Object ID: {pending.employee_object_id}\n\n"
        "Create this employee? (yes/no)"
    )


def _handle_create_employee(
    pending: PendingManagementAction, message: str, intent: ChatIntent
) -> ChatResponse:
    dept_options = _live_employee_departments()

    for field in EMPLOYEE_FIELD_ORDER:
        if getattr(pending, field):
            continue
        if pending.awaiting == f"employee_field:{field}" and message:
            value: Optional[str] = message.strip()
            if field == "employee_department":
                value = _match_option(message, dept_options)
            elif field == "employee_role":
                value = _match_option(message, list(EMPLOYEE_ASSIGNMENT_ROLES))
            elif field == "employee_email" and "@" not in (value or ""):
                value = None
            if value:
                setattr(pending, field, value)
                continue
        pending.awaiting = f"employee_field:{field}"
        return ChatResponse(
            message=_employee_field_prompt(field, dept_options),
            intent=intent,
            pending_action=pending,
        )

    if pending.awaiting != "employee_confirmation":
        pending.awaiting = "employee_confirmation"
        return ChatResponse(
            message=_review_message(pending), intent=intent, pending_action=pending
        )

    if _is_affirmative(message):
        add_department_user(
            department_name=pending.employee_department,
            azure_object_id=pending.employee_object_id,
            role=pending.employee_role,
            user_email=pending.employee_email,
        )
        who = (
            pending.employee_name
            or pending.employee_email
            or pending.employee_object_id
        )
        return ChatResponse(
            message=(
                f"Done. Created a portal assignment for {who} — "
                f"{pending.employee_role} in {pending.employee_department}."
            ),
            intent=intent,
            pending_action=None,
        )
    if _is_negative(message):
        return ChatResponse(
            message="Okay, I won't create that assignment.",
            intent=intent,
            pending_action=None,
        )

    return ChatResponse(
        message=_review_message(pending), intent=intent, pending_action=pending
    )


def _denied(intent: ChatIntent, capability: str) -> ChatResponse:
    return ChatResponse(
        message=f"Sorry, your role isn't authorized to {capability}.",
        intent=intent,
        pending_action=None,
    )


def _apply_extracted_fields(
    pending: PendingManagementAction, fields: Optional[ManagementActionFields]
) -> None:
    if not fields:
        return
    if fields.ticket_id and not pending.ticket_id:
        pending.ticket_id = fields.ticket_id.strip().upper()
    if fields.target_department and not pending.target_department:
        if fields.target_department in TICKET_DEPARTMENTS:
            pending.target_department = fields.target_department
    if fields.target_priority and not pending.target_priority:
        if fields.target_priority in TICKET_PRIORITIES:
            pending.target_priority = fields.target_priority
    if fields.employee_name and not pending.employee_name:
        pending.employee_name = fields.employee_name.strip()
    if fields.employee_email and not pending.employee_email:
        pending.employee_email = fields.employee_email.strip()
    if fields.employee_object_id and not pending.employee_object_id:
        pending.employee_object_id = fields.employee_object_id.strip()
    if fields.employee_role and not pending.employee_role:
        norm_role = fields.employee_role.strip()
        if norm_role.lower() == "member":
            norm_role = "Employee"
        elif norm_role.lower() in ("agent", "support"):
            norm_role = "Ticketer"
        if norm_role in EMPLOYEE_ASSIGNMENT_ROLES:
            pending.employee_role = norm_role
    if fields.employee_department and not pending.employee_department:
        if fields.employee_department in _live_employee_departments():
            pending.employee_department = fields.employee_department


def format_pending_context(pending: Optional[PendingManagementAction]) -> str:
    """Rendered into the GPT prompt so it doesn't re-ask for known fields."""
    if pending is None:
        return "(no management action in progress)"
    fields = pending.model_dump(exclude_none=True, exclude_defaults=True)
    fields.pop("candidate_tickets", None)
    if not fields:
        return "(no fields known yet)"
    return ", ".join(f"{k}={v}" for k, v in fields.items())


def handle_turn(
    request,
    decision,
    intent: ChatIntent,
    *,
    current_user: Optional[dict],
) -> ChatResponse:
    role = (current_user or {}).get("role") or request.role or "Employee"
    user_id = (
        (current_user or {}).get("oid") or (current_user or {}).get("email") or "user"
    )

    if intent in (ChatIntent.REASSIGN_TICKET, ChatIntent.CHANGE_PRIORITY):
        if not is_ticket_mutation_authorized(role):
            return _denied(intent, "reassign or reprioritize tickets")
    elif intent == ChatIntent.CREATE_PORTAL_EMPLOYEE:
        if not is_admin(role, (current_user or {}).get("is_dev", False)):
            return _denied(intent, "create new portal employees")
    else:  # pragma: no cover - defensive, chatbot_service only routes the 3 above
        return ChatResponse(
            message="I can't help with that here.", intent=ChatIntent.GENERAL
        )

    pending = request.pending_action
    if pending is None or pending.action_type != intent:
        pending = PendingManagementAction(action_type=intent)

    message = request.message.strip()
    _apply_extracted_fields(pending, decision.management_fields)

    if intent in (ChatIntent.REASSIGN_TICKET, ChatIntent.CHANGE_PRIORITY):
        # Sequence is fixed: resolve the caller's authorized scope FIRST,
        # then only ever retrieve/narrow tickets within it - never fetch
        # broadly and filter after the fact. An unresolvable scope fails
        # closed here, before any ticket is ever looked up.
        scope = resolve_visibility_scope(current_user)
        if scope is None:
            return ChatResponse(
                message=SCOPE_UNRESOLVED_MESSAGE, intent=intent, pending_action=None
            )

        step = _resolve_ticket_step(pending, scope, message, intent)
        if step is not None:
            return step
        target_step = (
            _resolve_department_step(pending, message, intent)
            if intent == ChatIntent.REASSIGN_TICKET
            else _resolve_priority_step(pending, message, intent)
        )
        if target_step is not None:
            return target_step
        if not _ticket_in_scope(scope, pending.ticket_id):
            return ChatResponse(
                message=UNAUTHORIZED_TICKET_MESSAGE, intent=intent, pending_action=None
            )
        return _execute_ticket_mutation(pending, role, user_id, intent)

    return _handle_create_employee(pending, message, intent)
