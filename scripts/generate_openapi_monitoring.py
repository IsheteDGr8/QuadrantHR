#!/usr/bin/env python3
"""OpenAPI-Driven Azure Monitoring Generator.

Parses the OpenAPI specification from the FastAPI backend and generates:
1. Azure Application Insights KQL queries (`artifacts/openapi_kql_queries.kql`)
2. Azure Application Insights Workbook definition (`artifacts/openapi_workbook.json`)
3. Terraform Metric Alert Rules (`terraform/openapi_alerts.tf`)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from backend.main import app  # noqa: E402


def parse_openapi_spec(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract route details from an OpenAPI specification dictionary."""
    routes = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() not in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            ]:
                continue

            summary = (
                details.get("summary")
                or details.get("operationId")
                or f"{method.upper()} {path}"
            )
            tags = details.get("tags", ["default"])
            responses = list(details.get("responses", {}).keys())

            routes.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "operation_id": details.get(
                        "operationId", f"{method}_{path.strip('/')}"
                    ),
                    "summary": summary,
                    "tags": tags,
                    "responses": responses,
                    "request_name": f"{method.upper()} {path}",
                }
            )

    return routes


def generate_kql_queries(routes: List[Dict[str, Any]]) -> str:
    """Generate Kusto Query Language (KQL) diagnostic queries for App Insights."""
    kql_blocks = [
        "// " + "=" * 74,
        "// Azure Application Insights KQL Diagnostic Queries (From OpenAPI)",
        "// " + "=" * 74 + "\n",
    ]

    # 1. Overall Endpoint Latency & Failure Summary
    kql_blocks.append("// 1. Latency (P50, P95, P99) and Error Rates for Endpoints")
    kql_blocks.append("""requests
| where timestamp > ago(24h)
| summarize
    TotalRequests = count(),
    SuccessCount = countif(success == true),
    FailedCount = countif(success == false),
    P50_Ms = percentiles(duration, 50)[0],
    P95_Ms = percentiles(duration, 95)[0],
    P99_Ms = percentiles(duration, 99)[0]
  by name, resultCode
| extend FailureRate = round(100.0 * FailedCount / TotalRequests, 2)
| order by TotalRequests desc
""")

    # 2. Per Endpoint Detailed Metrics
    kql_blocks.append("// 2. Per-Route Performance Breakdown")
    for route in routes:
        name = route["request_name"]
        kql_blocks.append(f"// Route: {name} ({', '.join(route['tags'])})")
        kql_blocks.append(f"""requests
| where timestamp > ago(1h) and name == "{name}"
| summarize
    RequestVolume = count(),
    AvgDurationMs = avg(duration),
    P95DurationMs = percentiles(duration, 95)[0],
    ServerError5xx = countif(toint(resultCode) >= 500),
    ClientError4xx = countif(toint(resultCode) >= 400 and toint(resultCode) < 500)
  by bin(timestamp, 5m)
| render timechart
""")

    # 3. High Latency Traces
    kql_blocks.append("// 3. High Latency (>1000ms) Request Trace Correlation")
    kql_blocks.append("""requests
| where timestamp > ago(24h) and duration > 1000
| project timestamp, name, resultCode, duration, url, customDimensions
| order by duration desc
""")

    # 4. LLM Token Usage & Cost Analytics
    kql_blocks.append(
        "// 4. LLM Token Consumption & Estimated Cost (OpenTelemetry Metrics)"
    )
    kql_blocks.append("""customMetrics
| where timestamp > ago(24h) and name startswith "llm_"
| summarize
    PromptTokens = sumif(value, name == "llm_prompt_tokens"),
    CompletionTokens = sumif(value, name == "llm_completion_tokens"),
    TotalTokens = sumif(value, name == "llm_total_tokens"),
    EstimatedCostUSD = sumif(value, name == "llm_estimated_cost_usd")
  by bin(timestamp, 1h), tostring(customDimensions.agent)
| order by timestamp desc
""")

    return "\n\n".join(kql_blocks)


def generate_workbook_json(routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate an Azure Application Insights Workbook definition JSON."""
    workbook = {
        "version": "Notebook/1.0",
        "items": [
            {
                "type": 1,
                "content": {
                    "json": (
                        "## 🚀 TicketGenie FastAPI & AI Agent Dashboard\n"
                        "*Auto-generated from OpenAPI 3.0 Specification & OpenTelemetry LLM Metrics*"
                    )
                },
            },
            {
                "type": 9,
                "content": {
                    "version": "KqlParameterItem/1.0",
                    "parameters": [
                        {
                            "id": "TimeRange",
                            "type": 4,
                            "isRequired": True,
                            "value": {"durationMs": 86400000},
                            "typeSettings": {
                                "selectableValues": [
                                    {"durationMs": 3600000, "name": "Last 1 hour"},
                                    {"durationMs": 14400000, "name": "Last 4 hours"},
                                    {"durationMs": 86400000, "name": "Last 24 hours"},
                                    {"durationMs": 604800000, "name": "Last 7 days"},
                                    {"durationMs": 2592000000, "name": "Last 30 days"},
                                ]
                            },
                            "name": "TimeRange",
                            "label": "Time Range",
                        }
                    ],
                    "style": "pills",
                    "queryType": 0,
                    "resourceType": "microsoft.insights/components",
                },
            },
            {
                "type": 3,
                "content": {
                    "version": "KqlItem/1.0",
                    "query": """requests
| where timestamp >= {TimeRange:start} and timestamp <= {TimeRange:end}
| summarize
    Total_Requests = count(),
    Failed_Requests = countif(success == false),
    Avg_Latency_Ms = round(avg(duration), 2),
    P95_Latency_Ms = round(percentiles(duration, 95)[0], 2)
  by name
| extend Error_Rate_Pct = round(100.0 * Failed_Requests / Total_Requests, 2)
| order by Total_Requests desc""",
                    "size": 0,
                    "title": "API Endpoint Performance & Error Overview",
                    "queryType": 0,
                    "resourceType": "microsoft.insights/components",
                    "timeContext": {"durationMs": 86400000},
                    "timeContextFromParameter": "TimeRange",
                },
            },
            {
                "type": 3,
                "content": {
                    "version": "KqlItem/1.0",
                    "query": """customMetrics
| where timestamp >= {TimeRange:start} and timestamp <= {TimeRange:end} and name startswith "llm_"
| summarize
    Prompt_Tokens = sumif(value, name == "llm_prompt_tokens"),
    Completion_Tokens = sumif(value, name == "llm_completion_tokens"),
    Total_Tokens = sumif(value, name == "llm_total_tokens"),
    Est_Cost_USD = round(sumif(value, name == "llm_estimated_cost_usd"), 4)
  by tostring(customDimensions.agent)
| order by Total_Tokens desc""",
                    "size": 0,
                    "title": "LLM Token Consumption & Cost by Subagent",
                    "queryType": 0,
                    "resourceType": "microsoft.insights/components",
                    "timeContext": {"durationMs": 86400000},
                    "timeContextFromParameter": "TimeRange",
                },
            },
            {
                "type": 3,
                "content": {
                    "version": "KqlItem/1.0",
                    "query": """requests
| where timestamp >= {TimeRange:start} and timestamp <= {TimeRange:end}
| make-series Requests=count() on timestamp
    from {TimeRange:start} to {TimeRange:end} step 5m by name
| render timechart""",
                    "size": 0,
                    "title": "Request Throughput per OpenAPI Route (RPS / 5m)",
                    "queryType": 0,
                    "resourceType": "microsoft.insights/components",
                    "timeContext": {"durationMs": 86400000},
                    "timeContextFromParameter": "TimeRange",
                },
            },
        ],
        "style": "categoryGrid",
        "tags": ["FastAPI", "OpenAPI", "OpenTelemetry", "TicketGenie"],
    }
    return workbook


def generate_terraform_alerts(routes: List[Dict[str, Any]]) -> str:
    """Generate Terraform HCL code for Azure Monitor Metric Alerts."""
    hcl = [
        "# " + "=" * 74,
        "# Auto-Generated Azure Monitor Metric Alerts for OpenAPI Endpoints",
        "# Generated by scripts/generate_openapi_monitoring.py",
        "# " + "=" * 74 + "\n",
        "# 1. Global High Server Error Rate Alert (5xx Errors)",
        """resource "azurerm_monitor_metric_alert" "api_server_errors" {
  name                = "alert-ticketgenie-api-5xx-errors"
  resource_group_name = data.azurerm_resource_group.rg.name
  scopes              = [azurerm_application_insights.appi.id]
  description         = "Triggers on high HTTP 5xx server errors"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 5
  }
}
""",
        "# 2. Global High Latency Alert (P95 > 1000ms)",
        """resource "azurerm_monitor_metric_alert" "api_high_latency" {
  name                = "alert-ticketgenie-api-high-latency"
  resource_group_name = data.azurerm_resource_group.rg.name
  scopes              = [azurerm_application_insights.appi.id]
  description         = "Triggers when average request latency exceeds 1000ms"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/duration"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 1000
  }
}
""",
        "# 3. HTTP 500 Internal Server Errors Alert",
        """resource "azurerm_monitor_metric_alert" "api_500_errors" {
  name                = "alert-ticketgenie-api-500-errors"
  resource_group_name = data.azurerm_resource_group.rg.name
  scopes              = [azurerm_application_insights.appi.id]
  description         = "Triggers when HTTP 500 Internal Server Errors occur"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 3

    dimension {
      name     = "request/resultCode"
      operator = "Include"
      values   = ["500"]
    }
  }
}
""",
        "# 4. HTTP 503 Service Unavailable Errors Alert",
        """resource "azurerm_monitor_metric_alert" "api_503_errors" {
  name                = "alert-ticketgenie-api-503-errors"
  resource_group_name = data.azurerm_resource_group.rg.name
  scopes              = [azurerm_application_insights.appi.id]
  description         = "Triggers when HTTP 503 Service Unavailable errors occur"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 3

    dimension {
      name     = "request/resultCode"
      operator = "Include"
      values   = ["503"]
    }
  }
}
""",
    ]

    return "\n".join(hcl)


def main():
    artifacts_dir = root_dir / "artifacts"
    terraform_dir = root_dir / "terraform"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    terraform_dir.mkdir(parents=True, exist_ok=True)

    spec = app.openapi()
    routes = parse_openapi_spec(spec)
    print(f"🔍 Discovered {len(routes)} routes in FastAPI OpenAPI spec.")

    # 1. Generate KQL queries
    kql_content = generate_kql_queries(routes)
    kql_file = artifacts_dir / "openapi_kql_queries.kql"
    kql_file.write_text(kql_content, encoding="utf-8")
    print(f"✅ Generated KQL queries artifact: {kql_file}")

    # 2. Generate Azure Workbook JSON
    workbook_content = generate_workbook_json(routes)
    workbook_file = artifacts_dir / "openapi_workbook.json"
    workbook_file.write_text(json.dumps(workbook_content, indent=2), encoding="utf-8")
    print(f"✅ Generated Azure Workbook artifact: {workbook_file}")

    # 3. Generate Terraform Metric Alerts
    tf_alerts_content = generate_terraform_alerts(routes)
    tf_alerts_file = terraform_dir / "openapi_alerts.tf"
    tf_alerts_file.write_text(tf_alerts_content, encoding="utf-8")
    print(f"✅ Generated Terraform metric alerts HCL: {tf_alerts_file}")


if __name__ == "__main__":
    main()
