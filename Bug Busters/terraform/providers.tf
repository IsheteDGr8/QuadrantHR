terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state — shared by the whole team via the storage account created
  # once, up front (see README note below). Without this, state lives on
  # whoever's laptop last ran `apply`, which breaks the moment two people
  # touch infra or that laptop is unavailable.
  backend "azurerm" {
    resource_group_name  = "BugBusters"
    storage_account_name = "sttfstatebugbusters"
    container_name       = "tfstate"
    key                  = "app.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}

  # Pinned explicitly so `terraform apply` always targets the correct
  # subscription regardless of whichever subscription happens to be
  # active in the person-running-it's `az login` session.
  subscription_id = "7981312c-4577-455a-8bae-10269b74a97b" # Quadrant Internship
}
