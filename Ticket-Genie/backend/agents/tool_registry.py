"""Tool Registry for TicketGenie ReAct Agent Loop Engine.

Defines available tools (SQL query, ticket updates, knowledge search,
bulk leave approvals, document generation) and tool execution dispatches.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from database.crud import get_all_tickets, update_ticket
from models.ticket import TICKET_DEPARTMENTS, TICKET_PRIORITIES, TicketUpdate
from services.knowledge_service import answer_question
from services.role_service import is_ticket_mutation_authorized
from services.sql_context_service import execute_sql_query

logger = logging.getLogger(__name__)


def sql_query_tool(query: str, role: str = "Admin", user_id: str = "user") -> str:
    """Execute a role-scoped SELECT or controlled UPDATE query on the database."""
    res = execute_sql_query(query, role=role, user_id=user_id)
    return json.dumps(res, default=str)


def update_ticket_tool(
    ticket_id: str, field: str, value: str, user_id: str = "user"
) -> str:
    """Update a specific field (department, priority, status, queue) on a ticket.

    Authorization is enforced by the caller (execute_tool) before this is
    invoked. This function still deterministically validates department/
    priority values against the canonical ticket vocabulary (models.ticket)
    so GPT can never write an invented value even if it somehow bypasses
    the ReAct prompt's few-shot examples.
    """
    valid_fields = {"department", "priority", "status", "queue", "category", "title"}
    if field not in valid_fields:
        return f"Error: Cannot update field '{field}'. Allowed fields: {valid_fields}"

    if field == "department" and value not in TICKET_DEPARTMENTS:
        return f"Error: '{value}' is not a valid department. Allowed: {', '.join(TICKET_DEPARTMENTS)}"
    if field == "priority" and value not in TICKET_PRIORITIES:
        return f"Error: '{value}' is not a valid priority. Allowed: {', '.join(TICKET_PRIORITIES)}"

    if field == "status" and (value or "").strip().lower() in ("resolved", "closed"):
        from database.crud import _resolve_user_email, get_ticket_by_id

        ticket = get_ticket_by_id(ticket_id)
        if ticket:
            req_id = str(ticket.get("requester_id") or "").strip().lower()
            uid = str(user_id or "").strip().lower()
            is_creator = False
            if req_id and uid:
                if req_id == uid:
                    is_creator = True
                else:
                    resolved_req = (
                        str(_resolve_user_email(req_id, None) or "").strip().lower()
                    )
                    resolved_uid = (
                        str(_resolve_user_email(uid, None) or "").strip().lower()
                    )
                    if resolved_req and (
                        resolved_req == uid or resolved_req == resolved_uid
                    ):
                        is_creator = True
            if is_creator:
                return "Error: Forbidden. You cannot resolve tickets you created."

    update_payload = TicketUpdate(**{field: value})
    res = update_ticket(ticket_id, update_payload)
    if res:
        return f"Success: Updated ticket {ticket_id} setting {field} = '{value}'."
    return f"Error: Ticket {ticket_id} not found."


def search_knowledge_tool(query: str, allowed_scopes: List[str] = None) -> str:
    """Search company knowledge base and policies."""
    ans = answer_question(query, allowed_scopes=allowed_scopes)
    return f"Knowledge Result (verified={ans.verified}): {ans.answer}"


def bulk_approve_leave_tool(max_days: int = 5, date_range: str = None) -> str:
    """Upper Management tool to bulk-approve pending leave requests."""
    tickets = get_all_tickets()
    approved_count = 0
    approved_ids = []

    for t in tickets:
        dept = (t.get("department") or "").lower()
        cat = (t.get("category") or "").lower()
        status = (t.get("status") or "").lower()

        is_leave = (
            "leave" in cat or "pto" in cat or "vacation" in cat or "executive" in dept
        )
        if is_leave and status in {"open", "pending"}:
            update_ticket(t["id"], TicketUpdate(status="Approved"))
            approved_count += 1
            approved_ids.append(t["id"])

    return f"Bulk Action Complete: Approved {approved_count} leave tickets ({', '.join(approved_ids) if approved_ids else 'none'})."


def generate_document_tool(ticket_id: str, doc_format: str = "pdf") -> str:
    """Trigger PDF or DOCX document generation for a ticket."""
    return f"Document generated for {ticket_id} in {doc_format.upper()} format. Ready for download at /api/tickets/{ticket_id}/export?format={doc_format}"


# Tool Registry Definitions for LLM Prompts
TOOL_DEFINITIONS = [
    {
        "name": "sql_query_tool",
        "description": "Execute role-scoped SELECT or controlled UPDATE query on the tickets database.",
        "parameters": {
            "query": "string (SQL query)",
            "role": "string",
            "user_id": "string",
        },
    },
    {
        "name": "update_ticket_tool",
        "description": "Update a ticket field (department, priority, status, queue).",
        "parameters": {"ticket_id": "string", "field": "string", "value": "string"},
    },
    {
        "name": "search_knowledge_tool",
        "description": "Search company policy and knowledge base.",
        "parameters": {"query": "string"},
    },
    {
        "name": "bulk_approve_leave_tool",
        "description": "Bulk approve pending leave tickets under criteria.",
        "parameters": {"max_days": "integer"},
    },
    {
        "name": "generate_document_tool",
        "description": "Generate downloadable PDF or DOCX official ticket document.",
        "parameters": {"ticket_id": "string", "doc_format": "string"},
    },
]


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    role: str = "Admin",
    user_id: str = "user",
) -> str:
    """Dispatch execution to the matching tool handler."""
    logger.info(f"[ReAct Tool Call] name={tool_name} args={arguments}")

    if tool_name == "sql_query_tool":
        query = arguments.get("query", "")
        return sql_query_tool(query, role=role, user_id=user_id)

    elif tool_name == "update_ticket_tool":
        if not is_ticket_mutation_authorized(role):
            return (
                f"Error: Forbidden. Role '{role}' is not authorized to update tickets. "
                "Ticket mutations require Admin."
            )
        ticket_id = arguments.get("ticket_id", "")
        field = arguments.get("field", "")
        value = arguments.get("value", "")
        return update_ticket_tool(ticket_id, field, value, user_id=user_id)

    elif tool_name == "search_knowledge_tool":
        query = arguments.get("query", "")
        return search_knowledge_tool(query)

    elif tool_name == "bulk_approve_leave_tool":
        max_days = int(arguments.get("max_days", 5))
        return bulk_approve_leave_tool(max_days=max_days)

    elif tool_name == "generate_document_tool":
        ticket_id = arguments.get("ticket_id", "")
        doc_format = arguments.get("doc_format", "pdf")
        return generate_document_tool(ticket_id, doc_format=doc_format)

    return f"Error: Tool '{tool_name}' not found."
