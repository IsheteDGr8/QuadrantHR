from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatIntent(str, Enum):
    NAVIGATION = "navigation"
    HOW_TO = "how_to"
    KNOWLEDGE = "knowledge"
    CREATE_TICKET = "create_ticket"
    LEAVE_MANAGEMENT = "leave_management"
    TICKET_STATUS = "ticket_status"
    SUPPORT_ISSUE = "support_issue"
    GENERAL = "general"
    # Management-only write actions (see services/management_action_service.py).
    # GPT may propose these for any user; services.chatbot_service always
    # re-checks the verified role deterministically before acting on them -
    # never trust the classification alone as an authorization signal.
    REASSIGN_TICKET = "reassign_ticket"
    CHANGE_PRIORITY = "change_priority"
    CREATE_PORTAL_EMPLOYEE = "create_portal_employee"
    START_ONBOARDING = "start_onboarding"
    CREATE_ANNOUNCEMENT = "create_announcement"
    DELETE_ANNOUNCEMENT = "delete_announcement"


class ChatScope(str, Enum):
    """
    Semantic scope classification for a single user turn, decided by GPT
    alongside ChatIntent (see agents/chatbot_agent.ChatbotDecision.scope).
    services.chatbot_service enforces this deterministically as a hard
    early exit BEFORE any ticket drafting, RAG retrieval, ticket-status
    lookup, or management-action dispatch - see its module docstring.
    """

    WORKPLACE = "workplace"
    OUT_OF_SCOPE = "out_of_scope"


class RequestType(str, Enum):
    """
    Which of the three existing New Request tabs a ticket_draft is meant
    for: standardRequestTab, anonymousRequestTab, or leaveRequestTab (see
    frontend/employee_NM/new-request.html). This is separate from
    ChatIntent - intent says "the user wants to submit a request";
    request_type says which existing form that request belongs in.
    """

    STANDARD = "standard"
    ANONYMOUS = "anonymous"
    LEAVE_MANAGEMENT = "leave_management"


class ChatAction(BaseModel):
    """A machine-actionable follow-up the frontend can execute."""

    type: str
    target: Optional[str] = None
    label: Optional[str] = None
    ticket_id: Optional[str] = None


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    message: str


class TicketDraft(BaseModel):
    """
    Mirrors models.ticket.TicketCreate exactly (all fields optional here
    since a draft may still be incomplete). This is never auto-submitted;
    the frontend places it into the existing Standard Request form for the
    user to review, edit, and submit via the existing POST /api/tickets flow.
    """

    title: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = None
    priority: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    # Single date, used only by the Standard/Anonymous forms' one date
    # field. For leave_management, this is a backward-compat alias of
    # startDate (kept in sync once startDate is known) - it is never the
    # source of truth for a leave range and must never be read as if it
    # implies endDate is also known. See services/ticket_draft_service.py.
    preferredDate: Optional[str] = None
    # Leave Management's date range - the only fields the leave form's
    # leaveStartDate/leaveEndDate should ever be prefilled from.
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    is_anonymous: bool = False
    attachment: Optional[str] = None


class OnboardingDraft(BaseModel):
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    job_title: Optional[str] = None
    employee_department: Optional[str] = None

    manager: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None


class TicketCandidate(BaseModel):
    """Minimum info shown when Genie must ask the user which ticket they mean."""

    id: str
    title: str
    department: str
    priority: str
    status: str


class PendingManagementAction(BaseModel):
    """
    Structured, client-echoed state for an in-progress management write
    action (reassign_ticket / change_priority / create_portal_employee).
    Mirrors how `draft`/`active_intent` already carry ticket-drafting state
    across turns - the backend stays stateless, the frontend just echoes
    back whatever the previous ChatResponse.pending_action was.

    `awaiting` names exactly what the next user turn is expected to resolve,
    so services.management_action_service never has to re-guess intent
    from free text alone: "ticket_selection" | "ticket_confirmation" |
    "target_department" | "target_priority" | "employee_field:<name>" |
    "employee_confirmation".
    """

    action_type: ChatIntent
    awaiting: Optional[str] = None

    # Ticket mutation fields (reassign_ticket / change_priority)
    ticket_id: Optional[str] = None
    ticket_title: Optional[str] = None
    current_department: Optional[str] = None
    current_priority: Optional[str] = None
    target_department: Optional[str] = None
    target_priority: Optional[str] = None
    candidate_tickets: List[TicketCandidate] = Field(default_factory=list)

    # Employee creation fields (create_portal_employee)
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    employee_object_id: Optional[str] = None
    employee_role: Optional[str] = None
    employee_department: Optional[str] = None

    # Echoed conversation state only; authorization is re-checked each turn.
    announcement_id: Optional[str] = None
    announcement_title: Optional[str] = None
    announcement_content: Optional[str] = None
    announcement_category: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    role: Optional[str] = "Employee"
    department: Optional[str] = None
    history: List[ChatTurn] = Field(default_factory=list)
    draft: Optional[TicketDraft] = None
    onboarding_draft: Optional[OnboardingDraft] = None
    # Set when the intent is already known without needing the model to
    # (re)classify it - either the user clicked a predefined option
    # (navigation/how-to don't need this; ticket-drafting/status/knowledge
    # buttons do), or this turn continues an in-progress drafting flow by
    # echoing the previous ChatResponse.intent.
    active_intent: Optional[ChatIntent] = None
    # Echo of the previous ChatResponse.request_type, so a continuation
    # turn doesn't have to re-derive (or risk flip-flopping) which of the
    # three forms this draft belongs to.
    active_request_type: Optional[RequestType] = None
    # Echo of the previous ChatResponse.pending_action, carrying an
    # in-progress management write action across turns (see
    # PendingManagementAction). Employee-portal requests never set this.
    pending_action: Optional[PendingManagementAction] = None
    # Id of a persisted Genie AI page conversation (services/conversation_service.py)
    # this turn belongs to. None for a brand-new chat - the backend then
    # lazily creates the conversation on the first turn instead of an
    # empty/junk row up front. Ownership is always re-verified server-side
    # against the authenticated user, never trusted from this field alone.
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    intent: ChatIntent
    action: Optional[ChatAction] = None
    request_type: Optional[RequestType] = None
    ticket_draft: Optional[TicketDraft] = None
    onboarding_draft: Optional[OnboardingDraft] = None
    missing_fields: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    knowledge_verified: Optional[bool] = None
    # True only once the draft has every required field for its
    # request_type and the frontend should open/prefill the matching form.
    # Never implies auto-submit - the user still must click the existing
    # submit button on that form.
    ready_for_review: bool = False
    # Set (and must be echoed back verbatim as ChatRequest.pending_action)
    # whenever a management write action is still awaiting information or
    # confirmation. Cleared once the action executes or is cancelled.
    pending_action: Optional[PendingManagementAction] = None
    # Populated only when pending_action.awaiting == "ticket_selection", so
    # the frontend can render the exact candidates the user is choosing
    # between (id + title + priority + status, never a raw SQL/DB dump).
    ticket_candidates: List[TicketCandidate] = Field(default_factory=list)
    # Id of the persisted Genie AI page conversation this turn was saved
    # under (see api/chatbot.py::chatbot_message). Set by the route layer
    # after handle_message() returns, not by handle_message() itself.
    conversation_id: Optional[str] = None
