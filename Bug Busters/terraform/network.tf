# ---------------------------------------------------------------------------
# Regional VNet integration for the backend App Service — outbound traffic
# from the app can be routed through this subnet. This does NOT restrict
# inbound public access (the app is still reachable from the internet the
# same as before) and does NOT lock down the storage account — it's the
# first step (giving the app a network identity to route through), not full
# network isolation.
#
# A fuller lockdown (private endpoints on the storage account + private DNS
# zones so blob traffic never leaves the VNet, NSGs restricting subnet
# traffic) is a bigger change that needs its own design pass — flagging
# rather than half-implementing it here, since a broken private endpoint /
# DNS setup would silently cut off storage access with no local way to
# verify it before it's live.
# ---------------------------------------------------------------------------

resource "azurerm_virtual_network" "main" {
  name                = "vnet-ai-policy"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  address_space       = ["10.20.0.0/16"]
}

resource "azurerm_subnet" "backend_integration" {
  name                 = "snet-ai-policy-backend"
  resource_group_name  = data.azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.20.1.0/24"]

  delegation {
    name = "backend-delegation"

    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}
