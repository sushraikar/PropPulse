/**
 * Container Apps module for PropPulse infrastructure
 * 
 * Creates Azure Container Apps for backend and frontend services
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
  description = "Subnet ID for Container Apps environment"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault ID"
  type        = string
}

variable "storage_account_name" {
  description = "Storage Account name"
  type        = string
}

variable "postgresql_connection_string" {
  description = "PostgreSQL connection string"
  type        = string
  sensitive   = true
}

variable "backend_image" {
  description = "Backend Docker image"
  type        = string
}

variable "frontend_image" {
  description = "Frontend Docker image"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

# Container Apps Environment
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-proppulse-${var.environment}"
  resource_group_name        = var.resource_group_name
  location                   = var.location
  infrastructure_subnet_id   = var.subnet_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
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

# Managed Identity for Container Apps
resource "azurerm_user_assigned_identity" "container_apps" {
  name                = "id-container-apps-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

# Key Vault Access Policy
resource "azurerm_key_vault_access_policy" "container_apps" {
  key_vault_id = var.key_vault_id
  tenant_id    = azurerm_user_assigned_identity.container_apps.tenant_id
  object_id    = azurerm_user_assigned_identity.container_apps.principal_id
  
  secret_permissions = [
    "Get",
    "List"
  ]
}

# Backend Container App
resource "azurerm_container_app" "backend" {
  name                         = "ca-backend-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags
  
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }
  
  template {
    container {
      name   = "backend"
      image  = var.backend_image
      cpu    = 1.0
      memory = "2Gi"
      
      env {
        name  = "DATABASE_URL"
        value = var.postgresql_connection_string
      }
      
      env {
        name  = "STORAGE_ACCOUNT_NAME"
        value = var.storage_account_name
      }
      
      env {
        name        = "ZOHO_CLIENT_ID"
        secret_name = "zoho-client-id"
      }
      
      env {
        name        = "ZOHO_CLIENT_SECRET"
        secret_name = "zoho-client-secret"
      }
      
      env {
        name        = "PINECONE_API_KEY"
        secret_name = "pinecone-api-key"
      }
      
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      
      env {
        name        = "SUPABASE_URL"
        secret_name = "supabase-url"
      }
      
      env {
        name        = "SUPABASE_KEY"
        secret_name = "supabase-key"
      }
    }
    
    min_replicas = 1
    max_replicas = 5
  }
  
  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
  
  secret {
    name  = "zoho-client-id"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/zoho-client-id/)"
  }
  
  secret {
    name  = "zoho-client-secret"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/zoho-client-secret/)"
  }
  
  secret {
    name  = "pinecone-api-key"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/pinecone-api-key/)"
  }
  
  secret {
    name  = "openai-api-key"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/openai-api-key/)"
  }
  
  secret {
    name  = "supabase-url"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/supabase-url/)"
  }
  
  secret {
    name  = "supabase-key"
    value = "@Microsoft.KeyVault(SecretUri=https://${element(split("/", var.key_vault_id), length(split("/", var.key_vault_id)) - 1)}.vault.azure.net/secrets/supabase-key/)"
  }
  
  depends_on = [
    azurerm_key_vault_access_policy.container_apps
  ]
}

# Frontend Container App
resource "azurerm_container_app" "frontend" {
  name                         = "ca-frontend-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags
  
  template {
    container {
      name   = "frontend"
      image  = var.frontend_image
      cpu    = 0.5
      memory = "1Gi"
      
      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
      }
    }
    
    min_replicas = 1
    max_replicas = 3
  }
  
  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# Outputs
output "backend_url" {
  description = "Backend URL"
  value       = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "app_url" {
  description = "Main application URL"
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}
