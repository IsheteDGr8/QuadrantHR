"""
Chatbot Agent: role-aware workplace assistant.

Semantic understanding (what the user means) comes from a single GPT-5.2
structured-output call per turn (agents/chatbot_agent.py). Everything that
must be trustworthy regardless of what the model says stays deterministic
Python here: route mapping, the leave-management business rule, knowledge
authorization/retrieval, ticket-field validation, and failure handling.
Knowledge answers get one additional GPT-5.2 call to compose a grounded
response from already-authorized, already-retrieved content - the model
never chooses what it's allowed to see.
"""

import re
from datetime import datetime
from typing import List, Optional

from agents import chatbot_agent, knowledge_agent, ticket_conversation_agent
from agents.chatbot_agent import ChatbotDecision, NavigationTarget
from agents.orchestrator import classify_ticket as default_classify_ticket
from database.crud import _resolve_user_email, list_departments
from database.crud import get_ticket_by_id as default_get_ticket_by_id
from database.crud import get_ticket_comments as default_get_ticket_comments
from models.chatbot import (
    ChatAction,
    ChatIntent,
    ChatRequest,
    ChatResponse,
    ChatScope,
    ChatTurn,
    OnboardingDraft,
    RequestType,
)
from models.ticket import TICKET_DEPARTMENTS, TICKET_PRIORITIES
from services import (
    announcement_action_service,
    management_action_service,
    ticket_draft_service,
)
from services.ai_service import ai_service as default_ai_service
from services.azure_ai_usage_service import (
    AzureAIUsageUnavailableError,
    get_azure_ai_usage,
    is_ai_usage_admin,
)
from services.knowledge_service import (
    KnowledgeRetriever,
    SearchUnavailableError,
    default_knowledge_retriever,
)
from services.role_service import (
    EMPLOYEE_ASSIGNMENT_ROLES,
    get_allowed_scopes,
    is_admin,
    is_admin_role,
    is_department_ticketer,
    resolve_visibility_scope,
)
from services.ticket_draft_service import merge_extracted_fields, validate_ticket_id

PREDEFINED_SUGGESTIONS = [
    "Ask a question",
    "Help me create a ticket",
    "Check my ticket status",
]

GPT_UNAVAILABLE_MESSAGE = (
    "I'm having trouble reaching the assistant service right now. Please "
    "try again in a moment, or use New Request / Knowledge Base directly "
    "from the navigation."
)
SEARCH_UNAVAILABLE_MESSAGE = (
    "I can't reach the knowledge search service right now, so I can't "
    "verify an answer to that. You can browse the Knowledge Base directly, "
    "or I can help you open a support request."
)
COULD_NOT_VERIFY_MESSAGE = (
    "I couldn't verify an answer to that from the knowledge sources you're "
    "authorized to access. You can browse the Knowledge Base for related "
    "articles, or I can help you open a support request."
)
OUT_OF_SCOPE_MESSAGE = (
    "I can only help with workplace-related questions and requests. "
    "Please ask me about company policies, HR, IT, accounting, workplace "
    "operations, tickets, leave, or other work-related support."
)
AI_USAGE_ADMIN_ONLY_MESSAGE = (
    "AI usage statistics are available only to verified Admins and Super Admins."
)

_AI_USAGE_QUERY_PATTERNS = (
    r"\b(?:ai|llm|genie)\s+(?:token\s+)?usage\b",
    r"\btoken\s+(?:count|counts|usage|metrics|statistics|stats)\b",
    r"\b(?:ai|llm|genie)\s+(?:cost|costs|metrics|statistics|stats)\b",
)


def _is_ai_usage_query(message: str) -> bool:
    return any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in _AI_USAGE_QUERY_PATTERNS
    )


def _handle_ai_usage_query(current_user: Optional[dict]) -> ChatResponse:
    if not is_ai_usage_admin(current_user):
        return ChatResponse(
            message=AI_USAGE_ADMIN_ONLY_MESSAGE,
            intent=ChatIntent.GENERAL,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    try:
        usage = get_azure_ai_usage()
    except AzureAIUsageUnavailableError:
        return ChatResponse(
            message=(
                "I couldn't retrieve AI usage from Azure Application Insights "
                "right now. Please try again shortly."
            ),
            intent=ChatIntent.GENERAL,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    totals = usage["totals"]
    message = (
        f"AI usage from Azure Application Insights for the last {usage['period_days']} days:\n"
        f"- Model calls: {totals['calls']:,}\n"
        f"- Prompt tokens: {totals['prompt_tokens']:,}\n"
        f"- Completion tokens: {totals['completion_tokens']:,}\n"
        f"- Total tokens: {totals['total_tokens']:,}\n"
        f"- Estimated cost: ${totals['estimated_cost_usd']:.6f}\n\n"
        "You can see the daily and model breakdown on General Analytics."
    )
    return ChatResponse(
        message=message,
        intent=ChatIntent.GENERAL,
        suggestions=PREDEFINED_SUGGESTIONS,
    )


def _out_of_scope_response() -> ChatResponse:
    """
    Fixed, safe refusal for a turn GPT classified as scope=out_of_scope
    (models.chatbot.ChatScope). Deliberately ignores decision.message -
    GPT may have already started answering the unrelated question in that
    field, and that answer must never reach the user. Never carries a
    ticket_draft/pending_action/action forward, so a request that's mid
    ticket-draft or mid management-action can't have unrelated content
    folded into it on this turn; the caller (handle_message) returns this
    BEFORE any drafting, RAG, ticket-status, or management-action code
    runs, so the existing_draft the client already holds is simply never
    touched this turn.
    """

    return ChatResponse(
        message=OUT_OF_SCOPE_MESSAGE,
        intent=ChatIntent.GENERAL,
        suggestions=PREDEFINED_SUGGESTIONS,
    )


def _gpt_unavailable_response() -> ChatResponse:
    """
    Safe fallback for any GPT/Azure OpenAI failure (including a decision
    that never raised but also never materialized). Never fabricates an
    intent, request_type, ticket_draft, navigation action, or RAG content
    - just a fixed message and the general intent so the frontend never
    opens a form or navigates on a failed turn.
    """

    return ChatResponse(
        message=GPT_UNAVAILABLE_MESSAGE,
        intent=ChatIntent.GENERAL,
        suggestions=PREDEFINED_SUGGESTIONS,
    )


_TICKET_DRAFT_INTENTS = (
    ChatIntent.CREATE_TICKET,
    ChatIntent.SUPPORT_ISSUE,
    ChatIntent.LEAVE_MANAGEMENT,
)

_MANAGEMENT_ACTION_INTENTS = (
    ChatIntent.REASSIGN_TICKET,
    ChatIntent.CHANGE_PRIORITY,
    ChatIntent.CREATE_PORTAL_EMPLOYEE,
)

_KNOWLEDGE_BASE_ACTION = ChatAction(
    type="navigate", target="create-ticket", label="Ask a support specialist"
)


def _my_tickets_tab(role: Optional[str]) -> str:
    """The activeTab a "my tickets" reference resolves to for `role`.

    Ticketers/admins/super-admins land on the department Inbox queue
    (frontend/src/components/Sidebar.svelte's `inbox` item, DB InboxView);
    everyone else lands on their own Dashboard, where DashboardView already
    shows the signed-in user's own tickets - there's no separate "my
    tickets" tab for plain employees in the live SPA.
    """

    return "inbox" if is_department_ticketer(role) else "dashboard"


def _resolve_active_tab(target: NavigationTarget, role: Optional[str]) -> Optional[str]:
    """
    Deterministically maps a semantic NavigationTarget to the EXACT
    activeTab string frontend/src/App.svelte renders for it today, gating
    role-restricted destinations the same way frontend/src/components/
    Sidebar.svelte hides their nav entries (isDepartmentTicketer/isAdmin/
    isSuperAdmin substring checks, mirrored in services.role_service).
    GPT never sees or produces this string - it only ever picks the
    semantic NavigationTarget.

    Returns None when `role` isn't authorized for a gated target - callers
    must treat that as "don't navigate" (a safe denial message instead),
    never fall back to guessing a different destination.
    """

    if target == NavigationTarget.DASHBOARD:
        return "dashboard"
    if target == NavigationTarget.CREATE_TICKET:
        return "create-ticket"
    if target == NavigationTarget.MY_TICKETS:
        return _my_tickets_tab(role)
    if target == NavigationTarget.KNOWLEDGE_BASE:
        return "knowledge" if is_department_ticketer(role) else None
    if target == NavigationTarget.NOTIFICATIONS:
        return "notifications"
    if target == NavigationTarget.ANNOUNCEMENTS:
        return "announcements"
    if target == NavigationTarget.PROFILE:
        return "profile"
    if target == NavigationTarget.SETTINGS:
        return "settings" if is_admin_role(role) else None
    if target == NavigationTarget.ANALYTICS:
        return "analytics" if is_department_ticketer(role) else None
    if target == NavigationTarget.ONBOARDING:
        return "onboarding" if is_admin_role(role) else None
    return None


_ACCESS_DENIED_MESSAGE = (
    "That section isn't available for your role, so I can't take you there."
)


def _shortcut_for_intent(
    intent: ChatIntent, role: Optional[str] = None
) -> ChatResponse:
    """A predefined button was clicked with no free-text yet - no GPT call needed."""

    if intent == ChatIntent.TICKET_STATUS:
        return ChatResponse(
            message=(
                "You can view all your requests and their status under My "
                "Tickets, or tell me a ticket number and I'll pull it up."
            ),
            intent=intent,
            action=ChatAction(
                type="navigate", target=_my_tickets_tab(role), label="My Tickets"
            ),
            suggestions=PREDEFINED_SUGGESTIONS,
        )
    if intent in _TICKET_DRAFT_INTENTS:
        return ChatResponse(
            message=(
                "Sure - briefly describe what's going on and I'll help put "
                "together a request."
            ),
            intent=intent,
            missing_fields=["a description of the issue"],
        )
    if intent == ChatIntent.KNOWLEDGE:
        return ChatResponse(message="What would you like to know?", intent=intent)
    return ChatResponse(
        message="What can I help you with?",
        intent=ChatIntent.GENERAL,
        suggestions=PREDEFINED_SUGGESTIONS,
    )


def _handle_navigation(decision: ChatbotDecision, role: Optional[str]) -> ChatResponse:
    if decision.navigation_target is None:
        return ChatResponse(
            message=decision.message,
            intent=ChatIntent.HOW_TO,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    target = _resolve_active_tab(decision.navigation_target, role)
    if target is None:
        return ChatResponse(
            message=_ACCESS_DENIED_MESSAGE,
            intent=ChatIntent.HOW_TO,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    label = decision.navigation_target.value.replace("_", " ").title()
    return ChatResponse(
        message=decision.message,
        intent=ChatIntent.NAVIGATION,
        action=ChatAction(type="navigate", target=target, label=label),
        suggestions=PREDEFINED_SUGGESTIONS,
    )


_TICKET_ID_IN_TEXT = re.compile(r"\bHD[\s-]?\d+\b", re.IGNORECASE)

_UNAUTHORIZED_TICKET_VIEW_MESSAGE = "You don't have access to view that ticket."


def _most_recent_ticket_id(history: List[ChatTurn]) -> Optional[str]:
    """
    Deterministic follow-up context: if THIS turn doesn't name a ticket
    (e.g. "who's assigned to it?"), fall back to the last ticket number
    mentioned anywhere in the conversation so far - a real chatbot session
    already carries `history` every turn, so no new memory system is
    needed. Only ever matches the literal "HD[-/space]####" shape (never a
    bare number), normalized through the same validate_ticket_id() every
    other extraction goes through, so an unrelated number mentioned
    earlier in the conversation can't be picked up by accident.
    """
    for turn in reversed(history or []):
        match = _TICKET_ID_IN_TEXT.search(turn.message)
        if match:
            validated = validate_ticket_id(match.group(0))
            if validated:
                return validated
    return None


def _is_ticket_owner(ticket: dict, current_user: Optional[dict]) -> bool:
    """
    Same creator-identity check already used before a self-resolve is
    blocked (agents.tool_registry.update_ticket_tool) and before a ticket
    update is applied (api.tickets.handle_update_ticket) - reused here
    rather than reinvented, including its `db=None` best-effort fallback
    for a requester_id that isn't already a bare oid/email.
    """
    if not current_user:
        return False
    requester_id = str(ticket.get("requester_id") or "").strip().lower()
    if not requester_id:
        return False
    oid = str(current_user.get("oid") or "").strip().lower()
    email = str(current_user.get("email") or "").strip().lower()
    if requester_id in (oid, email):
        return True
    resolved = str(_resolve_user_email(requester_id, None) or "").strip().lower()
    return bool(resolved) and resolved in (oid, email)


def _can_view_ticket(
    ticket: dict, current_user: Optional[dict], role: Optional[str]
) -> bool:
    """
    Deterministic RBAC gate for a Genie ticket-status lookup, built only
    from existing authorization primitives (services.role_service) - never
    a new access model. A caller may view a ticket if they created it, are
    a Super Admin, or are scoped (via resolve_visibility_scope, the same
    scope services.management_action_service already uses to decide which
    tickets a caller may act on) to the ticket's department. An
    unresolvable scope fails closed, same as management actions.
    """
    effective_role = (current_user or {}).get("role") or role
    if is_admin(effective_role, (current_user or {}).get("is_dev", False)):
        return True
    if _is_ticket_owner(ticket, current_user):
        return True
    scope = resolve_visibility_scope(current_user)
    if scope is None:
        return False
    if scope.unrestricted:
        return True
    ticket_department = (ticket.get("department") or "").strip().lower()
    return (
        bool(scope.department) and scope.department.strip().lower() == ticket_department
    )


def _visible_comments(
    ticket_id: str, role: Optional[str], comment_lookup
) -> List[dict]:
    """
    Every comment/activity entry on the ticket that `role` is authorized
    to see, applying the same "Private" (staff-only) visibility rule
    already enforced for comments elsewhere (api.tickets.
    list_comments_for_ticket / export_ticket_document) - the single
    source both the latest-update line and the conversation summary below
    read from, so neither can ever see a comment the other filters out.
    """
    try:
        comments = comment_lookup(ticket_id) or []
    except Exception:
        return []
    return [
        c for c in comments if is_admin_role(role) or c.get("sender_role") != "Private"
    ]


def _latest_visible_comment(visible_comments: List[dict]) -> Optional[str]:
    """Most recent already-authorized comment's text, or None if there is none."""
    if not visible_comments:
        return None
    return visible_comments[-1].get("message") or None


def _build_conversation_summary(
    ticket: dict, visible_comments: List[dict], *, ai_service
) -> Optional[str]:
    """
    A short GPT-composed synthesis of the ticket's already-authorized
    conversation (services.chatbot_service never sends unauthorized
    comment text to the model - `visible_comments` is pre-filtered by
    _visible_comments before this is ever called). Mirrors the same
    "grounded, only from supplied content" pattern _handle_knowledge
    already uses for knowledge_agent.answer_from_context - the model
    never gets to fill in a fact that isn't in the text it's given.

    Returns None (never fabricated, never a partial/broken summary) when
    there's no comment content to summarize, GPT judges the visible
    comments to have no meaningful content, or the summarization call
    fails for any reason - a summarization failure must never fail the
    ticket-status lookup itself.
    """
    comment_lines = [
        f"{c.get('sender_role') or 'Employee'}: {c.get('message')}"
        for c in visible_comments
        if (c.get("message") or "").strip()
    ]
    if not comment_lines:
        return None

    try:
        result = ticket_conversation_agent.summarize_conversation(
            ticket.get("title") or "",
            ticket.get("description") or "",
            comment_lines,
            ai_service=ai_service,
        )
    except Exception:
        return None

    if not result.has_meaningful_content:
        return None
    summary = (result.summary or "").strip()
    return summary or None


def _format_ticket_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %Y")
    except ValueError:
        return value


def _format_ticket_status_message(
    ticket: dict,
    *,
    latest_note: Optional[str],
    conversation_summary: Optional[str] = None,
) -> str:
    """
    Deterministic formatter - every line comes straight from the
    retrieved ticket dict (database.crud.get_ticket_by_id) or the
    already-authorized conversation_summary/latest_note built above,
    never invented here. A field that isn't present on the ticket is
    omitted entirely rather than guessed or left as a placeholder. The
    conversation summary is a separate section from the latest update,
    never a replacement for it - both can appear together.
    """
    lines = [f"{ticket.get('id')} — {ticket.get('title') or 'Untitled request'}"]
    lines.append(f"Status: {ticket.get('status') or 'Unknown'}")
    if ticket.get("priority"):
        lines.append(f"Priority: {ticket['priority']}")
    if ticket.get("department"):
        lines.append(f"Department: {ticket['department']}")
    if ticket.get("assigned_to"):
        lines.append(f"Assigned to: {ticket['assigned_to']}")
    created = _format_ticket_date(ticket.get("createdAt") or ticket.get("date"))
    if created:
        lines.append(f"Created: {created}")
    updated = _format_ticket_date(ticket.get("updatedAt"))
    if updated:
        lines.append(f"Last updated: {updated}")
    if conversation_summary:
        lines.append("")
        lines.append("Conversation summary:")
        lines.append(conversation_summary)
    if latest_note:
        lines.append("")
        lines.append(f"Latest update: {latest_note}")
    return "\n".join(lines)


def _handle_ticket_status(
    request: ChatRequest,
    decision: ChatbotDecision,
    *,
    ticket_lookup,
    comment_lookup,
    current_user: Optional[dict],
    ai_service,
) -> ChatResponse:
    role = (current_user or {}).get("role") or request.role

    ticket_id = None
    if decision.ticket_fields:
        # Validate the format BEFORE it ever reaches a database call.
        ticket_id = validate_ticket_id(decision.ticket_fields.ticket_id)
    if not ticket_id:
        # Follow-up turn with no ticket number of its own (e.g. "who's
        # assigned to it?") - resolve from conversation history instead of
        # falling back to a generic "check My Tickets" non-answer.
        ticket_id = _most_recent_ticket_id(request.history)

    my_tickets_tab = _my_tickets_tab(role)

    if not ticket_id:
        fallback_message = (
            "You can view your requests and their status under My Tickets."
        )
        return ChatResponse(
            message=decision.message or fallback_message,
            intent=ChatIntent.TICKET_STATUS,
            action=ChatAction(
                type="navigate", target=my_tickets_tab, label="My Tickets"
            ),
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    ticket = ticket_lookup(ticket_id)
    if ticket is None:
        return ChatResponse(
            message=(
                f"I couldn't find a ticket {ticket_id}. Double-check the "
                "number, or browse My Tickets to find it."
            ),
            intent=ChatIntent.TICKET_STATUS,
            action=ChatAction(
                type="navigate", target=my_tickets_tab, label="My Tickets"
            ),
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    if not _can_view_ticket(ticket, current_user, role):
        return ChatResponse(
            message=_UNAUTHORIZED_TICKET_VIEW_MESSAGE,
            intent=ChatIntent.TICKET_STATUS,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    visible_comments = _visible_comments(ticket_id, role, comment_lookup)
    latest_note = _latest_visible_comment(visible_comments)
    conversation_summary = _build_conversation_summary(
        ticket, visible_comments, ai_service=ai_service
    )
    return ChatResponse(
        message=_format_ticket_status_message(
            ticket, latest_note=latest_note, conversation_summary=conversation_summary
        ),
        intent=ChatIntent.TICKET_STATUS,
        action=ChatAction(
            type="lookup_ticket", target=my_tickets_tab, ticket_id=ticket_id
        ),
        suggestions=PREDEFINED_SUGGESTIONS,
    )


def _resolve_request_type(
    request: ChatRequest, decision: ChatbotDecision, intent: ChatIntent
) -> RequestType:
    """
    Deterministic: leave is always forced to the Leave Management form,
    regardless of what the model proposed. Otherwise prefer a
    continuation's already-chosen form - this can be `anonymous` from an
    earlier explicit UI/user choice, and is always honored as-is. For a
    fresh decision, the model's `anonymous` claim is only accepted when
    it also marked `anonymity_requested` - i.e. the user's own words
    explicitly asked for anonymity, not just a sensitive-sounding topic;
    otherwise (including when GPT incorrectly proposes anonymous with no
    such evidence) it's deterministically downgraded to standard.
    Standard is the default for every ordinary support/workplace
    request - we never ask the user to pick between Standard and
    Anonymous.
    """

    if intent == ChatIntent.LEAVE_MANAGEMENT:
        return RequestType.LEAVE_MANAGEMENT
    if request.active_request_type in (RequestType.STANDARD, RequestType.ANONYMOUS):
        return request.active_request_type
    if decision.request_type == RequestType.ANONYMOUS and decision.anonymity_requested:
        return RequestType.ANONYMOUS
    return RequestType.STANDARD


def _handle_ticket_drafting(
    request: ChatRequest,
    decision: ChatbotDecision,
    intent: ChatIntent,
    *,
    classify_ticket=default_classify_ticket,
) -> ChatResponse:
    request_type = _resolve_request_type(request, decision, intent)

    draft, missing = merge_extracted_fields(
        decision.ticket_fields,
        existing_draft=request.draft,
        gpt_missing_fields=decision.missing_fields,
        intent=intent,
        request_type=request_type,
        user_message=request.message,
    )

    if (
        not missing
        and request_type != RequestType.LEAVE_MANAGEMENT
        and draft.category == "Other"
    ):
        reclassified = ticket_draft_service.reclassify_other_category(
            draft.title or "",
            draft.description or "",
            classify_ticket=classify_ticket,
        )
        if reclassified:
            draft.category = reclassified

    if missing:
        return ChatResponse(
            message=decision.message or _missing_fields_prompt(missing),
            intent=intent,
            request_type=request_type,
            ticket_draft=draft,
            missing_fields=missing,
            ready_for_review=False,
        )

    return ChatResponse(
        message=(
            decision.message
            or "Here's a draft based on what you told me - review it, edit "
            "anything that's not quite right, and submit it when you're ready."
        ),
        intent=intent,
        request_type=request_type,
        ticket_draft=draft,
        missing_fields=[],
        ready_for_review=True,
    )


def _handle_onboarding_drafting(
    request: ChatRequest, decision: ChatbotDecision, current_user: Optional[dict]
) -> ChatResponse:
    role = (current_user or {}).get("role") or request.role
    is_dev = bool((current_user or {}).get("is_dev", False))
    if not is_admin(role, is_dev):
        return ChatResponse(
            message="Admin access is required to start employee onboarding.",
            intent=ChatIntent.START_ONBOARDING,
        )

    existing = request.onboarding_draft or OnboardingDraft()
    merged = existing.model_copy()
    if decision.onboarding_fields:
        for field, value in decision.onboarding_fields.model_dump(
            exclude_none=True
        ).items():
            if isinstance(value, str) and value.strip():
                setattr(merged, field, value.strip())

    required = {
        "employee_name": "the employee's name",
        "employee_email": "the employee's email",
        "job_title": "their job title",
        "employee_department": "their department",
        "start_date": "their start date",
    }
    missing = [label for field, label in required.items() if not getattr(merged, field)]
    if missing:
        return ChatResponse(
            message=decision.message or _missing_fields_prompt(missing),
            intent=ChatIntent.START_ONBOARDING,
            onboarding_draft=merged,
            missing_fields=missing,
        )
    return ChatResponse(
        message=decision.message or "I filled the onboarding form for your review.",
        intent=ChatIntent.START_ONBOARDING,
        action=ChatAction(
            type="navigate", target="onboarding", label="Review onboarding"
        ),
        onboarding_draft=merged,
        ready_for_review=True,
    )


def _missing_fields_prompt(missing: List[str]) -> str:
    if len(missing) == 1:
        return f"Could you tell me more about {missing[0]}?"
    joined = ", ".join(missing[:-1]) + f", and {missing[-1]}"
    return f"Could you tell me more about {joined}?"


def _handle_knowledge(
    request: ChatRequest,
    decision: ChatbotDecision,
    *,
    retriever: KnowledgeRetriever,
    ai_service,
    current_user: Optional[dict] = None,
) -> ChatResponse:
    role = (current_user or {}).get("role") or request.role
    department = (current_user or {}).get("department") or request.department
    allowed_scopes = get_allowed_scopes(role, department)
    query = decision.knowledge_query or request.message

    try:
        documents = retriever.search(query, allowed_scopes)
    except SearchUnavailableError:
        return ChatResponse(
            message=SEARCH_UNAVAILABLE_MESSAGE,
            intent=ChatIntent.KNOWLEDGE,
            knowledge_verified=False,
            action=_KNOWLEDGE_BASE_ACTION,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    if not documents:
        return ChatResponse(
            message=COULD_NOT_VERIFY_MESSAGE,
            intent=ChatIntent.KNOWLEDGE,
            knowledge_verified=False,
            action=_KNOWLEDGE_BASE_ACTION,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    try:
        grounded = knowledge_agent.answer_from_context(
            query, documents, ai_service=ai_service
        )
    except Exception:
        return ChatResponse(
            message=GPT_UNAVAILABLE_MESSAGE,
            intent=ChatIntent.KNOWLEDGE,
            knowledge_verified=False,
            action=_KNOWLEDGE_BASE_ACTION,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    return ChatResponse(
        message=grounded.answer,
        intent=ChatIntent.KNOWLEDGE,
        knowledge_verified=grounded.verified,
        action=None if grounded.verified else _KNOWLEDGE_BASE_ACTION,
        suggestions=PREDEFINED_SUGGESTIONS,
    )


def handle_message(
    request: ChatRequest,
    *,
    current_user: Optional[dict] = None,
    ai_service=default_ai_service,
    retriever: KnowledgeRetriever = None,
    ticket_lookup=default_get_ticket_by_id,
    comment_lookup=default_get_ticket_comments,
    classify_ticket=default_classify_ticket,
) -> ChatResponse:
    retriever = retriever or default_knowledge_retriever
    if current_user and current_user.get("role"):
        request.role = current_user.get("role")
    message = request.message.strip()

    if not message:
        if request.active_intent:
            return _shortcut_for_intent(request.active_intent, request.role)
        return ChatResponse(
            message="I'm Genie, your workplace assistant. What can I help you with?",
            intent=ChatIntent.GENERAL,
            suggestions=PREDEFINED_SUGGESTIONS,
        )

    # Deterministic and authorization-gated before GPT: the verified Bearer
    # identity is the only role source, and asking for stats consumes no AI call.
    if _is_ai_usage_query(message):
        return _handle_ai_usage_query(current_user)

    announcement_intent = (
        request.pending_action.action_type
        if request.pending_action
        and request.pending_action.action_type
        in announcement_action_service.ANNOUNCEMENT_INTENTS
        else announcement_action_service.detect_intent(message)
    )
    if announcement_intent:
        return announcement_action_service.handle_turn(
            request, announcement_intent, current_user
        )

    try:
        decision = chatbot_agent.decide(
            message,
            history=request.history,
            existing_draft=request.draft,
            existing_onboarding_draft=request.onboarding_draft,
            known_intent=request.active_intent,
            standard_categories=ticket_draft_service.STANDARD_CATEGORIES,
            leave_types=ticket_draft_service.LEAVE_TYPES,
            ticket_departments=list(TICKET_DEPARTMENTS),
            ticket_priorities=list(TICKET_PRIORITIES),
            employee_departments=[d["name"] for d in list_departments()],
            employee_roles=list(EMPLOYEE_ASSIGNMENT_ROLES),
            pending_action_context=management_action_service.format_pending_context(
                request.pending_action
            ),
            ai_service=ai_service,
        )
    except Exception:
        return _gpt_unavailable_response()

    if decision is None:
        # Defense in depth: ai_service.generate() is contractually
        # supposed to always raise AIServiceError rather than return None
        # on failure (see its docstring), so the `except` above should
        # already catch every upstream/connection failure. This guards
        # against ever dereferencing a None decision if that contract is
        # violated by a future change, instead of crashing with a 500 -
        # never fabricate an intent/request_type/ticket_draft here.
        return _gpt_unavailable_response()

    # Hard early exit: a turn GPT successfully classified as out-of-scope
    # is rejected immediately, before any active_intent/pending_action
    # continuation logic, ticket drafting, RAG, ticket-status lookup, or
    # management-action dispatch runs below - see _out_of_scope_response's
    # docstring. This check runs unconditionally every turn (never
    # skipped because active_intent/pending_action is already set), so an
    # in-progress flow can't be used to smuggle unrelated content past the
    # guardrail. Only a *successful* classification can trigger this - a
    # GPT/service failure is handled by the `except`/None-check above and
    # must never be treated as an out-of-scope refusal.
    if decision.scope == ChatScope.OUT_OF_SCOPE:
        return _out_of_scope_response()

    # A continuation always keeps the flow's intent - the model doesn't get
    # to silently change it mid-draft. A pending management action (echoed
    # back by the client) takes the same precedence as active_intent, so a
    # bare follow-up like "the VPN one" or "HD-1024" continues that flow
    # instead of being reclassified from scratch.
    pending_intent = (
        request.pending_action.action_type if request.pending_action else None
    )
    intent = request.active_intent or pending_intent or decision.intent

    if intent in _MANAGEMENT_ACTION_INTENTS:
        return management_action_service.handle_turn(
            request, decision, intent, current_user=current_user
        )

    if intent == ChatIntent.LEAVE_MANAGEMENT:
        # Hard business rule: leave requests always go through the
        # Leave Management ticket-drafting flow, regardless of the
        # action the model proposed.
        return _handle_ticket_drafting(
            request, decision, intent, classify_ticket=classify_ticket
        )

    if intent == ChatIntent.TICKET_STATUS:
        return _handle_ticket_status(
            request,
            decision,
            ticket_lookup=ticket_lookup,
            comment_lookup=comment_lookup,
            current_user=current_user,
            ai_service=ai_service,
        )

    if intent == ChatIntent.NAVIGATION:
        return _handle_navigation(decision, request.role)

    if intent == ChatIntent.START_ONBOARDING:
        return _handle_onboarding_drafting(request, decision, current_user)

    if intent in (ChatIntent.CREATE_TICKET, ChatIntent.SUPPORT_ISSUE):
        return _handle_ticket_drafting(
            request, decision, intent, classify_ticket=classify_ticket
        )

    if intent == ChatIntent.KNOWLEDGE:
        return _handle_knowledge(
            request,
            decision,
            retriever=retriever,
            ai_service=ai_service,
            current_user=current_user,
        )

    return ChatResponse(
        message=decision.message,
        intent=intent,
        suggestions=PREDEFINED_SUGGESTIONS,
    )
