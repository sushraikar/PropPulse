/**
 * Monitoring module for PropPulse infrastructure
 * 
 * Creates Log Analytics workspace and Azure Defender for Cloud
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

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-proppulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# Security Center
resource "azurerm_security_center_subscription_pricing" "main" {
  for_each      = toset(["VirtualMachines", "SqlServers", "AppServices", "StorageAccounts", "ContainerRegistry", "KeyVaults", "KubernetesService"])
  tier          = "Standard"
  resource_type = each.key
}

# Security Center Workspace
resource "azurerm_security_center_workspace" "main" {
  scope        = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  workspace_id = azurerm_log_analytics_workspace.main.id
  
  depends_on = [
    azurerm_security_center_subscription_pricing.main
  ]
}

# Data sources
data "azurerm_client_config" "current" {}

# Outputs
output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = azurerm_log_analytics_workspace.main.id
}

output "log_analytics_workspace_name" {
  description = "Log Analytics Workspace name"
  value       = azurerm_log_analytics_workspace.main.name
}

output "log_analytics_workspace_primary_key" {
  description = "Log Analytics Workspace primary key"
  value       = azurerm_log_analytics_workspace.main.primary_shared_key
  sensitive   = true
}
