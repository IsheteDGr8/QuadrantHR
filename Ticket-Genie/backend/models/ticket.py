from typing import Literal, Optional

from pydantic import BaseModel, Field

# Canonical ticket vocabulary. Single source of truth reused everywhere a
# department/priority value must be validated against the real allowed set
# (TicketCreate/CompletedTicket's Literal fields below, plus the Genie
# management-action service - see services/management_action_service.py).
TICKET_DEPARTMENTS: tuple[str, ...] = (
    "HR Team",
    "Accounting Team",
    "Workplace Operations Team",
    "IT Team",
    "Upper Management",
)
TICKET_PRIORITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    category: Optional[str] = Field(default="IT Support")
    priority: Optional[str] = Field(default="Medium")
    department: Optional[Literal[TICKET_DEPARTMENTS]] = None
    preferredDate: Optional[str] = None
    is_anonymous: bool = False
    attachment: Optional[str] = None
    requester_id: Optional[str] = None
    assigned_to: Optional[str] = None
    # Deterministic routing bypass for the small set of request types that
    # must NEVER go through AI classification (currently: Leave Management,
    # which always routes to "Upper Management" - see
    # services/ticket_draft_service.LEAVE_DEPARTMENT and
    # services/ticket_service.process_new_ticket). Distinct from
    # `department` above, which classify_ticket() always overwrites - this
    # field is the only thing that can make a submission skip
    # classification entirely. Never set from free-text/GPT output.
    department_override: Optional[Literal[TICKET_DEPARTMENTS]] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = Field(None, min_length=5)
    is_anonymous: Optional[bool] = None
    attachment: Optional[str] = None
    requester_id: Optional[str] = None
    assigned_to: Optional[str] = None


class TicketResponse(BaseModel):
    id: str
    title: str
    category: str
    priority: str
    status: str
    department: str
    description: str
    date: str
    createdAt: str
    is_anonymous: bool = False
    attachment: Optional[str] = None
    requester_id: Optional[str] = None
    assigned_to: Optional[str] = None
    requester: Optional[str] = None
    requester_name: Optional[str] = None
    classification_status: str = "Classified"
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    needs_human_review: bool = False
    model_deployment: Optional[str] = None
    onboarding_id: Optional[str] = None
    due_date: Optional[str] = None


class GenieChatRequest(BaseModel):
    message: str


class GenieChatResponse(BaseModel):
    reply: str
    suggestions: Optional[list[str]] = None


class CompletedTicket(TicketCreate):
    """A TicketCreate enriched with the AI classification result.

    This is what actually gets persisted: the raw ticket fields plus the
    department/category/priority/confidence/reason/needs_human_review
    values produced by classify_ticket(). `department` is reused from
    TicketCreate (same allowed values) rather than duplicated under a
    different name, but becomes required here since the AI always fills
    it in.
    """

    department: Literal[TICKET_DEPARTMENTS]
    category: str
    priority: Literal[TICKET_PRIORITIES]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    needs_human_review: bool
