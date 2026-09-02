# ---------------------------------------------------------------------------
# Backend compute — this was missing before: storage existed, but nothing
# actually ran the FastAPI app. Adding the minimum needed for the CI/CD
# pipeline to have somewhere real to deploy to.
# ---------------------------------------------------------------------------

resource "azurerm_service_plan" "backend" {
  name                = "asp-ai-policy-backend"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "B1"
}

resource "azurerm_linux_web_app" "backend" {
  name                = "app-ai-policy-backend"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.backend.id

  # System-assigned identity for least-privilege blob access. This is now
  # load-bearing: the connection-string app setting has been removed below,
  # so storage_service.py authenticates via this identity + the
  # "Storage Blob Data Contributor" role assignment (further down this
  # file) exclusively.
  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    cors {
      # This is NOT just a secondary layer that main.py's own
      # CORSMiddleware makes redundant — that assumption (from when this
      # block was first tightened) turned out to be wrong. This
      # platform-level setting is enforced by Azure's edge BEFORE a
      # request ever reaches the FastAPI app, so a mismatch between the
      # two lists blocks the request outright with a 400 on the OPTIONS
      # preflight — confirmed directly:
      #   curl -X OPTIONS .../demo-login -H "Origin: http://localhost:5173"
      #   -> HTTP 400 "The origin ... is not allowed" (from Azure's own
      #      middleware, x-ms-middleware-request-id header — never
      #      reaches main.py).
      # This only surfaces on POST/PATCH (they trigger a CORS preflight;
      # plain GETs don't), which is why it went unnoticed: it silently
      # broke local dev against the real backend for anything but simple
      # reads. Mirrors backend/main.py's CORSMiddleware allow_origins
      # exactly — keep the two lists in sync going forward.
      allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://${azurerm_static_web_app.frontend.default_host_name}",
      ]
    }
    # Without this, Azure just shows its default placeholder page even
    # after a successful deploy — it needs to be told how to actually
    # start the app.
    app_command_line = "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
  }

  app_settings = {
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"

    # Cutover complete: storage_service.py now authenticates via the
    # managed identity below (Storage Blob Data Contributor, scoped to
    # just this storage account) instead of a connection-string secret.
    # No secret in App Service config anymore. If this ever needs rolling
    # back, re-add "AZURE_STORAGE_CONNECTION_STRING" =
    # azurerm_storage_account.main.primary_connection_string — the code
    # still supports it and prioritizes it over the identity path.
    "AZURE_STORAGE_ACCOUNT_NAME" = azurerm_storage_account.main.name

    # Placeholders — openai_service.py already handles these being unset
    # (falls back to its placeholder response), so leaving blank here is
    # safe until real Azure OpenAI credentials exist.
    "AZURE_OPENAI_ENDPOINT"   = var.azure_openai_endpoint
    "AZURE_OPENAI_API_KEY"    = var.azure_openai_api_key
    "AZURE_OPENAI_DEPLOYMENT" = var.azure_openai_deployment

    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.backend.connection_string

    # Runtime uses a query key (read-only, search-only) rather than the
    # admin key — the app only ever queries this index, never manages its
    # schema or documents, so it doesn't need write access. The admin key
    # (for search_index_setup.py / seed_reference_links.py) is a separate
    # sensitive output, not an app setting.
    "AZURE_SEARCH_ENDPOINT" = "https://${azurerm_search_service.main.name}.search.windows.net"
    "AZURE_SEARCH_KEY"      = azurerm_search_service.main.query_keys[0].key
    "AZURE_SEARCH_INDEX"    = "policy-reference-links"
  }

  virtual_network_subnet_id = azurerm_subnet.backend_integration.id
}

# Least-privilege data access for the backend's managed identity, scoped to
# just this storage account (not the resource group or subscription). This
# is what storage_service.py actually authenticates through now that the
# connection string has been removed above.
resource "azurerm_role_assignment" "backend_storage_access" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_web_app.backend.identity[0].principal_id
}

# ---------------------------------------------------------------------------
# storage_service.py currently hardcodes CONTAINER_NAME = "policies", which
# doesn't match either container actually defined (source-documents,
# generated-policies) — this container exists so that mismatch doesn't
# silently create an untracked container outside Terraform's view. The
# better long-term fix is updating storage_service.py to use
# "generated-policies" instead and removing this — flag it to whoever owns
# that file rather than carrying two names indefinitely.
# ---------------------------------------------------------------------------
resource "azurerm_storage_container" "policies_compat" {
  name                  = "policies"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
