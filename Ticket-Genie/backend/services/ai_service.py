"""Azure OpenAI client wrapper for AI ticket classification.

Responsible for:
- deciding whether to run in mock mode or call Azure OpenAI for real
- building the system prompt
- making the actual model request
- translating Azure/OpenAI SDK errors into a single AIServiceError

This module does NOT validate the classification result against the
department/category/priority taxonomy — that happens in
agents/orchestrator.py. This module only guarantees it returns either a
dict or raises AIServiceError.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests
from pydantic import BaseModel, Field

from agents.category_agent import ALLOWED_CATEGORIES
from agents.priority_agent import (
    ALLOWED_PRIORITIES,
    PRIORITY_DESCRIPTIONS,
    classify_priority,
)

logger = logging.getLogger(__name__)

try:  # local .env support for developer machines; safe no-op if unavailable
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_AZURE_API_VERSION = "2024-08-01-preview"
DEFAULT_AI_TIMEOUT = 8.0


class AIServiceError(Exception):
    """Raised whenever a classification request cannot be completed.

    The message is safe to log and safe to surface to callers — it never
    contains API keys, stack traces, or other sensitive internal details.
    """


def _strictify_json_schema(node: Any) -> None:
    """
    Mutate a Pydantic-generated JSON schema in place into the Azure/OpenAI
    "strict" structured-output subset: every object schema gets
    additionalProperties=false and lists every one of its properties in
    `required` (an Optional field expresses its optionality through its
    own type - e.g. Pydantic already emits `anyOf: [..., {"type": "null"}]`
    for `Optional[X] = None` - not by being omitted from `required`, which
    strict mode does not allow). `default` is stripped since it is not
    part of the strict-mode keyword subset.
    """

    if isinstance(node, dict):
        node.pop("default", None)
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for value in node.values():
            _strictify_json_schema(value)
    elif isinstance(node, list):
        for item in node:
            _strictify_json_schema(item)


def _pydantic_to_strict_schema(response_model: Any) -> dict[str, Any]:
    """Build an Azure/OpenAI strict json_schema payload from a Pydantic model with inlined $defs."""

    schema = response_model.model_json_schema()
    defs = schema.pop("$defs", {})
    if defs:

        def _resolve(node: Any) -> Any:
            if isinstance(node, dict):
                if "$ref" in node:
                    ref_name = node["$ref"].split("/")[-1]
                    if ref_name in defs:
                        resolved = dict(defs[ref_name])
                        for k, v in node.items():
                            if k != "$ref":
                                resolved[k] = v
                        return _resolve(resolved)
                return {k: _resolve(v) for k, v in node.items()}
            elif isinstance(node, list):
                return [_resolve(item) for item in node]
            return node

        schema = _resolve(schema)

    _strictify_json_schema(schema)
    return schema


class AIServiceWrapper:
    """Structured .generate() interface for Pydantic response models
    (used by the chatbot, knowledge/RAG, summary, and suggested-response
    agents - see agents/chatbot_agent.py, agents/knowledge_agent.py).

    Internally reuses generate_structured() below - the exact same
    shared, Key-Vault-backed GROUP1* Azure OpenAI v1 Responses call that
    agents/orchestrator.py's category/priority/routing classification
    already goes through - converting the Pydantic response_model into a
    strict JSON schema instead of opening a second AzureOpenAI SDK client
    against a separate AZURE_OPENAI_* configuration. There is exactly one
    Azure OpenAI call path in this module now.

    Contract: always either returns a valid response_model instance or
    raises AIServiceError - never None. Callers should catch
    AIServiceError (see services/chatbot_service.handle_message).
    """

    def generate(
        self,
        *,
        system_prompt: str,
        user_content: str,
        response_model: Any,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Any:
        model_name = getattr(response_model, "__name__", "response")
        # Keep semantic-router responses compact without changing the caller's
        # stable interface (important for injected test and local AI services).
        if max_tokens is None and model_name == "ChatbotDecision":
            max_tokens = 400

        if use_mock_ai():
            try:
                res = response_model()
                try:
                    from telemetry import record_llm_metrics

                    prompt_tok = max(
                        15, len((system_prompt + " " + user_content).split()) * 2
                    )
                    record_llm_metrics(
                        prompt_tokens=prompt_tok,
                        completion_tokens=25,
                        model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"),
                        agent_name=f"structured_{model_name}",
                    )
                except Exception:
                    pass
                return res
            except Exception as exc:
                raise AIServiceError(
                    f"Mock AI mode cannot construct a default {model_name} - "
                    "it has required fields with no safe default."
                ) from exc

        endpoint = os.getenv("GROUP1OPENAIENDPOINT") or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        api_key = os.getenv("GROUP1OPENAIAPIKEY") or os.getenv("AZURE_OPENAI_API_KEY")

        if endpoint and api_key:
            schema = _pydantic_to_strict_schema(response_model)
            prompt = f"{system_prompt}\n\n{user_content}"
            data = generate_structured(
                prompt=prompt,
                schema=schema,
                name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            try:
                return response_model.model_validate(data)
            except Exception as exc:
                raise AIServiceError(
                    f"{model_name} response did not match the expected schema."
                ) from exc

        raise AIServiceError("Azure OpenAI configuration is missing.")


ai_service = AIServiceWrapper()


def use_mock_ai() -> bool:
    """Return True when the module should use deterministic local rules
    instead of calling Azure OpenAI."""
    return os.getenv("USE_MOCK_AI", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _record_structured_usage(usage: Any, *, model: str, agent_name: str) -> None:
    """Record token usage from either Responses or Chat Completions payloads, including prompt cache discounts."""
    if not usage:
        return

    def usage_value(*names: str) -> int:
        for field in names:
            value = (
                usage.get(field)
                if isinstance(usage, dict)
                else getattr(usage, field, None)
            )
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return 0

    prompt_tokens = usage_value("input_tokens", "prompt_tokens")
    completion_tokens = usage_value("output_tokens", "completion_tokens")

    # Extract native Azure OpenAI prefix prompt caching tokens
    prompt_tokens_details = (
        usage.get("prompt_tokens_details")
        if isinstance(usage, dict)
        else getattr(usage, "prompt_tokens_details", None)
    )
    cached_tokens = 0
    if prompt_tokens_details:
        cached_tokens = (
            prompt_tokens_details.get("cached_tokens", 0)
            if isinstance(prompt_tokens_details, dict)
            else getattr(prompt_tokens_details, "cached_tokens", 0)
        ) or 0
    elif isinstance(usage, dict) and "cached_tokens" in usage:
        try:
            cached_tokens = int(usage.get("cached_tokens", 0) or 0)
        except (ValueError, TypeError):
            cached_tokens = 0

    if not prompt_tokens and not completion_tokens and not cached_tokens:
        return

    try:
        from telemetry import record_llm_metrics

        record_llm_metrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
            agent_name=agent_name,
            cached_tokens=cached_tokens,
        )
    except Exception as exc:
        # Observability must never make an otherwise valid AI response fail.
        logger.debug("Could not record structured LLM token metrics: %s", exc)


def generate_structured(
    *,
    prompt: str,
    schema: dict[str, Any],
    name: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Call the configured Azure v1 Responses endpoint or Azure OpenAI endpoint with strict JSON output."""
    endpoint = os.getenv("GROUP1OPENAIENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("GROUP1OPENAIAPIKEY") or os.getenv("AZURE_OPENAI_API_KEY")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")

    if not endpoint or not api_key:
        raise AIServiceError("Azure OpenAI configuration is missing.")

    # Check Prompt & Response Cache
    from services.prompt_cache_service import estimate_prompt_tokens, prompt_cache

    agent_label = f"structured_{name}"
    cache_key = prompt_cache.make_key(agent_label, prompt, name)
    cached_result = prompt_cache.get(cache_key, agent_name=agent_label)
    if cached_result is not None:
        est_tokens = estimate_prompt_tokens(prompt)
        _record_structured_usage(
            {
                "prompt_tokens": est_tokens,
                "completion_tokens": 0,
                "cached_tokens": est_tokens,
            },
            model=model,
            agent_name=agent_label,
        )
        return cached_result

    body: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "temperature": temperature,
        "text": {
            "format": {
                "type": "json_schema",
                "name": name,
                "schema": schema,
                "strict": True,
            }
        },
    }
    if max_tokens is not None:
        body["max_output_tokens"] = max_tokens

    timeout_raw = os.getenv("AZURE_OPENAI_TIMEOUT", str(DEFAULT_AI_TIMEOUT))
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = DEFAULT_AI_TIMEOUT

    try:
        response = requests.post(
            endpoint,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        _record_structured_usage(
            payload.get("usage"), model=model, agent_name=agent_label
        )
        output_text = payload.get("output_text")
        if not output_text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text")
                        break
        if not output_text:
            raise AIServiceError("Azure OpenAI returned no structured output.")
        result = json.loads(output_text)
        prompt_cache.set(
            cache_key,
            result,
            est_tokens=estimate_prompt_tokens(prompt),
            ttl_seconds=3600,
            agent_name=agent_label,
        )
        return result
    except AIServiceError:
        raise
    except Exception as exc:
        try:
            from openai import AzureOpenAI

            api_version = os.getenv(
                "AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION
            )
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
                timeout=timeout,
                max_retries=0,
            )
            resp = client.chat.completions.create(
                model=model,
                temperature=0.0,
                max_tokens=max_tokens or 150,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": name,
                        "schema": schema,
                        "strict": True,
                    },
                },
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            _record_structured_usage(
                getattr(resp, "usage", None),
                model=model,
                agent_name=agent_label,
            )
            content = resp.choices[0].message.content
            if content:
                result = json.loads(content)
                prompt_cache.set(
                    cache_key,
                    result,
                    est_tokens=estimate_prompt_tokens(prompt),
                    ttl_seconds=3600,
                    agent_name=agent_label,
                )
                return result
        except Exception:
            pass
        logger.warning("Structured AI agent call failed: %s", exc)
        raise AIServiceError("Azure OpenAI agent call failed.") from exc


def get_confidence_threshold() -> float:
    """Return the minimum confidence below which a result must be flagged
    for human review."""
    raw = os.getenv("AI_CONFIDENCE_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD))
    try:
        threshold = float(raw)
    except ValueError:
        logger.warning("Invalid AI_CONFIDENCE_THRESHOLD=%r, using default.", raw)
        return DEFAULT_CONFIDENCE_THRESHOLD
    return min(max(threshold, 0.0), 1.0)


def get_ai_classification(
    title: str,
    description: str,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Classify a ticket and return a raw (not-yet-validated) result dict.

    Raises AIServiceError if the classification cannot be produced.
    """
    if use_mock_ai():
        return _mock_classify(title, description, context)
    return _call_azure_openai(title, description, context)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def build_system_prompt() -> str:
    departments_block = "\n".join(
        f"- {department}: {', '.join(categories)}"
        for department, categories in ALLOWED_CATEGORIES.items()
    )
    priorities_block = "\n".join(
        f"- {priority}: {PRIORITY_DESCRIPTIONS[priority]}"
        for priority in ALLOWED_PRIORITIES
    )

    return (
        "You are a workplace ticket classifier for an internal company "
        "helpdesk. Given a ticket title and description, classify it.\n\n"
        "Allowed departments and their allowed categories. You must choose "
        "exactly one department and exactly one category that belongs to "
        "that department. Never invent a department or category that is "
        "not in this list:\n"
        f"{departments_block}\n\n"
        "Priority levels:\n"
        f"{priorities_block}\n\n"
        "Rules:\n"
        "- Base priority on business impact, not on emotional language. "
        'The word "urgent" appearing in the ticket text does NOT by '
        'itself justify a "Critical" priority.\n'
        "- If the ticket is vague, could reasonably belong to more than "
        "one department, or is missing information needed to classify it "
        "confidently, lower your confidence and set needs_human_review "
        "to true.\n"
        "- If the ticket describes something unusually sensitive or "
        "high-risk (legal, safety, security, executive-level conflict), "
        "set needs_human_review to true even if you are otherwise "
        "confident.\n"
        "- Reports of workplace harassment, discrimination, retaliation, "
        "sexual misconduct, or workplace bullying must route to HR Team / "
        "Employee Relationships and must be at least High priority.\n"
        "- Reserve Critical for an immediate threat of serious physical harm, "
        "credible workplace violence, a major security/data breach, or a "
        "company-wide outage.\n"
        '- "reason" must be one short, concise, factual sentence.\n'
        "- Respond with a single JSON object and no other text, matching "
        "exactly this shape and no additional keys:\n"
        "{\n"
        '  "department": string,\n'
        '  "category": string,\n'
        '  "priority": "Low" | "Medium" | "High" | "Critical",\n'
        '  "confidence": number between 0 and 1,\n'
        '  "reason": string,\n'
        '  "needs_human_review": boolean\n'
        "}"
    )


# ---------------------------------------------------------------------------
# Real Azure OpenAI call
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise AIServiceError(f"Missing required Azure OpenAI configuration: {name}.")
    return value


def _call_azure_openai(
    title: str,
    description: str,
    context: Optional[dict[str, Any]],
) -> dict[str, Any]:
    deployment = _require_env("AZURE_OPENAI_DEPLOYMENT")

    try:
        import openai  # noqa: F401
    except ImportError as exc:
        raise AIServiceError(
            "The 'openai' package is required for real AI mode but is not installed."
        ) from exc

    user_content = f"Title: {title}\nDescription: {description}"
    if context:
        user_content += f"\nAdditional context: {json.dumps(context, default=str)}"

    from services.prompt_cache_service import estimate_prompt_tokens, prompt_cache

    cache_key = prompt_cache.make_key("ticket_classifier", f"{title}|{description}")
    cached_result = prompt_cache.get(cache_key, agent_name="ticket_classifier")
    if cached_result is not None:
        est_tokens = estimate_prompt_tokens(f"{title} {description}")
        _record_structured_usage(
            {
                "prompt_tokens": est_tokens,
                "completion_tokens": 0,
                "cached_tokens": est_tokens,
            },
            model=deployment,
            agent_name="ticket_classifier",
        )
        return cached_result

    class TicketClassificationDecision(BaseModel):
        category: str = Field(default="IT Support", description="Ticket category")
        priority: str = Field(
            default="Medium",
            description="Ticket priority (Low, Medium, High, Critical)",
        )
        confidence: float = Field(
            default=0.85, description="Confidence score from 0.0 to 1.0"
        )
        reasoning: str = Field(default="", description="Reasoning for classification")

    try:
        decision = ai_service.generate(
            system_prompt=build_system_prompt(),
            user_content=user_content,
            response_model=TicketClassificationDecision,
            max_tokens=250,
        )
        if decision:
            val = (
                decision.model_dump()
                if hasattr(decision, "model_dump")
                else dict(decision)
            )
            prompt_cache.set(
                cache_key,
                val,
                est_tokens=estimate_prompt_tokens(f"{title} {description}"),
                ttl_seconds=3600,
                agent_name="ticket_classifier",
            )
            return val
    except Exception as struct_exc:
        logger.warning(
            "Primary structured classification error, falling back to heuristic: %s",
            struct_exc,
        )
        fallback_res = _mock_classify(title, description, context)
        prompt_cache.set(
            cache_key,
            fallback_res,
            est_tokens=estimate_prompt_tokens(f"{title} {description}"),
            ttl_seconds=3600,
            agent_name="ticket_classifier",
        )
        return fallback_res


# ---------------------------------------------------------------------------
# Mock mode — deterministic local rules, no network calls
# ---------------------------------------------------------------------------

# category -> keywords that, if present in the ticket text, select it.
# Order matters: first department whose category matches wins.
_MOCK_KEYWORD_RULES: dict[str, dict[str, list[str]]] = {
    "IT Team": {
        "Identity and Access Management": [
            "password",
            "login",
            "log in",
            "account",
            "locked out",
            "access",
            "vpn",
            "credentials",
        ],
        "Laptop Requests": ["laptop"],
        "Software Licensing": ["software", "license", "licensing"],
    },
    "Accounting Team": {
        "Reimbursement Requests": ["reimbursement", "reimburse", "expense"],
        "Company Card Management": ["company card", "corporate card"],
        "Business Development Management": ["business development"],
    },
    "Workplace Operations Team": {
        "Badge Registration": ["badge"],
        "Maintenance": ["maintenance", "repair"],
        "Office Equipment Issues": [
            "office equipment",
            "mouse",
            "keyboard",
            "monitor",
            "printer",
            "desk",
            "chair",
        ],
    },
    "HR Team": {
        "Benefits Inquiries": ["benefits", "benefit"],
        "Onboarding and Offboarding": [
            "onboarding",
            "offboarding",
            "onboard",
            "offboard",
            "new hire",
        ],
        "Employee Relationships": [
            "employee relationship",
            "harassment",
            "harassed",
            "harassing",
            "discrimination",
            "discriminated",
            "discriminatory",
            "retaliation",
            "retaliated",
            "workplace bullying",
            "hostile work environment",
            "sexual misconduct",
            "coworker conflict",
            "workplace conflict",
        ],
    },
    "Upper Management": {
        "High-Impact Company Conflict": [
            "serious company-wide conflict",
            "major organizational conflict",
            "company-wide conflict",
        ],
        "Executive Review": ["executive issue", "executive review"],
        "Company-Wide Issue": ["company-wide issue", "company wide issue"],
    },
}


def _mock_classify(
    title: str,
    description: str,
    context: Optional[dict[str, Any]],
) -> dict[str, Any]:
    text = f"{title} {description}".lower()
    if context:
        text += " " + " ".join(str(value) for value in context.values()).lower()

    matches: list[tuple[str, str]] = []
    for department, categories in _MOCK_KEYWORD_RULES.items():
        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                matches.append((department, category))

    priority = classify_priority(text)

    if not matches:
        return {
            "department": "Upper Management",
            "category": "Other Management Issue",
            "priority": priority,
            "confidence": 0.3,
            "reason": "[MOCK] No keyword rule matched this ticket; routed for manual triage.",
            "needs_human_review": True,
        }

    department, category = matches[0]
    ambiguous = len({matched_department for matched_department, _ in matches}) > 1

    try:
        from telemetry import record_llm_metrics

        prompt_tok = max(20, len(text.split()) * 3 + 60)
        record_llm_metrics(
            prompt_tokens=prompt_tok,
            completion_tokens=35,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"),
            agent_name="ticket_classifier",
        )
    except Exception:
        pass

    return {
        "department": department,
        "category": category,
        "priority": priority,
        "confidence": 0.55 if ambiguous else 0.95,
        "reason": (
            f"[MOCK] Deterministic keyword rule matched '{category}' under '{department}'."
        ),
        "needs_human_review": ambiguous,
    }
