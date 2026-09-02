data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "kv" {
  name                        = "kv-app-prod-12345"
  location                    = data.azurerm_resource_group.rg.location
  resource_group_name         = data.azurerm_resource_group.rg.name
  enabled_for_disk_encryption = true
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false
  sku_name                    = "standard"

  # NOTE: Do NOT use inline access_policy blocks here when managing individual access policies separately.
}

# 1. App/Identity Policy (da02463e-9da4-4f3e-99d3-c68530280b2a)
resource "azurerm_key_vault_access_policy" "app_identity" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = "da02463e-9da4-4f3e-99d3-c68530280b2a"

  certificate_permissions = ["Get", "List"]
  key_permissions         = ["Get"]
  secret_permissions      = ["Get", "List"]
}

# 2. Admin / Deployer User Policy (3c2f99ad-d759-4bcb-aba4-17823aaa36ec)
resource "azurerm_key_vault_access_policy" "admin_user" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = "3c2f99ad-d759-4bcb-aba4-17823aaa36ec"

  key_permissions = [
    "Get", "List", "Create", "Import", "Delete", "Recover",
    "Backup", "Restore", "GetRotationPolicy", "SetRotationPolicy",
    "Rotate", "Update"
  ]
  secret_permissions = [
    "Get", "List", "Set", "Delete", "Purge", "Recover", "Backup", "Restore"
  ]
}

# 3. Backend Web App Managed Identity Access Policy
resource "azurerm_key_vault_access_policy" "backend_web_app" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_web_app.backend.identity[0].principal_id

  secret_permissions = ["Get", "List"]
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "db-admin-password"
  value        = random_password.db_password.result
  key_vault_id = azurerm_key_vault.kv.id

  # Ensures access policies exist before secrets are created
  depends_on = [
    azurerm_key_vault_access_policy.admin_user
  ]
}