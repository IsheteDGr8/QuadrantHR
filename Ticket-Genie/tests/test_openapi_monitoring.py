"""Unit tests for Azure Monitor setup and OpenAPI-driven monitoring generator."""

import json
from pathlib import Path

from fastapi import FastAPI

from backend.main import app
from backend.telemetry import setup_telemetry
from scripts.export_openapi import export_openapi_spec
from scripts.generate_openapi_monitoring import (
    generate_kql_queries,
    generate_terraform_alerts,
    generate_workbook_json,
    parse_openapi_spec,
)


def test_telemetry_setup_disabled_without_connection_string():
    """Verify setup_telemetry returns False when connection string is missing."""
    test_app = FastAPI()
    result = setup_telemetry(test_app, connection_string="")
    assert result is False


def test_export_openapi_spec(tmp_path: Path):
    """Verify export_openapi_spec exports valid openapi.json."""
    spec = export_openapi_spec(tmp_path)
    assert "openapi" in spec
    assert "paths" in spec
    assert (tmp_path / "openapi.json").exists()

    with open(tmp_path / "openapi.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["info"]["title"] == "TicketGenie API"


def test_parse_openapi_spec():
    """Verify route parsing from FastAPI OpenAPI schema."""
    spec = app.openapi()
    routes = parse_openapi_spec(spec)
    assert len(routes) > 0

    route_paths = [r["path"] for r in routes]
    assert "/" in route_paths
    assert "/health" in route_paths


def test_generate_kql_queries():
    """Verify KQL queries string generation."""
    spec = app.openapi()
    routes = parse_openapi_spec(spec)
    kql = generate_kql_queries(routes)

    assert "Azure Application Insights KQL Diagnostic Queries" in kql
    assert "percentiles(duration, 95)" in kql
    assert "requests" in kql


def test_generate_workbook_json():
    """Verify Workbook JSON generation."""
    spec = app.openapi()
    routes = parse_openapi_spec(spec)
    workbook = generate_workbook_json(routes)

    assert workbook["version"] == "Notebook/1.0"
    assert len(workbook["items"]) >= 3
    assert "TicketGenie" in workbook["tags"]


def test_generate_terraform_alerts():
    """Verify Terraform metric alert rules generation."""
    spec = app.openapi()
    routes = parse_openapi_spec(spec)
    alerts_hcl = generate_terraform_alerts(routes)

    assert "azurerm_monitor_metric_alert" in alerts_hcl
    assert "alert-ticketgenie-api-5xx-errors" in alerts_hcl
    assert "requests/duration" in alerts_hcl
