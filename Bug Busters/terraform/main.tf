# Uses the resource group Quadrant already provisioned for us — do NOT
# create a new one. Terraform will manage resources *inside* it without
# taking ownership of (or being able to accidentally delete) the group
# itself.
data "azurerm_resource_group" "main" {
  name = "BugBusters"
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_storage_account" "main" {
  name                     = "aipolicykhusum${random_string.suffix.result}"
  resource_group_name      = data.azurerm_resource_group.main.name
  location                 = data.azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "source_documents" {
  name                  = "source-documents"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "generated_policies" {
  name                  = "generated-policies"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# --------------------------------------------------
# Frontend - Azure Static Web App
# --------------------------------------------------

resource "azurerm_static_web_app" "frontend" {
  name                = "app-ai-policy-frontend"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = "eastus2"

  sku_tier = "Free"
  sku_size = "Free"
}