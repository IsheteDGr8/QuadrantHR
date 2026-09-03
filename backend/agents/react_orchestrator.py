"""ReAct (Reason + Act + Observe) Agent Loop Engine for TicketGenie.

Executes an iterative reasoning loop:
1. Thought: LLM reasons about task / user prompt.
2. Action: LLM calls a registered tool (SQL, update, RAG search, bulk approve, doc gen).
3. Observation: System executes tool and returns result to LLM.
4. Loop repeats until max_iterations or Final Response is produced.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents.tool_registry import TOOL_DEFINITIONS, execute_tool
from telemetry import record_llm_metrics

logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = 5


class ReActStep(BaseModel):
    iteration: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None


class ReActResult(BaseModel):
    final_response: str
    steps: List[ReActStep]
    iterations_used: int


REACT_SYSTEM_PROMPT = """
You are the TicketGenie ReAct (Reason + Act) Autonomous Agent Engine.
You process helpdesk tickets, admin commands, SQL queries, and governance requests.

AVAILABLE TOOLS:
{tools_spec}

REACT FORMAT INSTRUCTIONS:
To complete a task, you MUST use the following step-by-step format:

Thought: Reason step-by-step about what to do next.
Action: the tool name to use (must be one of [{tool_names}])
Action Input: a valid JSON dictionary of parameters for the tool

When you have gathered all information or completed the requested actions, respond with:

Thought: I now have the final answer / task completed.
Final Response: Your clear, concise response to the user or system.

FEW-SHOT EXAMPLES:

Example 1 (Ticket Relocation Command):
User: Move ticket HD-102 to IT Department
Thought: The user wants to reassign ticket HD-102 to IT Department. I should call update_ticket_tool setting department = 'IT Team'.
Action: update_ticket_tool
Action Input: {{"ticket_id": "HD-102", "field": "department", "value": "IT Team"}}
Observation: Success: Updated ticket HD-102 setting department = 'IT Team'.
Thought: The ticket department has been updated successfully.
Final Response: Ticket HD-102 has been successfully reassigned to the IT Team.

Example 2 (Text-to-SQL Query):
User: How many open IT tickets are in the queue?
Thought: I need to query the database for count of open IT tickets. I will execute a SELECT query using sql_query_tool.
Action: sql_query_tool
Action Input: {{"query": "SELECT COUNT(*) as open_count FROM tickets WHERE department='IT Team' AND status='Open'"}}
Observation: {{"success": true, "rows": [{{"open_count": 4}}]}}
Thought: I have retrieved the count of open IT tickets.
Final Response: There are currently 4 open IT tickets in the queue.

Example 3 (Executive Bulk Approval):
User: Approve all pending leave requests
Thought: The user is asking to approve all pending leave tickets. I should run bulk_approve_leave_tool.
Action: bulk_approve_leave_tool
Action Input: {{"max_days": 5}}
Observation: Bulk Action Complete: Approved 3 leave tickets (HD-1002, HD-1004, HD-1009).
Thought: All pending leave tickets have been approved.
Final Response: Successfully approved 3 pending leave requests (HD-1002, HD-1004, HD-1009).
"""


def run_react_agent_loop(
    user_prompt: str,
    role: str = "Admin",
    user_id: str = "user",
    context: Optional[Dict[str, Any]] = None,
) -> ReActResult:
    """Execute the ReAct loop (Thought -> Action -> Observation -> Final Response)."""
    tool_names = ", ".join([t["name"] for t in TOOL_DEFINITIONS])
    tools_spec = json.dumps(TOOL_DEFINITIONS, indent=2)

    system_prompt = REACT_SYSTEM_PROMPT.format(
        tools_spec=tools_spec,
        tool_names=tool_names,
    )

    steps: List[ReActStep] = []
    conversation_history = f"User Request: {user_prompt}\nUser Role: {role}\n"

    for iteration in range(1, MAX_REACT_ITERATIONS + 1):
        # Call Azure OpenAI or Mock AI
        response_text = _call_llm_react_step(system_prompt, conversation_history)

        # Parse Thought, Action, Action Input, or Final Response
        thought, action, action_input, final_response = _parse_react_output(
            response_text
        )

        if final_response:
            steps.append(
                ReActStep(
                    iteration=iteration,
                    thought=thought or "Task complete.",
                    action=None,
                    action_input=None,
                    observation=None,
                )
            )
            return ReActResult(
                final_response=final_response,
                steps=steps,
                iterations_used=iteration,
            )

        if action and action in [t["name"] for t in TOOL_DEFINITIONS]:
            action_input = action_input or {}
            # Execute tool
            observation = execute_tool(action, action_input, role=role, user_id=user_id)

            steps.append(
                ReActStep(
                    iteration=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation,
                )
            )

            # Append to prompt history for next loop
            conversation_history += f"\nThought: {thought}\nAction: {action}\nAction Input: {json.dumps(action_input)}\nObservation: {observation}\n"
        else:
            # Fallback if no valid action was formatted
            final_resp = thought or response_text
            steps.append(
                ReActStep(
                    iteration=iteration,
                    thought=thought,
                    action=None,
                    action_input=None,
                    observation=None,
                )
            )
            return ReActResult(
                final_response=final_resp,
                steps=steps,
                iterations_used=iteration,
            )

    return ReActResult(
        final_response="ReAct loop reached maximum iterations limit.",
        steps=steps,
        iterations_used=MAX_REACT_ITERATIONS,
    )


def _parse_react_output(
    text: str,
) -> tuple[str, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Parse Thought, Action, Action Input, and Final Response from LLM output."""
    thought_match = re.search(
        r"Thought:\s*(.*?)(?=(Action:|Final Response:|$))", text, re.DOTALL
    )
    thought = thought_match.group(1).strip() if thought_match else ""

    final_match = re.search(r"Final Response:\s*(.*)", text, re.DOTALL)
    if final_match:
        return thought, None, None, final_match.group(1).strip()

    action_match = re.search(r"Action:\s*(\w+)", text)
    action = action_match.group(1).strip() if action_match else None

    action_input = None
    input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
    if input_match:
        try:
            action_input = json.loads(input_match.group(1))
        except Exception:
            pass

    return thought, action, action_input, None


def _call_llm_react_step(system_prompt: str, user_history: str) -> str:
    """Call Azure OpenAI endpoint or fallback mock for a ReAct iteration step."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    use_mock = os.getenv("USE_MOCK_AI", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if use_mock or not (endpoint and api_key and deployment):
        # Local deterministic ReAct parser for mock testing
        return _mock_react_response(user_history)

    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
        response = client.chat.completions.create(
            model=deployment,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_history},
            ],
        )

        if hasattr(response, "usage") and response.usage:
            try:
                record_llm_metrics(
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    model=deployment,
                    agent_name="react_orchestrator",
                )
            except Exception:
                pass

        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.warning(f"Azure OpenAI ReAct step failed: {exc}")
        return _mock_react_response(user_history)


def _mock_react_response(user_history: str) -> str:
    """Deterministic ReAct step response for mock mode testing."""
    lowered = user_history.lower()

    if "observation:" in lowered:
        # After tool execution, output final response
        return "Thought: I have processed the observation.\nFinal Response: Task completed successfully."

    if "move" in lowered or "reassign" in lowered or "department" in lowered:
        # Extract ticket ID if present
        match = re.search(r"\b(hd-\d+)\b", lowered)
        tid = match.group(1).upper() if match else "HD-1001"
        return f'Thought: I will update the department for ticket {tid}.\nAction: update_ticket_tool\nAction Input: {{"ticket_id": "{tid}", "field": "department", "value": "IT Team"}}'

    if "approve" in lowered or "leave" in lowered:
        return 'Thought: I will bulk approve pending leave requests.\nAction: bulk_approve_leave_tool\nAction Input: {"max_days": 5}'

    if "select" in lowered or "how many" in lowered or "count" in lowered:
        return 'Thought: I will query the database.\nAction: sql_query_tool\nAction Input: {"query": "SELECT COUNT(*) as total_tickets FROM tickets"}'

    return "Thought: Processing standard prompt.\nFinal Response: I'm Genie, your workplace AI assistant. How can I help you today?"
