terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }
  }
  
  backend "azurerm" {
    # Backend configuration will be provided via CLI or environment variables
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

provider "azuread" {}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region to deploy resources"
  type        = string
  default     = "uaenorth"  # Dubai data center
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = null
}

variable "backend_image" {
  description = "Backend Docker image"
  type        = string
}

variable "frontend_image" {
  description = "Frontend Docker image"
  type        = string
}

variable "zoho_client_id" {
  description = "Zoho CRM client ID"
  type        = string
  sensitive   = true
}

variable "zoho_client_secret" {
  description = "Zoho CRM client secret"
  type        = string
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "supabase_url" {
  description = "Supabase URL"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "Supabase key"
  type        = string
  sensitive   = true
}

# Local variables
locals {
  resource_group_name = var.resource_group_name != null ? var.resource_group_name : "rg-proppulse-${var.environment}"
  tags = {
    Environment = var.environment
    Project     = "PropPulse"
    ManagedBy   = "Terraform"
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.tags
}

# Virtual Network
module "network" {
  source              = "./modules/network"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  tags                = local.tags
}

# Key Vault
module "key_vault" {
  source              = "./modules/key_vault"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  subnet_id           = module.network.private_endpoints_subnet_id
  tags                = local.tags
  
  secrets = {
    "zoho-client-id"     = var.zoho_client_id
    "zoho-client-secret" = var.zoho_client_secret
    "pinecone-api-key"   = var.pinecone_api_key
    "openai-api-key"     = var.openai_api_key
    "supabase-url"       = var.supabase_url
    "supabase-key"       = var.supabase_key
  }
}

# PostgreSQL
module "postgresql" {
  source              = "./modules/postgresql"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  subnet_id           = module.network.private_endpoints_subnet_id
  tags                = local.tags
}

# Storage Account
module "storage" {
  source              = "./modules/storage"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  subnet_id           = module.network.private_endpoints_subnet_id
  tags                = local.tags
}

# Container Apps
module "container_apps" {
  source              = "./modules/container_apps"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  subnet_id           = module.network.container_apps_subnet_id
  key_vault_id        = module.key_vault.key_vault_id
  storage_account_name = module.storage.storage_account_name
  postgresql_connection_string = module.postgresql.connection_string
  backend_image       = var.backend_image
  frontend_image      = var.frontend_image
  tags                = local.tags
}

# Log Analytics and Monitoring
module "monitoring" {
  source              = "./modules/monitoring"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  environment         = var.environment
  tags                = local.tags
}

# Outputs
output "app_url" {
  description = "URL of the deployed application"
  value       = module.container_apps.app_url
}

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = module.key_vault.key_vault_name
}

output "storage_account_name" {
  description = "Storage account name"
  value       = module.storage.storage_account_name
}

output "postgresql_server_name" {
  description = "PostgreSQL server name"
  value       = module.postgresql.server_name
}
