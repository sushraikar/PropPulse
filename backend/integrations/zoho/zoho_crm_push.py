"""
CRM integration for pushing new developer listings to Zoho Opportunities pipeline.

This module provides:
1. Automatic creation of Opportunities in Zoho CRM for new developer listings
2. Assignment to sales squads based on tower location
3. Webhook handlers for status updates
4. Synchronization between PropPulse and Zoho CRM
"""

import os
import json
import uuid
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import requests
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Get Zoho credentials from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
zoho_client_id = secret_client.get_secret("ZOHO-CLIENT-ID").value
zoho_client_secret = secret_client.get_secret("ZOHO-CLIENT-SECRET").value
zoho_refresh_token = secret_client.get_secret("ZOHO-REFRESH-TOKEN").value
zoho_domain = "https://accounts.zoho.eu"  # EU tenant as specified in requirements

class ZohoCRMIntegration:
    """Integration with Zoho CRM for developer listings."""
    
    def __init__(self, db: Session = None):
        """Initialize the integration."""
        self.db = db
        self.access_token = None
        self.token_expiry = 0
    
    async def push_listing_to_crm(
        self, 
        property_id: str, 
        developer_id: str,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Push a new developer listing to Zoho CRM Opportunities pipeline.
        
        Returns a dictionary with push status.
        """
        try:
            # Get property data
            from ...db.models.property import Property
            property_data = self.db.query(Property).filter_by(id=property_id).first()
            
            if not property_data:
                return {"success": False, "error": "Property not found"}
            
            # Get developer data
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Push to CRM in background if background_tasks is provided
            if background_tasks:
                background_tasks.add_task(
                    self._push_to_zoho_crm,
                    property_data,
                    developer
                )
                
                return {
                    "success": True,
                    "status": "processing",
                    "message": "Listing push to CRM started in background"
                }
            else:
                # Push to CRM synchronously
                return await self._push_to_zoho_crm(
                    property_data,
                    developer
                )
        except Exception as e:
            print(f"Error pushing listing to CRM: {e}")
            return {"success": False, "error": str(e)}
    
    async def _push_to_zoho_crm(
        self,
        property_data: Any,
        developer: Any
    ) -> Dict[str, Any]:
        """
        Push property data to Zoho CRM Opportunities pipeline.
        
        Returns a dictionary with push status.
        """
        try:
            # Get access token
            await self._ensure_access_token()
            
            # Check if opportunity already exists
            existing_opportunity = await self._check_existing_opportunity(property_data.id)
            
            if existing_opportunity:
                # Update existing opportunity
                return await self._update_opportunity(
                    existing_opportunity["id"],
                    property_data,
                    developer
                )
            else:
                # Create new opportunity
                return await self._create_opportunity(
                    property_data,
                    developer
                )
        except Exception as e:
            print(f"Error in _push_to_zoho_crm: {e}")
            return {"success": False, "error": str(e)}
    
    async def _ensure_access_token(self) -> None:
        """
        Ensure a valid access token is available.
        
        Refreshes the token if expired.
        """
        current_time = time.time()
        
        # Check if token is expired or not set
        if not self.access_token or current_time >= self.token_expiry:
            # Refresh token
            token_url = f"{zoho_domain}/oauth/v2/token"
            payload = {
                "refresh_token": zoho_refresh_token,
                "client_id": zoho_client_id,
                "client_secret": zoho_client_secret,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expiry = current_time + token_data["expires_in"] - 300  # 5 minutes buffer
    
    async def _check_existing_opportunity(self, property_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if an opportunity already exists for the property.
        
        Returns the opportunity data if found, None otherwise.
        """
        try:
            # Search for opportunity by property ID
            search_url = "https://www.zohoapis.eu/crm/v2/Opportunities/search"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "criteria": f"(Property_ID:equals:{property_id})"
            }
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data") and len(data["data"]) > 0:
                    return data["data"][0]
            
            return None
        except Exception as e:
            print(f"Error checking existing opportunity: {e}")
            return None
    
    async def _create_opportunity(
        self,
        property_data: Any,
        developer: Any
    ) -> Dict[str, Any]:
        """
        Create a new opportunity in Zoho CRM.
        
        Returns a dictionary with creation status.
        """
        try:
            # Determine sales squad based on tower location
            sales_squad = self._determine_sales_squad(property_data)
            
            # Create opportunity data
            opportunity_data = {
                "data": [
                    {
                        "Deal_Name": f"{developer.legal_name} - {property_data.unit_no}",
                        "Stage": "Fresh Stock",
                        "Property_ID": property_data.id,
                        "Unit_No": property_data.unit_no,
                        "Tower": property_data.tower,
                        "Floor": property_data.floor,
                        "Unit_Type": property_data.unit_type,
                        "Bedrooms": property_data.bedrooms,
                        "Size_ft2": property_data.size_ft2,
                        "Price_AED": property_data.price,
                        "View": property_data.view,
                        "Developer": developer.legal_name,
                        "Developer_ID": developer.id,
                        "Sales_Squad": sales_squad,
                        "Amount": property_data.price,  # Set opportunity amount to property price
                        "Closing_Date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")  # 30 days from now
                    }
                ]
            }
            
            # Create opportunity
            create_url = "https://www.zohoapis.eu/crm/v2/Opportunities"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(create_url, headers=headers, json=opportunity_data)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("data") and len(result["data"]) > 0 and result["data"][0].get("status") == "success":
                # Save CRM ID to database
                opportunity_id = result["data"][0]["details"]["id"]
                
                # Update property with CRM ID
                property_data.zoho_opportunity_id = opportunity_id
                self.db.commit()
                
                # Assign to sales squad
                await self._assign_to_sales_squad(opportunity_id, sales_squad)
                
                return {
                    "success": True,
                    "message": "Opportunity created successfully",
                    "opportunity_id": opportunity_id
                }
            else:
                return {"success": False, "error": "Failed to create opportunity", "details": result}
        except Exception as e:
            print(f"Error creating opportunity: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_opportunity(
        self,
        opportunity_id: str,
        property_data: Any,
        developer: Any
    ) -> Dict[str, Any]:
        """
        Update an existing opportunity in Zoho CRM.
        
        Returns a dictionary with update status.
        """
        try:
            # Determine sales squad based on tower location
            sales_squad = self._determine_sales_squad(property_data)
            
            # Create opportunity data
            opportunity_data = {
                "data": [
                    {
                        "id": opportunity_id,
                        "Deal_Name": f"{developer.legal_name} - {property_data.unit_no}",
                        "Unit_No": property_data.unit_no,
                        "Tower": property_data.tower,
                        "Floor": property_data.floor,
                        "Unit_Type": property_data.unit_type,
                        "Bedrooms": property_data.bedrooms,
                        "Size_ft2": property_data.size_ft2,
                        "Price_AED": property_data.price,
                        "View": property_data.view,
                        "Sales_Squad": sales_squad,
                        "Amount": property_data.price  # Update opportunity amount to property price
                    }
                ]
            }
            
            # Update opportunity
            update_url = "https://www.zohoapis.eu/crm/v2/Opportunities"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.put(update_url, headers=headers, json=opportunity_data)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("data") and len(result["data"]) > 0 and result["data"][0].get("status") == "success":
                # Update property with CRM ID if not already set
                if not property_data.zoho_opportunity_id:
                    property_data.zoho_opportunity_id = opportunity_id
                    self.db.commit()
                
                # Assign to sales squad if changed
                await self._assign_to_sales_squad(opportunity_id, sales_squad)
                
                return {
                    "success": True,
                    "message": "Opportunity updated successfully",
                    "opportunity_id": opportunity_id
                }
            else:
                return {"success": False, "error": "Failed to update opportunity", "details": result}
        except Exception as e:
            print(f"Error updating opportunity: {e}")
            return {"success": False, "error": str(e)}
    
    def _determine_sales_squad(self, property_data: Any) -> str:
        """
        Determine the sales squad based on tower location.
        
        Returns the name of the sales squad.
        """
        # In a real implementation, this would be based on actual business logic
        # For this example, we'll use a simple mapping based on tower name
        
        # Extract location from tower name if available
        tower = property_data.tower or ""
        tower_lower = tower.lower()
        
        if "marina" in tower_lower or "jbr" in tower_lower or "dubai marina" in tower_lower:
            return "Marina Squad"
        elif "palm" in tower_lower or "jumeirah" in tower_lower:
            return "Palm Squad"
        elif "downtown" in tower_lower or "burj" in tower_lower:
            return "Downtown Squad"
        elif "hills" in tower_lower or "springs" in tower_lower or "meadows" in tower_lower:
            return "Emirates Hills Squad"
        elif "creek" in tower_lower or "festival" in tower_lower:
            return "Creek Squad"
        elif "marjan" in tower_lower or "rak" in tower_lower or "ras al khaimah" in tower_lower:
            return "RAK Squad"
        else:
            # Default squad
            return "General Squad"
    
    async def _assign_to_sales_squad(self, opportunity_id: str, sales_squad: str) -> Dict[str, Any]:
        """
        Assign an opportunity to a sales squad.
        
        Returns a dictionary with assignment status.
        """
        try:
            # In a real implementation, this would involve:
            # 1. Looking up the sales squad in Zoho CRM
            # 2. Finding available sales reps in that squad
            # 3. Assigning the opportunity to a specific rep
            
            # For this example, we'll simulate the assignment
            print(f"Assigning opportunity {opportunity_id} to {sales_squad}")
            
            # This would be a real API call in production
            return {
                "success": True,
                "message": f"Opportunity assigned to {sales_squad}",
                "opportunity_id": opportunity_id,
                "sales_squad": sales_squad
            }
        except Exception as e:
            print(f"Error assigning to sales squad: {e}")
            return {"success": False, "error": str(e)}
    
    async def sync_opportunity_status(self, opportunity_id: str) -> Dict[str, Any]:
        """
        Sync opportunity status from Zoho CRM to PropPulse.
        
        Returns a dictionary with sync status.
        """
        try:
            # Get access token
            await self._ensure_access_token()
            
            # Get opportunity from Zoho CRM
            get_url = f"https://www.zohoapis.eu/crm/v2/Opportunities/{opportunity_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(get_url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("data") and len(result["data"]) > 0:
                opportunity = result["data"][0]
                
                # Get property by Zoho opportunity ID
                from ...db.models.property import Property
                property_data = self.db.query(Property).filter_by(
                    zoho_opportunity_id=opportunity_id
                ).first()
                
                if not property_data:
                    return {"success": False, "error": "Property not found for opportunity ID"}
                
                # Update property status based on opportunity stage
                stage = opportunity.get("Stage")
                
                if stage == "Closed Won":
                    property_data.status = "Sold"
                elif stage == "Negotiation":
                    property_data.status = "Booked"
                elif stage == "Fresh Stock":
                    property_data.status = "Available"
                
                # Save changes
                self.db.commit()
                
                return {
                    "success": True,
                    "message": "Opportunity status synced successfully",
                    "opportunity_id": opportunity_id,
                    "stage": stage,
                    "property_status": property_data.status
                }
            else:
                return {"success": False, "error": "Opportunity not found", "details": result}
        except Exception as e:
            print(f"Error syncing opportunity status: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_zoho_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle webhook notifications from Zoho CRM.
        
        Returns a dictionary with handling status.
        """
        try:
            # Process webhook data
            module = webhook_data.get("module")
            
            if module != "Opportunities":
                return {"success": False, "error": f"Unsupported module: {module}"}
            
            # Get opportunity data
            opportunity = webhook_data.get("data", {})
            opportunity_id = opportunity.get("id")
            
            if not opportunity_id:
                return {"success": False, "error": "Missing opportunity ID"}
            
            # Sync opportunity status
            sync_result = await self.sync_opportunity_status(opportunity_id)
            
            return {
                "success": sync_result["success"],
                "message": "Webhook processed successfully",
                "sync_result": sync_result
            }
        except Exception as e:
            print(f"Error handling Zoho webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def bulk_sync_opportunities(
        self, 
        developer_id: Optional[str] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Bulk sync opportunities between Zoho CRM and PropPulse.
        
        Returns a dictionary with sync status.
        """
        try:
            # Get properties to sync
            from ...db.models.property import Property
            query = self.db.query(Property)
            
            if developer_id:
                query = query.filter_by(developer_id=developer_id)
            
            properties = query.all()
            
            # Sync in background if background_tasks is provided
            if background_tasks:
                background_tasks.add_task(
                    self._bulk_sync_opportunities,
                    properties
                )
                
                return {
                    "success": True,
                    "status": "processing",
                    "message": f"Bulk sync started for {len(properties)} properties",
                    "property_count": len(properties)
                }
            else:
                # Sync synchronously
                return await self._bulk_sync_opportunities(properties)
        except Exception as e:
            print(f"Error starting bulk sync: {e}")
            return {"success": False, "error": str(e)}
    
    async def _bulk_sync_opportunities(self, properties: List[Any]) -> Dict[str, Any]:
        """
        Perform bulk sync of opportunities.
        
        Returns a dictionary with sync status.
        """
        try:
            results = {
                "success": True,
                "total": len(properties),
                "created": 0,
                "updated": 0,
                "failed": 0,
                "skipped": 0,
                "failures": []
            }
            
            for property_data in properties:
                try:
                    # Get developer
                    from ...db.models.developer import Developer
                    developer = self.db.query(Developer).filter_by(id=property_data.developer_id).first()
                    
                    if not developer:
                        results["skipped"] += 1
                        continue
                    
                    # Check if property has Zoho opportunity ID
                    if property_data.zoho_opportunity_id:
                        # Update existing opportunity
                        update_result = await self._update_opportunity(
                            property_data.zoho_opportunity_id,
                            property_data,
                            developer
                        )
                        
                        if update_result["success"]:
                            results["updated"] += 1
                        else:
                            results["failed"] += 1
                            results["failures"].append({
                                "property_id": property_data.id,
                                "error": update_result.get("error", "Unknown error")
                            })
                    else:
                        # Create new opportunity
                        create_result = await self._create_opportunity(
                            property_data,
                            developer
                        )
                        
                        if create_result["success"]:
                            results["created"] += 1
                        else:
                            results["failed"] += 1
                            results["failures"].append({
                                "property_id": property_data.id,
                                "error": create_result.get("error", "Unknown error")
                            })
                except Exception as property_error:
                    results["failed"] += 1
                    results["failures"].append({
                        "property_id": property_data.id,
                        "error": str(property_error)
                    })
            
            return results
        except Exception as e:
            print(f"Error in bulk sync: {e}")
            return {"success": False, "error": str(e)}
