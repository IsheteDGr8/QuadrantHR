# ---------------------------------------------------------------------------
# Azure AI Search — backs the "further reading" feature: a small, curated
# index of external regulatory links (HIPAA, FMLA, FLSA, EEOC, IRS mileage
# rates) filtered by policy_type. This is a keyword/filter search over a
# handful of hand-picked documents, not a RAG/embedding pipeline — free tier
# is intentionally plenty for that.
#
# The index itself isn't created by Terraform (search_index_setup.py and
# seed_reference_links.py, run manually with the admin key output below,
# handle the index schema and its documents) — Terraform only provisions
# the search service.
# ---------------------------------------------------------------------------

resource "azurerm_search_service" "main" {
  name                = "srch-ai-policy"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  sku                 = "free"
}
