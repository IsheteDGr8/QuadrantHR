from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from models.ticket import GenieChatRequest, GenieChatResponse
from services.jwt_verifier import verify_azure_user

router = APIRouter(prefix="/genie", tags=["genie"])


@router.post("/chat", response_model=GenieChatResponse)
def genie_chat(
    request: GenieChatRequest,
    current_user: dict = Depends(verify_azure_user),
):
    msg = request.message.lower().strip()

    if "ticket" in msg or "status" in msg:
        reply = (
            "You can track your submitted tickets under 'My Tickets' "
            "in the navigation bar. "
            "Your open requests are currently being processed by support staff."
        )
        suggestions = ["Check my tickets", "Create new request"]
    elif "payroll" in msg or "pay" in msg or "salary" in msg:
        reply = (
            "For payroll questions, paystub requests, or direct deposit updates, "
            "please submit a request under Payroll in the Help Center."
        )
        suggestions = ["Submit Payroll Ticket", "View Payroll FAQs"]
    elif "it" in msg or "laptop" in msg or "password" in msg or "access" in msg:
        reply = (
            "For IT issues, password resets, hardware requests, or VPN access, "
            "submit an IT Support request or contact the IT Helpdesk."
        )
        suggestions = ["IT Support Request", "Hardware Request"]
    elif "pto" in msg or "time off" in msg or "vacation" in msg or "leave" in msg:
        reply = (
            "Time off and leave requests can be submitted via the HR Portal "
            "or by opening a Time Off support request."
        )
        suggestions = ["Time Off Request", "HR Portal"]
    else:
        reply = (
            f"Hi {current_user.get('name', 'there')}! I'm Genie, your AI helpdesk assistant. "
            "I can help you search knowledge base articles, "
            "understand ticket statuses, or route you to the right department."
        )
        suggestions = ["Check my tickets", "IT help", "Payroll help", "Time off"]

    return GenieChatResponse(reply=reply, suggestions=suggestions)


# ---------------------------------------------------------------------------
# ReAct Agent Loop Engine Endpoints (Absorbs Verified User Role & Identity)
# ---------------------------------------------------------------------------


class ReActAgentRequest(BaseModel):
    message: str
    role: Optional[str] = None
    user_id: Optional[str] = None


class ExecutiveActionRequest(BaseModel):
    command: str
    user_id: Optional[str] = None


@router.post("/react")
def run_react_chat(
    req: ReActAgentRequest,
    current_user: dict = Depends(verify_azure_user),
):
    from agents.react_orchestrator import run_react_agent_loop

    # AI Agent absorbs authenticated user's verified role and OID/identity
    absorbed_role = current_user.get("role") or req.role or "Employee"
    absorbed_user_id = (
        current_user.get("oid") or current_user.get("email") or req.user_id or "user"
    )

    print(
        f"🤖 [AI Agent Security] ReAct Agent running for user '{absorbed_user_id}' with absorbed role permissions: '{absorbed_role}'"
    )

    result = run_react_agent_loop(
        user_prompt=req.message,
        role=absorbed_role,
        user_id=absorbed_user_id,
    )
    return {
        "reply": result.final_response,
        "iterations_used": result.iterations_used,
        "steps": [s.model_dump() for s in result.steps],
    }


@router.post("/exec-agent")
def handle_exec_agent_command(
    req: ExecutiveActionRequest,
    current_user: dict = Depends(verify_azure_user),
):
    from agents.exec_agent import execute_upper_management_action

    absorbed_user_id = (
        current_user.get("oid")
        or current_user.get("email")
        or req.user_id
        or "exec_user"
    )
    print(f"🤖 [AI Agent Security] Exec Agent executing for user '{absorbed_user_id}'")

    return execute_upper_management_action(
        command_prompt=req.command,
        user_id=absorbed_user_id,
    )


@router.get("/exec-briefing")
def handle_exec_briefing(current_user: dict = Depends(verify_azure_user)):
    from agents.exec_agent import get_executive_leave_briefing

    return get_executive_leave_briefing()
