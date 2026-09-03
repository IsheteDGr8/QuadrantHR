# --- Log Analytics Workspace & Application Insights Monitoring Infrastructure ---

resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-ticketgenie-westus-prod"
  location            = var.region
  resource_group_name = data.azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "appi" {
  name                = "appi-ticketgenie-westus-prod"
  location            = var.region
  resource_group_name = data.azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"
  sampling_percentage = 100
}

resource "azurerm_role_assignment" "backend_log_analytics_reader" {
  scope                = azurerm_log_analytics_workspace.law.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_linux_web_app.backend.identity[0].principal_id
}

# --- OpenAPI Auto-Generated Dashboard Workbook ---

resource "azurerm_application_insights_workbook" "wb_openapi" {
  name                = "6f29910d-2f08-4d56-a052-7b24391e8432"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region
  display_name        = "FastAPI Backend - OpenAPI Monitoring Workbook"
  data_json           = file("${path.module}/../artifacts/openapi_workbook.json")
}
