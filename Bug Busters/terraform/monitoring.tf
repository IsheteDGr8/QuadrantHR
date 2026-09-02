# ---------------------------------------------------------------------------
# SRE / monitoring baseline for the backend App Service.
#
# Static Web Apps don't support server-side Application Insights the way
# App Service does, so this covers the backend only. Frontend RUM (real user
# monitoring) would need the App Insights JS SDK wired into the React app
# separately — not done here, flagging for whoever picks up frontend
# observability.
#
# SLO/SLI targets below (99% availability, P95 latency, <1% error rate) are
# placeholder starting points, not numbers the team has agreed on — treat
# them as a first draft to review, not a commitment.
# ---------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-ai-policy"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "backend" {
  name                = "appi-ai-policy-backend"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

# --------------------------------------------------
# Alerting — where notifications go
# --------------------------------------------------

resource "azurerm_monitor_action_group" "sre" {
  name                = "ag-ai-policy-sre"
  resource_group_name = data.azurerm_resource_group.main.name
  short_name          = "aipolicysre"

  email_receiver {
    name                    = "primary-oncall"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# --------------------------------------------------
# Availability — SLI: is the backend reachable at all
# SLO (draft): 99% successful pings over a rolling window
# --------------------------------------------------

resource "azurerm_application_insights_web_test" "backend_ping" {
  name                    = "webtest-ai-policy-backend"
  resource_group_name     = data.azurerm_resource_group.main.name
  location                = data.azurerm_resource_group.main.location
  application_insights_id = azurerm_application_insights.backend.id
  kind                    = "ping"
  frequency               = 300
  timeout                 = 30
  enabled                 = true
  geo_locations           = ["us-tx-sn1-azr", "us-il-ch1-azr"]

  configuration = <<XML
<WebTest Name="webtest-ai-policy-backend" Enabled="True" Timeout="30" xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Items>
    <Request Method="GET" Guid="a5f10126-e4cd-570d-961c-cea43999a200" Version="1.1" Url="https://${azurerm_linux_web_app.backend.default_hostname}/" ThinkTime="0" Timeout="30" ParseDependentRequests="False" FollowRedirects="True" RecordResult="True" Cache="False" ResponseTimeGoal="0" Encoding="utf-8" ExpectedHttpStatusCode="200" ExpectedResponseUrl="" ReportingName="" IgnoreHttpStatusCode="False" />
  </Items>
</WebTest>
XML
}

resource "azurerm_monitor_metric_alert" "backend_availability" {
  name                = "alert-ai-policy-backend-availability"
  resource_group_name = data.azurerm_resource_group.main.name
  # Availability alerts on a web test need BOTH the web test and the App
  # Insights resource in scopes — App Insights alone gets rejected by the
  # API with "Alert scope is invalid" (confirmed against live Azure).
  scopes = [
    azurerm_application_insights_web_test.backend_ping.id,
    azurerm_application_insights.backend.id,
  ]
  description = "SLO: 99% of pings succeed over 15 min. Fires when availability drops below that."
  severity    = 1
  frequency   = "PT5M"
  window_size = "PT15M"

  application_insights_web_test_location_availability_criteria {
    web_test_id           = azurerm_application_insights_web_test.backend_ping.id
    component_id          = azurerm_application_insights.backend.id
    failed_location_count = 2
  }

  action {
    action_group_id = azurerm_monitor_action_group.sre.id
  }
}

# --------------------------------------------------
# Error rate — SLI: proportion of server errors
# SLO (draft): <1% of requests return 5xx over 15 min
# --------------------------------------------------

resource "azurerm_monitor_metric_alert" "backend_server_errors" {
  name                = "alert-ai-policy-backend-5xx"
  resource_group_name = data.azurerm_resource_group.main.name
  scopes              = [azurerm_linux_web_app.backend.id]
  description         = "SLO: <1% 5xx error rate. Fires on a sustained burst of server errors."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "Http5xx"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.sre.id
  }
}

# --------------------------------------------------
# Latency — SLI: response time
# SLO (draft): P95 response time under 2s
# --------------------------------------------------

resource "azurerm_monitor_metric_alert" "backend_response_time" {
  name                = "alert-ai-policy-backend-latency"
  resource_group_name = data.azurerm_resource_group.main.name
  scopes              = [azurerm_linux_web_app.backend.id]
  description         = "SLO: P95 response time < 2s. Fires when average response time exceeds that over 15 min."
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "AverageResponseTime"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 2
  }

  action {
    action_group_id = azurerm_monitor_action_group.sre.id
  }
}
