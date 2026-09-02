# --- Reference Existing Resource Group ---

data "azurerm_resource_group" "rg" {
  name = "Azure_Rangers"
}

data "azurerm_storage_account" "knowledge" {
  name                = "seed123data"
  resource_group_name = data.azurerm_resource_group.rg.name
}

# --- Generate Secure DB Password ---

resource "random_password" "db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# --- Azure SQL Database ---

resource "azurerm_mssql_server" "sql" {
  name                         = "sql-server-ticket-genie-westus-prod"
  resource_group_name          = data.azurerm_resource_group.rg.name
  location                     = var.region
  version                      = "12.0"
  administrator_login          = "dbadmin"
  administrator_login_password = random_password.db_password.result
}

resource "azurerm_mssql_database" "db" {
  name        = "app-db"
  server_id   = azurerm_mssql_server.sql.id
  collation   = "SQL_Latin1_General_CP1_CI_AS"
  sku_name    = "Basic"
  max_size_gb = 2
}

# Allow internal Azure services (like the Web App) to reach SQL
resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.sql.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
# --- Azure Container Registry ---

resource "azurerm_container_registry" "acr" {
  name                = "acrwebappprodticketgenie" # Must be globally unique (alphanumeric only, lowercase)
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region
  sku                 = "Basic" # Basic tier is ~$5/month
  admin_enabled       = true    # Enables admin username/password for simple auth
}
# --- Linux Web Apps (Backend API & Frontend UI) ---

resource "azurerm_service_plan" "asp" {
  name                = "asp-app-prod"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region
  os_type             = "Linux"
  sku_name            = "B1"
}

# 1. Backend Web App (FastAPI REST API) - Port 8000
resource "azurerm_linux_web_app" "backend" {
  name                = "webapp-prod-backend-ticketgenie"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = azurerm_service_plan.asp.location
  service_plan_id     = azurerm_service_plan.asp.id

  site_config {
    always_on = true

    application_stack {
      docker_image_name        = "ticket-genie-backend:latest"
      docker_registry_url      = "https://${azurerm_container_registry.acr.login_server}"
      docker_registry_username = azurerm_container_registry.acr.admin_username
      docker_registry_password = azurerm_container_registry.acr.admin_password
    }
  }

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    "DATABASE_URL"                               = "Server=tcp:${azurerm_mssql_server.sql.fully_qualified_domain_name},1433;Initial Catalog=${azurerm_mssql_database.db.name};Persist Security Info=False;User ID=${azurerm_mssql_server.sql.administrator_login};Password=${random_password.db_password.result};MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;"
    "WEBSITES_PORT"                              = "8000"
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE"        = "false"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"      = azurerm_application_insights.appi.connection_string
    "LOG_ANALYTICS_WORKSPACE_ID"                 = azurerm_log_analytics_workspace.law.workspace_id
    "ApplicationInsightsAgent_EXTENSION_VERSION" = "~3"
    "OTEL_TRACES_SAMPLER"                        = "always_on"
    "ENABLE_SYNTHETIC_ANALYTICS"                 = "true"
    "AZURE_CLIENT_ID"                            = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-client-id)"
    "AZURE_CLIENT_SECRET"                        = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-client-secret)"
    "AZURE_TENANT_ID"                            = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-tenant-id)"
    "AZURE_MANAGED_IDENTITY_CLIENT_ID"           = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-managed-identity-client-id)"
    "AZURE_STORAGE_ACCOUNT_NAME"                 = data.azurerm_storage_account.knowledge.name
    "KNOWLEDGE_BLOB_CONTAINER"                   = "ticket-genie-knowledge"
    "GOOGLE_EMAIL"                               = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=google-email)"
    "SMTP_USER"                                  = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=smtp-user)"
    "GOOGLE_APP_PASSWORD"                        = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=google-app-password)"
    "SMTP_PASSWORD"                              = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=smtp-password)"
    "SMTP_HOST"                                  = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=smtp-host)"
    "SMTP_PORT"                                  = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=smtp-port)"
    "SMTP_USE_TLS"                               = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=smtp-use-tls)"
    "AZURE_OPENAI_ENDPOINT"                      = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-openai-endpoint)"
    "GROUP1OPENAIENDPOINT"                       = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1openaiendpoint)"
    "AZURE_OPENAI_API_KEY"                       = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-openai-api-key)"
    "GROUP1OPENAIAPIKEY"                         = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1openaiapikey)"
    "GROUP1_EMBEDDING_API_KEY"                   = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1-embedding-api-key)"
    "GROUP1_EMBEDDING_ENDPOINT"                  = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1-embedding-endpoint)"
    "GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY"       = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1-embedding-api-key)"
    "GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT"     = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=group1-embedding-endpoint)"
    "AZURE_AI_SEARCH_ENDPOINT"                   = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-ai-search-endpoint)"
    "AZURE_AI_SEARCH_KEY"                        = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-ai-search-key)"
    "AISEARCH_ENDPOINT"                          = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-ai-search-endpoint)"
    "AISEARCH_APIKEY"                            = "@Microsoft.KeyVault(VaultName=kv-app-prod-12345;SecretName=azure-ai-search-key)"
    "AISEARCH_INDEX_NAME"                        = "group-1"
  }

  lifecycle {
    ignore_changes = [
      site_config[0].application_stack[0].docker_image_name,
    ]
  }
}

# 2. Frontend Web App (Nginx UI with Reverse Proxy) - Port 80
resource "azurerm_linux_web_app" "frontend" {
  name                = "webapp-prod-frontend-ticketgenie"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = azurerm_service_plan.asp.location
  service_plan_id     = azurerm_service_plan.asp.id

  site_config {
    always_on = true

    application_stack {
      docker_image_name        = "ticketgenie:latest"
      docker_registry_url      = "https://${azurerm_container_registry.acr.login_server}"
      docker_registry_username = azurerm_container_registry.acr.admin_username
      docker_registry_password = azurerm_container_registry.acr.admin_password
    }
  }

  app_settings = {
    "BACKEND_API_URL"                     = "https://${azurerm_linux_web_app.backend.default_hostname}"
    "WEBSITES_PORT"                       = "80"
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = "false"
  }

  lifecycle {
    ignore_changes = [
      site_config[0].application_stack[0].docker_image_name,
    ]
  }
}

resource "azurerm_role_assignment" "backend_knowledge_blob_contributor" {
  name                 = "87b70dda-dcae-453b-b4f1-e626196e6080"
  scope                = data.azurerm_storage_account.knowledge.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_web_app.backend.identity[0].principal_id
}
