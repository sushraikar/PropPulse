/**
 * PostgreSQL module for PropPulse infrastructure
 * 
 * Creates an Azure Database for PostgreSQL Flexible Server with private endpoint
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

variable "sku_name" {
  description = "PostgreSQL SKU name"
  type        = string
  default     = "B_Standard_B1ms"
}

variable "storage_mb" {
  description = "PostgreSQL storage in MB"
  type        = number
  default     = 32768
}

variable "postgresql_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "14"
}

# Random password for PostgreSQL admin
resource "random_password" "postgresql" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# PostgreSQL Flexible Server
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "psql-proppulse-${var.environment}"
  resource_group_name    = var.resource_group_name
  location               = var.location
  version                = var.postgresql_version
  delegated_subnet_id    = var.subnet_id
  private_dns_zone_id    = azurerm_private_dns_zone.postgresql.id
  administrator_login    = "proppulseadmin"
  administrator_password = random_password.postgresql.result
  zone                   = "1"
  storage_mb             = var.storage_mb
  sku_name               = var.sku_name
  backup_retention_days  = 7
  
  high_availability {
    mode = "Disabled"
  }
  
  tags = var.tags
}

# Private DNS Zone
resource "azurerm_private_dns_zone" "postgresql" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# Private DNS Zone Link
resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "pdns-link-psql-proppulse-${var.environment}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = data.azurerm_subnet.postgresql_subnet.virtual_network_id
  tags                  = var.tags
}

# Data source for subnet
data "azurerm_subnet" "postgresql_subnet" {
  name                 = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 1)
  virtual_network_name = element(split("/", var.subnet_id), length(split("/", var.subnet_id)) - 3)
  resource_group_name  = var.resource_group_name
}

# Database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "proppulse"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Firewall rule to allow Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Outputs
output "server_id" {
  description = "PostgreSQL server ID"
  value       = azurerm_postgresql_flexible_server.main.id
}

output "server_name" {
  description = "PostgreSQL server name"
  value       = azurerm_postgresql_flexible_server.main.name
}

output "server_fqdn" {
  description = "PostgreSQL server FQDN"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "database_name" {
  description = "PostgreSQL database name"
  value       = azurerm_postgresql_flexible_server_database.main.name
}

output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.postgresql.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}"
  sensitive   = true
}
