from enum import Enum
from io import BytesIO

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from openai_service import OpenAIService
from prompt_builder import build_policy_prompt, build_policy_chat_prompt
from logger import get_logger
from policy_repository import (
    create_policy,
    get_policy,
    list_policies,
    update_policy,
    get_policy_history,
)
from models import StoredPolicy, PolicySource, TicketType
from file_service import policy_to_docx_bytes, policy_to_pdf_bytes
from document_parser import extract_text_from_upload, UnsupportedFileTypeError
from search_service import get_reference_links
from auth import get_current_user, require_role
from signature_repository import sign_policy, get_signature, list_signatures
from assignment_repository import assign_policy, list_user_assignments
from feedback_repository import create_ticket, list_tickets, resolve_ticket
from training_repository import (
    create_link_resource,
    create_file_resource,
    get_resource,
    get_resource_file_bytes,
    list_resources,
)
from adherence_repository import acknowledge, get_acknowledgment
from training_agent import generate_metadata as generate_training_metadata, TrainingAgentError
from incident_policy_agent import draft_from_incident, IncidentPolicyAgentError
from incident_report_agent import (
    reply_to_incident_message,
    summarize_incident,
    IncidentReportAgentError,
)
from demo_login_db import init_demo_db
from demo_login_repository import get_user_by_email
from questionnaire_agent import generate_questions, QuestionnaireAgentError
from chat_agent import answer_chat_message, interpret_chat_intent, ChatAgentError


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title="Policy Guardian API",
    description=(
        "Backend API for generating, refining, storing, "
        "retrieving, and exporting HR policies using Azure OpenAI."
    ),
    version="1.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://gray-sky-0be5fb50f.7.azurestaticapps.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


openai_service = OpenAIService()
logger = get_logger(__name__)

# Demo login fallback - see demo_login_db.py. Safe/idempotent to run on
# every startup; only creates the table + seed rows if they don't exist.
init_demo_db()


# --------------------------------------------------
# Enums
# --------------------------------------------------

class PolicyType(str, Enum):
    work_from_home = "Work From Home"
    paid_time_off = "Paid Time Off"
    code_of_conduct = "Code of Conduct"
    expense_reimbursement = "Expense Reimbursement"
    custom_section = "Custom Section"

    attendance = "Attendance Policy"
    leave = "Leave Policy"
    dress_code = "Dress Code"
    security = "Security Policy"
    travel = "Travel Policy"
    remote_work = "Remote Work Policy"


class Tone(str, Enum):
    professional = "Professional"
    formal = "Formal"
    friendly = "Friendly"
    simple = "Simple"


# --------------------------------------------------
# Request Models
# --------------------------------------------------

class PolicyRequest(BaseModel):
    company_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    policy_type: PolicyType
    tone: Tone

    # Required when policy_type is "Custom Section" — otherwise the AI has
    # no actual subject to write about, since "Custom Section" itself
    # isn't a topic (see build_policy_prompt). Optional for the other,
    # predefined policy types.
    title: str | None = Field(
        default=None,
        max_length=150,
    )

    requirements: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        return value or None

    # Optional — when the caller already has finished policy text (e.g. a
    # section a user has edited/reworded in the frontend), pass it here to
    # store it as-is instead of having this endpoint generate new content
    # from `requirements`. Lets "save for export" reflect exactly what's on
    # screen rather than a fresh, possibly different AI generation.
    content: str | None = Field(
        default=None,
        max_length=20000,
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        return value or None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Company name cannot be blank.")

        return value

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, requirements: list[str]):
        cleaned_requirements = []

        for requirement in requirements:
            requirement = requirement.strip()

            if not requirement:
                raise ValueError("Requirements cannot be blank.")

            cleaned_requirements.append(requirement)

        return cleaned_requirements

    @model_validator(mode="after")
    def validate_custom_section_has_title(self):
        if self.policy_type == PolicyType.custom_section and not self.title:
            raise ValueError(
                "title is required when policy_type is 'Custom Section' — "
                "otherwise there's no actual subject for the policy."
            )

        return self


class PolicyChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    text: str = Field(..., min_length=1, max_length=2000)


class PolicyChatRequest(BaseModel):
    # Was max_length=20 - too low for a real back-and-forth (user+
    # assistant turns both count), so a long conversation could 422 right
    # as someone was trying to wrap it up. 60 gives real headroom (~30
    # user turns) while prompt_builder.py's build_policy_chat_prompt
    # nudges the model toward READY well before that.
    messages: list[PolicyChatMessage] = Field(..., min_length=1, max_length=60)


class IncidentMessagesRequest(BaseModel):
    messages: list[PolicyChatMessage] = Field(..., min_length=1, max_length=60)


class RefinePolicyRequest(BaseModel):
    current_policy: str = Field(
        ...,
        min_length=10,
        max_length=20000,
    )

    instruction: str = Field(
        ...,
        min_length=3,
        max_length=500,
    )

    @field_validator("current_policy", "instruction")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be blank.")

        return value


class AskAIRequest(BaseModel):
    highlighted_text: str = Field(
        ...,
        min_length=3,
        max_length=20000,
    )

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
    )

    @field_validator("highlighted_text", "question")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be blank.")

        return value


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("message cannot be blank.")

        return value


class ChatScreenOption(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)


class ChatIntentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    # The frontend's screenKnowledgeBase.js is the single source of truth
    # for what screens exist - passed in per-request rather than
    # duplicated/hardcoded here, so a new screen only needs to be added
    # in one place.
    screens: list[ChatScreenOption] = Field(default_factory=list, max_length=50)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("message cannot be blank.")

        return value


class DemoLoginRequest(BaseModel):
    # Demo-only fallback for when real Entra login is unavailable - see
    # demo_login_db.py. No password field on purpose: this is an email
    # lookup, not authentication.
    email: str = Field(..., min_length=3, max_length=200)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("email cannot be blank.")

        return value


class GenerateQuestionsRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    policy_type: str | None = Field(default=None, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("title cannot be blank.")

        return value


class UpdatePolicyRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=20000)
    edited_by: str | None = None


class SignPolicyRequest(BaseModel):
    # The name the user types to sign, e.g. "Jane Doe" — kept separate
    # from their authenticated identity (see PolicySignature) so this is
    # "how they want their name recorded," not "who they are."
    signed_name: str = Field(..., min_length=2, max_length=150)

    @field_validator("signed_name")
    @classmethod
    def validate_signed_name(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("signed_name cannot be blank.")

        return value


class AssignPolicyRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=200)


class CreateTicketRequest(BaseModel):
    type: TicketType
    role: str | None = None
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)


class TrainingLinkRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=2, max_length=500)
    category: str = Field(..., min_length=2, max_length=100)
    url: str = Field(..., min_length=5, max_length=2000)

    @field_validator("title", "description", "category", "url")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be blank.")

        return value


class DraftPolicyFromIncidentRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    incident_summary: str = Field(..., min_length=10, max_length=20000)
    # Optional follow-up Q&A from the Incident Report Assistant, if the
    # caller has it (see incident-assistant/'s ticket schema) — sharpens
    # the draft without requiring it.
    context: str | None = Field(default=None, max_length=5000)

    @field_validator("company_name", "incident_summary")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be blank.")

        return value


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get(
    "/",
    tags=["Health"],
    summary="Backend health check",
)
def home():
    return {
        "message": "Backend is working!"
    }


# --------------------------------------------------
# AI Policy Generation
# --------------------------------------------------

@app.post(
    "/generate-policy",
    tags=["AI Policies"],
    summary="Generate a new HR policy",
)
def generate_policy_endpoint(
    request: PolicyRequest,
    user=Depends(require_role("HR")),
):

    logger.info(
        f"Received policy generation request: "
        f"company={request.company_name}, "
        f"type={request.policy_type.value}, "
        f"tone={request.tone.value}"
    )

    try:
        prompt = build_policy_prompt(
            company_name=request.company_name,
            policy_type=request.policy_type.value,
            tone=request.tone.value,
            requirements=request.requirements,
            title=request.title,
        )

        policy = openai_service.generate_policy(prompt)

    except Exception as e:
        logger.error(f"Policy generation failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to generate policy. Please try again.",
        )

    logger.info(
        f"Successfully generated policy for {request.company_name}"
    )

    further_reading = get_reference_links(request.policy_type.value)

    return {
        "policy": policy,
        "further_reading": further_reading,
    }


# --------------------------------------------------
# Agentic Policy Chat — smart follow-up questions while drafting a new
# section, instead of a fixed field form.
# --------------------------------------------------

@app.post(
    "/policy-chat",
    tags=["AI Policies"],
    summary="Ask a follow-up question while drafting a new policy section",
)
def policy_chat_endpoint(
    request: PolicyChatRequest,
    user=Depends(require_role("HR")),
):
    logger.info("Received policy chat request")

    try:
        prompt = build_policy_chat_prompt(
            [{"role": m.role, "text": m.text} for m in request.messages]
        )

        reply = openai_service.generate_policy(prompt)

    except Exception as e:
        logger.error(f"Policy chat failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to get a response. Please try again.",
        )

    return {"reply": reply.strip()}


# --------------------------------------------------
# Incident Report Assistant — the private chat + summary tool on the
# Incident Report page (Frontend/src/pages/IncidentReport.jsx). Separate
# from Incident-to-Policy below: this drafts a summary of what happened,
# not a policy.
# --------------------------------------------------

@app.post(
    "/incident/reply",
    tags=["Incident Report"],
    summary="Ask a follow-up question while describing an incident",
)
def incident_reply_endpoint(
    request: IncidentMessagesRequest,
    user=Depends(require_role("HR")),
):
    logger.info("Received incident report reply request")

    try:
        reply = reply_to_incident_message(
            [{"role": m.role, "text": m.text} for m in request.messages]
        )
    except IncidentReportAgentError as e:
        logger.error(f"Incident report reply failed: {e}")

        if e.content_filtered:
            raise HTTPException(status_code=422, detail=str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to get a response. Please try again.",
        )

    return {"reply": reply}


@app.post(
    "/incident/summarize",
    tags=["Incident Report"],
    summary="Summarize an incident conversation into a report + next steps",
)
def incident_summarize_endpoint(
    request: IncidentMessagesRequest,
    user=Depends(require_role("HR")),
):
    logger.info("Received incident report summarize request")

    try:
        result = summarize_incident(
            [{"role": m.role, "text": m.text} for m in request.messages]
        )
    except IncidentReportAgentError as e:
        logger.error(f"Incident report summarize failed: {e}")

        if e.content_filtered:
            raise HTTPException(status_code=422, detail=str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to generate a summary. Please try again.",
        )

    return result


# --------------------------------------------------
# AI Policy Refinement
# --------------------------------------------------

@app.post(
    "/refine-policy",
    tags=["AI Policies"],
    summary="Refine an existing HR policy",
)
def refine_policy_endpoint(
    request: RefinePolicyRequest,
    user=Depends(require_role("HR")),
):

    logger.info("Received policy refinement request")

    prompt = f"""
You are an experienced HR policy writer.

Below is the exact text selected by the user:

--- SELECTED TEXT ---
{request.current_policy}
--- END SELECTED TEXT ---

User instruction:
{request.instruction}

Revise only the selected text according to the user's instruction.

Important rules:
- Return only the revised text.
- Do not add headings, titles, labels, bullet points, or section names unless they already exist in the selected text.
- Do not add explanations before or after the revised text.
- Preserve the meaning unless the user's instruction specifically asks for a change.
- Keep the response concise and appropriate for a professional HR policy.
"""

    try:
        refined_policy = openai_service.generate_policy(prompt)

    except Exception as e:
        logger.error(f"Policy refinement failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to refine policy. Please try again.",
        )

    logger.info("Successfully refined policy")

    return {
        "policy": refined_policy
    }

# --------------------------------------------------
# Ask AI About Selected Policy Text
# --------------------------------------------------

@app.post(
    "/ask-ai",
    tags=["AI Policies"],
    summary="Ask AI a question about selected policy text",
)
def ask_ai(request: AskAIRequest, user=Depends(get_current_user)):
    logger.info("Received Ask AI request")

    try:
        prompt = f"""
You are an HR policy assistant.

The user selected this text from an HR policy:

--- SELECTED TEXT ---
{request.highlighted_text}
--- END SELECTED TEXT ---

User question:
{request.question}

Answer the user's question clearly and concisely.

Important rules:
- Answer only based on the selected policy text.
- Do not invent company-specific information.
- Explain the text in clear, easy-to-understand language.
- Do not rewrite the policy unless the user specifically asks for an explanation of wording.
"""

        answer = openai_service.generate_policy(prompt)

        logger.info("Successfully answered Ask AI question")

        return {
            "answer": answer
        }

    except Exception as e:
        logger.error(f"Ask AI failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to answer question. Please try again.",
        )


# --------------------------------------------------
# Demo Login (fallback)
#
# Deliberately isolated from the real Entra/MSAL auth flow (auth.py,
# get_current_user, require_role): no JWT, no token, no role check on
# this endpoint itself - it exists to hand out a role, not to guard one.
# Swap the frontend between this and real MSAL login without touching
# either implementation. See demo_login_db.py for why SQLite / why this
# is the only SQL table in the project.
# --------------------------------------------------

@app.post(
    "/demo-login",
    tags=["Demo Login"],
    summary="Look up a demo user's role by email (no password/token check)",
)
def demo_login(request: DemoLoginRequest):
    demo_user = get_user_by_email(request.email)

    if demo_user is None:
        raise HTTPException(
            status_code=404,
            detail="No demo user found with that email.",
        )

    return demo_user


# --------------------------------------------------
# Mini Chat Widget
#
# No auth dependency: MiniChatWidget.jsx renders on the public Landing
# page (no signed-in user yet) as well as HRDashboard, so this can't
# require a role or even a token the way /ask-ai does. chat_agent.py's
# prompt is written to not assume any org/role context accordingly.
# --------------------------------------------------

@app.post(
    "/chat",
    tags=["Chat Widget"],
    summary="Answer a general question from the mini chat widget",
)
def chat_widget_endpoint(request: ChatMessageRequest):
    try:
        answer = answer_chat_message(request.message)
    except ChatAgentError as e:
        logger.error(f"Chat widget reply failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to get a response. Please try again.",
        )

    return {"answer": answer}


@app.post(
    "/chat/intent",
    tags=["Chat Widget"],
    summary="Classify whether a chat message wants a theme change, navigation, or neither",
)
def chat_intent_endpoint(request: ChatIntentRequest):
    try:
        result = interpret_chat_intent(
            request.message,
            [s.model_dump() for s in request.screens],
        )
    except ChatAgentError as e:
        logger.error(f"Chat intent classification failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to classify that message. Please try again.",
        )

    return result


# --------------------------------------------------
# Policy Storage
# --------------------------------------------------

@app.post(
    "/policies",
    tags=["Policy Storage"],
    summary="Generate and save a policy",
)
def save_generated_policy(
    org_id: str,
    request: PolicyRequest,
    user=Depends(get_current_user),
):

    logger.info(
        f"Saving generated policy for "
        f"org={org_id}, company={request.company_name}"
    )

    try:
        if request.content is not None:
            content = request.content
        else:
            prompt = build_policy_prompt(
                company_name=request.company_name,
                policy_type=request.policy_type.value,
                tone=request.tone.value,
                requirements=request.requirements,
                title=request.title,
            )

            content = openai_service.generate_policy(prompt)

        policy = StoredPolicy(
            company_name=request.company_name,
            policy_type=request.policy_type.value,
            title=request.title,
            tone=request.tone.value,
            requirements=request.requirements,
            content=content,
            further_reading=get_reference_links(request.policy_type.value),
        )

        saved = create_policy(
            org_id,
            policy,
        )

    except Exception as e:
        logger.error(f"Failed to save policy: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to save policy. Please try again.",
        )

    logger.info(
        f"Successfully saved policy for org={org_id}"
    )

    return saved


@app.get(
    "/policies/{org_id}/{policy_id}",
    tags=["Policy Storage"],
    summary="Retrieve one saved policy",
)
def fetch_policy(
    org_id: str,
    policy_id: str,
    user=Depends(get_current_user),
):

    policy = get_policy(
        org_id,
        policy_id,
    )

    if not policy:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    return policy


@app.get(
    "/policies/{org_id}",
    tags=["Policy Storage"],
    summary="Retrieve all policies for an organization",
)
def fetch_all_policies(org_id: str, user=Depends(get_current_user)):
    return list_policies(org_id)


@app.post(
    "/policies/{org_id}/upload",
    tags=["Policy Storage"],
    summary="Upload an existing policy",
)
async def upload_policy(
    org_id: str,
    company_name: str = Form(...),
    policy_type: PolicyType = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_role("HR")),
):
    logger.info(
        f"Received policy upload for org={org_id}, filename={file.filename}"
    )

    try:
        file_bytes = await file.read()
        extracted_text = extract_text_from_upload(file.filename, file_bytes)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract any text from the uploaded file.",
            )

        policy = StoredPolicy(
            company_name=company_name,
            policy_type=policy_type.value,
            tone="Uploaded",
            requirements=[],
            content=extracted_text,
            source=PolicySource.uploaded,
            original_filename=file.filename,
        )

        saved = create_policy(org_id, policy)

    except UnsupportedFileTypeError as e:
        logger.warning(f"Unsupported upload type: {e}")

        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Policy upload failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to upload policy. Please try again.",
        )

    logger.info(f"Successfully uploaded and saved policy for org={org_id}")

    return saved


@app.patch(
    "/policies/{org_id}/{policy_id}",
    tags=["Policy Storage"],
    summary="Edit a saved policy (creates a new version)",
)
def edit_policy(
    org_id: str,
    policy_id: str,
    request: UpdatePolicyRequest,
    user=Depends(require_role("HR")),
):
    updated = update_policy(
        org_id,
        policy_id,
        {"content": request.content},
        edited_by=request.edited_by,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    return updated


@app.get(
    "/policies/{org_id}/{policy_id}/history",
    tags=["Policy Storage"],
    summary="Get version history for a policy",
)
def policy_history(
    org_id: str,
    policy_id: str,
    user=Depends(require_role("HR")),
):
    return get_policy_history(org_id, policy_id)


# --------------------------------------------------
# Policy Signatures
# --------------------------------------------------

@app.post(
    "/policies/{org_id}/{policy_id}/sign",
    tags=["Policy Signatures"],
    summary="Sign a policy as the current user",
)
def sign_policy_endpoint(
    org_id: str,
    policy_id: str,
    request: SignPolicyRequest,
    user=Depends(get_current_user),
):
    policy = get_policy(org_id, policy_id)

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    signature = sign_policy(
        org_id,
        policy_id,
        signer_user_id=user.object_id,
        signer_roles=user.roles,
        signed_name=request.signed_name,
    )

    logger.info(f"Policy {policy_id} signed by user {user.object_id} for org {org_id}")

    return signature


@app.get(
    "/policies/{org_id}/{policy_id}/signed-by-me",
    tags=["Policy Signatures"],
    summary="Check whether the current user has signed a policy",
)
def signed_by_me(
    org_id: str,
    policy_id: str,
    user=Depends(get_current_user),
):
    signature = get_signature(org_id, policy_id, user.object_id)

    return {"signed": signature is not None, "signature": signature}


@app.get(
    "/policies/{org_id}/{policy_id}/signatures",
    tags=["Policy Signatures"],
    summary="List everyone who has signed a policy (HR/Manager progress view)",
)
def policy_signatures(
    org_id: str,
    policy_id: str,
    user=Depends(require_role("HR", "Manager")),
):
    return list_signatures(org_id, policy_id)


# --------------------------------------------------
# Policy Assignments — HR sends specific policies to specific employees;
# this is what "1/2 policies signed" progress is actually measured
# against, not every policy in the org.
# --------------------------------------------------

@app.post(
    "/policies/{org_id}/{policy_id}/assign",
    tags=["Policy Assignments"],
    summary="Assign a policy to one or more employees (HR only)",
)
def assign_policy_endpoint(
    org_id: str,
    policy_id: str,
    request: AssignPolicyRequest,
    user=Depends(require_role("HR")),
):
    policy = get_policy(org_id, policy_id)

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy_name = policy.title if policy.title else policy.policy_type

    assignments = [
        assign_policy(
            org_id,
            policy_id,
            policy_name=policy_name,
            assigned_to_user_id=recipient_id,
            assigned_by_user_id=user.object_id,
        )
        for recipient_id in request.user_ids
    ]

    logger.info(
        f"Policy {policy_id} assigned to {len(assignments)} user(s) for org {org_id}"
    )

    return assignments


@app.get(
    "/policies/{org_id}/users/{user_id}/progress",
    tags=["Policy Assignments"],
    summary="Signing progress for one employee (e.g. '1/2 policies signed')",
)
def user_progress(
    org_id: str,
    user_id: str,
    user=Depends(get_current_user),
):
    # Anyone can check their own progress; checking someone else's is an
    # HR/Manager oversight action, not something every role gets.
    if user_id != user.object_id and not (
        user.has_role("HR") or user.has_role("Manager")
    ):
        raise HTTPException(
            status_code=403,
            detail="Can only view your own progress unless you're HR or a Manager.",
        )

    assignments = list_user_assignments(org_id, user_id)

    policies = [
        {
            "policy_id": assignment.policy_id,
            "policy_name": assignment.policy_name,
            "signed": get_signature(org_id, assignment.policy_id, user_id) is not None,
        }
        for assignment in assignments
    ]

    signed_count = sum(1 for p in policies if p["signed"])

    return {
        "assigned": len(policies),
        "signed": signed_count,
        "policies": policies,
    }


# --------------------------------------------------
# Tickets — manager feedback on a policy and manager-requested signature
# reminders land here for HR to review (see feedback_repository.py).
# Any signed-in role can create one (an employee sending feedback, a
# manager sending a reminder, or HR itself logging a policy_updated
# entry after applying feedback) - listing and resolving are HR-only,
# since Tickets.jsx is only reachable from the HR dashboard.
# --------------------------------------------------

@app.post(
    "/tickets/{org_id}",
    tags=["Tickets"],
    summary="Create a feedback, reminder, or policy-updated ticket",
)
def create_ticket_endpoint(
    org_id: str,
    request: CreateTicketRequest,
    user=Depends(get_current_user),
):
    return create_ticket(
        org_id,
        type=request.type,
        role=request.role,
        title=request.title,
        body=request.body,
        created_by=user.object_id,
    )


@app.get(
    "/tickets/{org_id}",
    tags=["Tickets"],
    summary="List all tickets for an org (HR only)",
)
def list_tickets_endpoint(
    org_id: str,
    user=Depends(require_role("HR")),
):
    return list_tickets(org_id)


@app.patch(
    "/tickets/{org_id}/{ticket_id}/resolve",
    tags=["Tickets"],
    summary="Mark a ticket resolved (HR only)",
)
def resolve_ticket_endpoint(
    org_id: str,
    ticket_id: str,
    user=Depends(require_role("HR")),
):
    ticket = resolve_ticket(org_id, ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket


# --------------------------------------------------
# Policy Export
# --------------------------------------------------

@app.get(
    "/policies/{org_id}/{policy_id}/export/docx",
    tags=["Policy Export"],
    summary="Export a saved policy as DOCX",
)
def export_policy_docx(
    org_id: str,
    policy_id: str,
    user=Depends(get_current_user),
):

    policy = get_policy(
        org_id,
        policy_id,
    )

    if not policy:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    try:
        # For Custom Section policies, policy_type isn't a real subject
        # (see prompt_builder.py) — use the actual title instead so the
        # export isn't literally named "{company} Custom Section".
        subject = policy.title if (policy.policy_type == "Custom Section" and policy.title) else policy.policy_type
        title = (
            f"{policy.company_name} "
            f"{subject}"
        )

        docx_bytes = policy_to_docx_bytes(
            policy.content,
            title,
        )

        return StreamingResponse(
            BytesIO(docx_bytes),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f'attachment; filename="{policy_id}.docx"'
            },
        )

    except Exception as e:
        logger.error(f"DOCX export failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to export policy as DOCX.",
        )


@app.get(
    "/policies/{org_id}/{policy_id}/export/pdf",
    tags=["Policy Export"],
    summary="Export a saved policy as PDF",
)
def export_policy_pdf(
    org_id: str,
    policy_id: str,
    user=Depends(get_current_user),
):

    policy = get_policy(
        org_id,
        policy_id,
    )

    if not policy:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    try:
        # For Custom Section policies, policy_type isn't a real subject
        # (see prompt_builder.py) — use the actual title instead so the
        # export isn't literally named "{company} Custom Section".
        subject = policy.title if (policy.policy_type == "Custom Section" and policy.title) else policy.policy_type
        title = (
            f"{policy.company_name} "
            f"{subject}"
        )

        pdf_bytes = policy_to_pdf_bytes(
            policy.content,
            title,
        )

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{policy_id}.pdf"'
            },
        )

    except Exception as e:
        logger.error(f"PDF export failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to export policy as PDF.",
        )


# --------------------------------------------------
# Training Resources — onboarding "Train" section: handbook, articles,
# training links. Creating/uploading is HR only; viewing is open to
# everyone, since the whole point is that employees can access these.
# --------------------------------------------------

@app.post(
    "/training/{org_id}/link",
    tags=["Training"],
    summary="Add a training resource that's an external link",
)
def add_training_link(
    org_id: str,
    request: TrainingLinkRequest,
    user=Depends(require_role("HR")),
):
    return create_link_resource(
        org_id,
        title=request.title,
        description=request.description,
        category=request.category,
        url=request.url,
        uploaded_by_user_id=user.object_id,
    )


@app.post(
    "/training/{org_id}/upload",
    tags=["Training"],
    summary="Upload a training document (e.g. the employee handbook)",
)
async def upload_training_file(
    org_id: str,
    # All optional — the whole point is HR shouldn't have to type these.
    # An agent generates whichever ones aren't provided, from the
    # document's actual content. Still overridable per-field if HR wants
    # to correct or skip the AI for a specific upload.
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
    file: UploadFile = File(...),
    user=Depends(require_role("HR")),
):
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if not (title and description and category):
        try:
            extracted_text = extract_text_from_upload(file.filename, file_bytes)
            generated = generate_training_metadata(file.filename, extracted_text)
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except TrainingAgentError as e:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Couldn't auto-generate title/description/category "
                    f"for this file ({e}). Provide them manually instead."
                ),
            )

        title = title or generated["title"]
        description = description or generated["description"]
        category = category or generated["category"]

    return create_file_resource(
        org_id,
        title=title,
        description=description,
        category=category,
        original_filename=file.filename,
        file_bytes=file_bytes,
        uploaded_by_user_id=user.object_id,
    )


@app.get(
    "/training/{org_id}",
    tags=["Training"],
    summary="List all training resources for an org",
)
def list_training_resources(org_id: str, user=Depends(get_current_user)):
    return list_resources(org_id)


@app.get(
    "/training/{org_id}/{resource_id}/download",
    tags=["Training"],
    summary="Download a training file resource",
)
def download_training_resource(
    org_id: str,
    resource_id: str,
    user=Depends(get_current_user),
):
    resource = get_resource(org_id, resource_id)

    if not resource:
        raise HTTPException(status_code=404, detail="Training resource not found")

    if resource.resource_type != "file":
        raise HTTPException(
            status_code=400,
            detail="This resource is a link, not a downloadable file.",
        )

    file_bytes = get_resource_file_bytes(org_id, resource_id)

    if file_bytes is None:
        raise HTTPException(status_code=404, detail="File content not found")

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{resource.original_filename}"'
        },
    )


# --------------------------------------------------
# Adherence — onboarding "Adhere" section: one org-wide acknowledgment
# per user. Frontend gates other features on this; the backend just
# persists who has and hasn't acknowledged.
# --------------------------------------------------

@app.post(
    "/adherence/{org_id}/acknowledge",
    tags=["Adherence"],
    summary="Acknowledge the company's general rules",
)
def acknowledge_adherence(org_id: str, user=Depends(get_current_user)):
    return acknowledge(org_id, user.object_id)


@app.get(
    "/adherence/{org_id}/acknowledged-by-me",
    tags=["Adherence"],
    summary="Check whether the current user has acknowledged the company's general rules",
)
def adherence_status(org_id: str, user=Depends(get_current_user)):
    acknowledgment = get_acknowledgment(org_id, user.object_id)

    return {"acknowledged": acknowledgment is not None, "acknowledgment": acknowledgment}


# --------------------------------------------------
# Incident-to-Policy — the "agentic" half of the incident report copy
# button (task #7): rather than HR pasting raw incident text into the
# custom-section form and writing the policy themselves, an agent drafts
# a real title + requirements + generated policy content from it. This
# is a draft only — nothing is saved until HR reviews it and calls
# POST /policies themselves, same as any other generated policy.
# --------------------------------------------------

@app.post(
    "/policies/{org_id}/from-incident",
    tags=["AI Policies"],
    summary="Draft a custom policy from an incident report (not saved)",
)
def draft_policy_from_incident_endpoint(
    org_id: str,
    request: DraftPolicyFromIncidentRequest,
    user=Depends(require_role("HR")),
):
    try:
        draft = draft_from_incident(request.incident_summary, request.context)
    except IncidentPolicyAgentError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Couldn't draft a policy from this incident ({e}). "
                f"Use the custom section form to write one manually instead."
            ),
        )

    try:
        prompt = build_policy_prompt(
            company_name=request.company_name,
            policy_type="Custom Section",
            tone=Tone.professional.value,
            requirements=draft["requirements"],
            title=draft["title"],
        )
        content = openai_service.generate_policy(prompt)
    except Exception as e:
        logger.error(f"Policy generation from incident draft failed: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to generate policy content from the draft. Please try again.",
        )

    return {
        "title": draft["title"],
        "requirements": draft["requirements"],
        "policy": content,
        "further_reading": get_reference_links(draft["title"]),
    }


# --------------------------------------------------
# Agentic Questionnaire
#
# Replaces the frontend's static, generic Custom Section questions
# (Frontend/src/Data/policyTemplates.js's `custom` entry) with ones
# tailored to whatever the HR person actually typed as a title - e.g.
# "Office Pet Policy" gets asked about pet types and approval, not a
# generic "what is the purpose of this section?".
# --------------------------------------------------

@app.post(
    "/questionnaire/generate",
    tags=["AI Policies"],
    summary="Generate tailored questionnaire fields for a policy section title",
)
def generate_questionnaire_endpoint(
    request: GenerateQuestionsRequest,
    user=Depends(require_role("HR")),
):
    try:
        questions = generate_questions(request.title, request.policy_type)
    except QuestionnaireAgentError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Couldn't generate tailored questions for this title ({e}). "
                f"Use the generic questionnaire fields instead."
            ),
        )

    return {"questions": questions}