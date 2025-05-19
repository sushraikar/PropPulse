/**
 * Key Vault module for PropPulse infrastructure
 * 
 * Creates an Azure Key Vault with private endpoint and stores secrets
 */

# Variables
variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "location" {
  description = "Azure region to deploy resources"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for private endpoint"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Map of secrets to store in Key Vault"
  type        = map(string)
  sensitive   = true
  default     = {}
}

# Data sources
data "azurerm_client_config" "current" {}

# Key Vault
resource "azurerm_key_vault" "main" {
  name                        = "kv-proppulse-${var.environment}"
  resource_group_name         = var.resource_group_name
  location                    = var.location
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = true
  enable_rbac_authorization   = true
  sku_name                    = "standard"
  tags                        = var.tags
  
  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    ip_rules                   = []
    virtual_network_subnet_ids = []
  }
}

# Private Endpoint
resource "azurerm_private_endpoint" "key_vault" {
  name                = "pe-kv-proppulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.subnet_id
  tags                = var.tags
  
  private_service_connection {
    name                           = "psc-kv-proppulse-${var.environment}"
    private_connection_resource_id = azurerm_key_vault.main.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }
}

# Private DNS Zone
resource "azurerm_private_dns_zone" "key_vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# Private DNS Zone Link
resource "azurerm_private_dns_zone_virtual_network_link" "key_vault" {
  name                  = "pdns-link-kv-proppulse-${var.environment}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.key_vault.name
  virtual_network_id    = data.azurerm_subnet.endpoint_subnet.virtual_network_id
  tags                  = var.tags
}

# Data source for subnet
data "azurerm_subnet" "endpoint_subnet" {
  name                 = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 1)
  virtual_network_name = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 3)
  resource_group_name  = var.resource_group_name
}

# RBAC Role Assignment
resource "azurerm_role_assignment" "key_vault_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Secrets
resource "azurerm_key_vault_secret" "secrets" {
  for_each     = var.secrets
  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [
    azurerm_role_assignment.key_vault_admin,
    azurerm_private_endpoint.key_vault
  ]
}

# Outputs
output "key_vault_id" {
  description = "Key Vault ID"
  value       = azurerm_key_vault.main.id
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}
