/**
 * Storage module for PropPulse infrastructure
 * 
 * Creates an Azure Storage Account with private endpoint for blob storage
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

# Storage Account
resource "azurerm_storage_account" "main" {
  name                     = "stproppulse${var.environment}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
  enable_https_traffic_only = true
  allow_nested_items_to_be_public = false
  
  blob_properties {
    versioning_enabled = true
    
    container_delete_retention_policy {
      days = 7
    }
    
    delete_retention_policy {
      days = 7
    }
  }
  
  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
  
  tags = var.tags
}

# Blob Containers
resource "azurerm_storage_container" "proposals" {
  name                  = "proposals"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "images" {
  name                  = "images"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

# Private Endpoint
resource "azurerm_private_endpoint" "storage_blob" {
  name                = "pe-st-blob-proppulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.subnet_id
  tags                = var.tags
  
  private_service_connection {
    name                           = "psc-st-blob-proppulse-${var.environment}"
    private_connection_resource_id = azurerm_storage_account.main.id
    is_manual_connection           = false
    subresource_names              = ["blob"]
  }
}

# Private DNS Zone
resource "azurerm_private_dns_zone" "storage_blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# Private DNS Zone Link
resource "azurerm_private_dns_zone_virtual_network_link" "storage_blob" {
  name                  = "pdns-link-st-blob-proppulse-${var.environment}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.storage_blob.name
  virtual_network_id    = data.azurerm_subnet.endpoint_subnet.virtual_network_id
  tags                  = var.tags
}

# Data source for subnet
data "azurerm_subnet" "endpoint_subnet" {
  name                 = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 1)
  virtual_network_name = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 3)
  resource_group_name  = var.resource_group_name
}

# Outputs
output "storage_account_id" {
  description = "Storage Account ID"
  value       = azurerm_storage_account.main.id
}

output "storage_account_name" {
  description = "Storage Account name"
  value       = azurerm_storage_account.main.name
}

output "primary_blob_endpoint" {
  description = "Primary Blob Endpoint"
  value       = azurerm_storage_account.main.primary_blob_endpoint
}

output "proposals_container_name" {
  description = "Proposals container name"
  value       = azurerm_storage_container.proposals.name
}

output "documents_container_name" {
  description = "Documents container name"
  value       = azurerm_storage_container.documents.name
}

output "images_container_name" {
  description = "Images container name"
  value       = azurerm_storage_container.images.name
}
