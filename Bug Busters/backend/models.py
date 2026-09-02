from enum import Enum
from datetime import datetime, UTC
from pydantic import BaseModel, Field
import uuid


class PolicyStatus(str, Enum):
    draft = "draft"
    under_review = "under_review"
    active = "active"
    expired = "expired"


class PolicySource(str, Enum):
    generated = "generated"
    uploaded = "uploaded"


class ReferenceLink(BaseModel):
    title: str
    url: str
    source: str
    description: str


class StoredPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    policy_type: str
    # Only meaningful (and set) for policy_type == "Custom Section", where
    # policy_type itself isn't a real subject — see prompt_builder.py.
    # None for predefined policy types, where policy_type already names
    # the subject.
    title: str | None = None
    tone: str
    requirements: list[str]
    content: str
    status: PolicyStatus = PolicyStatus.draft
    source: PolicySource = PolicySource.generated
    original_filename: str | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    review_date: datetime | None = None
    further_reading: list[ReferenceLink] = Field(default_factory=list)


class PolicyVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str
    version: int
    content: str
    tone: str
    edited_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicySignature(BaseModel):
    policy_id: str
    # From the caller's Entra token (auth.CurrentUser), not user-supplied —
    # signed_name below is the user-typed name, kept separate so a
    # signature can't be forged by typing someone else's name while
    # authenticated as a different account.
    signer_user_id: str
    signer_roles: list[str] = Field(default_factory=list)
    signed_name: str
    signed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyAssignment(BaseModel):
    # Records that HR sent a specific policy to a specific employee.
    # Progress ("1/2 policies signed") is computed from these, scoped to
    # what an employee was actually sent — not every policy in the org.
    policy_id: str
    policy_name: str
    assigned_to_user_id: str
    assigned_by_user_id: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TicketType(str, Enum):
    feedback = "feedback"
    reminder = "reminder"
    policy_updated = "policy_updated"


class TicketStatus(str, Enum):
    open = "open"
    resolved = "resolved"


class FeedbackTicket(BaseModel):
    # Manager feedback on a policy and manager-requested signature
    # reminders land here for HR to review; applying feedback with AI
    # logs a "policy_updated" ticket as the record of what changed,
    # standing in for a real email notification (see Tickets.jsx).
    id: str = Field(default_factory=lambda: f"ticket_{uuid.uuid4().hex[:12]}")
    type: TicketType
    role: str | None = None
    title: str
    body: str
    status: TicketStatus = TicketStatus.open
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class TrainingResourceType(str, Enum):
    file = "file"
    link = "link"


class TrainingResource(BaseModel):
    # Onboarding "Train" section — handbook, articles, training links.
    # Either a real uploaded document (resource_type "file", content in
    # blob storage under source-documents) or an external link
    # (resource_type "link", just a URL) — never both.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    title: str
    description: str
    category: str
    resource_type: TrainingResourceType
    url: str | None = None
    original_filename: str | None = None
    uploaded_by_user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AdherenceAcknowledgment(BaseModel):
    # "Adhere" section — one org-wide acknowledgment per user, gating the
    # rest of the app until ticked (frontend concern; this is just the
    # persisted record of who has and hasn't acknowledged).
    org_id: str
    user_id: str
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))