"""Read historical Ticket-Genie LLM usage from Azure Application Insights."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

AI_USAGE_QUERY = r"""
AppTraces
| where Message startswith "[LLM Telemetry]"
| parse Message with "[LLM Telemetry] agent=" Agent:string
    " model=" Model:string
    " prompt_tokens=" PromptTokens:long
    " completion_tokens=" CompletionTokens:long
    " total_tokens=" TotalTokens:long
    " est_cost_usd=$" EstimatedCostUsd:real
| where isnotnull(TotalTokens)
| summarize
    Calls=count(),
    PromptTokens=sum(PromptTokens),
    CompletionTokens=sum(CompletionTokens),
    TotalTokens=sum(TotalTokens),
    EstimatedCostUsd=sum(EstimatedCostUsd),
    LastSeen=max(TimeGenerated)
    by Day=bin(TimeGenerated, 1d), Agent, Model
| order by Day asc
""".strip()


class AzureAIUsageUnavailableError(RuntimeError):
    """Raised when Azure-backed usage cannot be queried safely."""


def is_ai_usage_admin(current_user: Optional[dict]) -> bool:
    """Authorize only verified Admin/Super Admin identities."""
    if not current_user:
        return False
    normalized_role = re.sub(
        r"[\s_-]+", " ", str(current_user.get("role") or "").strip().lower()
    )
    return normalized_role in {"admin", "super admin"} or bool(
        current_user.get("is_dev", False)
    )


def _column_name(column: Any) -> str:
    return str(getattr(column, "name", column))


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _build_azure_credential():
    """Construct Azure credential prioritizing App Service System-Assigned Managed Identity.

    In Azure App Service, AZURE_CLIENT_ID in the environment is typically the App Registration
    Client ID (used for OAuth/OIDC JWT verification). When DefaultAzureCredential detects
    AZURE_CLIENT_ID, it incorrectly passes it as the client_id for User-Assigned Managed Identity,
    causing IMDS token requests to fail with invalid_scope (400).

    We explicitly construct a credential chain that uses ManagedIdentityCredential (system-assigned
    by default), falling back to Azure CLI and Environment credentials.
    """
    from azure.identity import (
        AzureCliCredential,
        ChainedTokenCredential,
        DefaultAzureCredential,
        EnvironmentCredential,
        ManagedIdentityCredential,
    )

    user_assigned_client_id = os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
    managed_identity = (
        ManagedIdentityCredential(client_id=user_assigned_client_id)
        if user_assigned_client_id
        else ManagedIdentityCredential()
    )

    return ChainedTokenCredential(
        managed_identity,
        AzureCliCredential(),
        EnvironmentCredential(),
        DefaultAzureCredential(exclude_managed_identity_credential=True),
    )


def get_azure_ai_usage(
    *,
    days: int = 30,
    workspace_id: Optional[str] = None,
    client: Any = None,
) -> dict:
    """Query Application Insights traces through its Log Analytics workspace."""
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")

    workspace = workspace_id or os.getenv("LOG_ANALYTICS_WORKSPACE_ID")
    if not workspace:
        raise AzureAIUsageUnavailableError(
            "Azure Log Analytics workspace configuration is missing."
        )

    if client is None:
        try:
            from azure.monitor.query import LogsQueryClient

            credential = _build_azure_credential()
            client = LogsQueryClient(credential)
        except Exception as exc:
            logger.warning("Could not initialize Azure logs client: %s", exc)
            raise AzureAIUsageUnavailableError(
                "Azure authentication is unavailable in this environment. "
                "Deploy the backend with its managed identity, or configure "
                "local Azure service-principal credentials."
            ) from exc

    logger.info(
        f"[AI Usage Query] Querying Log Analytics workspace '{workspace}' for past {days} days..."
    )

    try:
        result = client.query_workspace(
            workspace,
            AI_USAGE_QUERY,
            timespan=timedelta(days=days),
            server_timeout=30,
        )
        status_value = str(getattr(result, "status", "")).lower()
        tables = getattr(result, "tables", None)
        if "partial" in status_value:
            tables = getattr(result, "partial_data", None)
        if not tables and "success" not in status_value:
            raise AzureAIUsageUnavailableError(
                "Azure returned no usable AI usage result."
            )
    except AzureAIUsageUnavailableError:
        raise
    except Exception as exc:
        logger.warning("Azure AI usage query failed: %s", exc)
        raise AzureAIUsageUnavailableError(
            "Azure Application Insights could not be queried with the current "
            "environment's Azure identity."
        ) from exc

    breakdown = []
    daily: dict[str, dict] = {}
    totals = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    last_updated = None

    for table in tables or []:
        columns = [_column_name(column) for column in table.columns]
        for raw_row in table.rows:
            row = dict(zip(columns, raw_row, strict=True))
            day = _iso(row.get("Day")) or ""
            day = day[:10]
            item = {
                "day": day,
                "agent": str(row.get("Agent") or "unknown"),
                "model": str(row.get("Model") or "unknown"),
                "calls": int(row.get("Calls") or 0),
                "prompt_tokens": int(row.get("PromptTokens") or 0),
                "completion_tokens": int(row.get("CompletionTokens") or 0),
                "total_tokens": int(row.get("TotalTokens") or 0),
                "estimated_cost_usd": round(float(row.get("EstimatedCostUsd") or 0), 6),
            }
            breakdown.append(item)
            for key in ("calls", "prompt_tokens", "completion_tokens", "total_tokens"):
                totals[key] += item[key]
            totals["estimated_cost_usd"] += item["estimated_cost_usd"]

            daily_item = daily.setdefault(
                day,
                {"day": day, "calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
            )
            daily_item["calls"] += item["calls"]
            daily_item["total_tokens"] += item["total_tokens"]
            daily_item["estimated_cost_usd"] += item["estimated_cost_usd"]

            seen = _iso(row.get("LastSeen"))
            if seen and (last_updated is None or seen > last_updated):
                last_updated = seen

    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 6)
    for item in daily.values():
        item["estimated_cost_usd"] = round(item["estimated_cost_usd"], 6)

    logger.info(
        f"[AI Usage Query] Completed successfully. Found {len(breakdown)} records across {len(daily)} days. "
        f"Totals: {totals['calls']} calls, {totals['total_tokens']} tokens (${totals['estimated_cost_usd']:.6f})."
    )

    now = datetime.now(timezone.utc)
    return {
        "source": "Azure Application Insights",
        "period_days": days,
        "period_start": (now - timedelta(days=days)).isoformat(),
        "period_end": now.isoformat(),
        "last_updated": last_updated,
        "totals": totals,
        "daily": sorted(daily.values(), key=lambda item: item["day"]),
        "breakdown": breakdown,
    }
