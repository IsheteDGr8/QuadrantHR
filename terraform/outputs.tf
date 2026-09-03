output "frontend_webapp_url" {
  value       = "https://${azurerm_linux_web_app.frontend.default_hostname}"
  description = "The public URL of the deployed Streamlit Frontend Web App"
}

output "frontend_webapp_name" {
  value       = azurerm_linux_web_app.frontend.name
  description = "The name of the Frontend Web App resource"
}

output "backend_webapp_url" {
  value       = "https://${azurerm_linux_web_app.backend.default_hostname}"
  description = "The public URL of the deployed FastAPI Backend Web App"
}

output "backend_webapp_name" {
  value       = azurerm_linux_web_app.backend.name
  description = "The name of the Backend Web App resource"
}

# --- Database Outputs ---

output "sql_server_fqdn" {
  value       = azurerm_mssql_server.sql.fully_qualified_domain_name
  description = "Fully qualified domain name of the Azure SQL Server"
}

output "database_name" {
  value       = azurerm_mssql_database.db.name
  description = "Name of the Azure SQL Database"
}

# --- Key Vault Outputs ---

output "key_vault_name" {
  value       = azurerm_key_vault.kv.name
  description = "Name of the Key Vault storing secrets"
}

output "key_vault_secret_name" {
  value       = azurerm_key_vault_secret.db_password.name
  description = "Key Vault secret name holding the SQL admin password"
}
output "acr_login_server" {
  value       = azurerm_container_registry.acr.login_server
  description = "The login server for Azure Container Registry"
}

# --- Monitoring Outputs ---

output "application_insights_connection_string" {
  value       = azurerm_application_insights.appi.connection_string
  description = "Connection string for Azure Application Insights"
  sensitive   = true
}

output "application_insights_instrumentation_key" {
  value       = azurerm_application_insights.appi.instrumentation_key
  description = "Instrumentation key for Azure Application Insights"
  sensitive   = true
}

output "log_analytics_workspace_id" {
  value       = azurerm_log_analytics_workspace.law.id
  description = "Resource ID of the Log Analytics Workspace"
}