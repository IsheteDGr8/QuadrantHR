"""Upper Management Executive Action Agent for TicketGenie.

Tailored for senior leadership and upper executive management to execute:
- Bulk conversational approvals ("Approve pending leave under 3 days")
- Auto-reassignment of unassigned high-priority tickets
- Real-time SLA & ticket resolution executive briefings
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.react_orchestrator import run_react_agent_loop
from database.crud import get_leave_tickets

logger = logging.getLogger(__name__)


def execute_upper_management_action(
    command_prompt: str,
    user_id: str = "exec_user",
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Execute an executive action or bulk command using the ReAct loop engine."""
    logger.info(f"[Executive Agent Action] command={command_prompt}")

    result = run_react_agent_loop(
        user_prompt=command_prompt,
        role="Upper Management",
        user_id=user_id,
        context=context,
    )

    return {
        "success": True,
        "executive_response": result.final_response,
        "steps_taken": [s.model_dump() for s in result.steps],
        "iterations": result.iterations_used,
    }


def get_executive_leave_briefing() -> Dict[str, Any]:
    """Generate an executive summary briefing of pending leave requests requiring review."""
    leave_tickets = get_leave_tickets()
    pending = [
        t
        for t in leave_tickets
        if (t.get("status") or "").lower() in {"open", "pending"}
    ]

    return {
        "total_leave_requests": len(leave_tickets),
        "pending_executive_approvals": len(pending),
        "tickets": pending[:10],
        "summary": f"There are currently {len(pending)} leave requests awaiting Upper Management approval.",
    }
