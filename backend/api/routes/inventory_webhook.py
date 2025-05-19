"""
Live sync webhook for developer inventory updates.

This module provides:
1. Webhook endpoint for real-time inventory updates
2. Signature validation for secure updates
3. Database upsert operations for property data
4. Pinecone embedding refresh triggers
"""

import os
import json
import hmac
import hashlib
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from ...db.models.developer import Developer
from ...db.models.property import Property
from ...utils.database import get_db
from ...integrations.pinecone.pinecone_metadata_updater import update_property_metadata

# Initialize router
router = APIRouter(prefix="/api/webhook/dev", tags=["developer"])

# Get webhook secret from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

# Helper functions
def validate_signature(payload: bytes, signature: str, developer_id: str, db: Session) -> bool:
    """
    Validate webhook signature using HMAC-SHA256.
    
    Returns True if signature is valid, False otherwise.
    """
    try:
        # Get developer
        developer = db.query(Developer).filter_by(id=developer_id).first()
        
        if not developer:
            print(f"Developer not found: {developer_id}")
            return False
        
        # Get webhook secret for this developer
        # In production, this would be stored in the database or Key Vault
        # For this example, we'll generate a deterministic secret based on the developer ID
        webhook_secret = hashlib.sha256(f"proppulse-webhook-{developer_id}".encode()).hexdigest()
        
        # Compute expected signature
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison to prevent timing attacks)
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        print(f"Error validating signature: {e}")
        return False

async def process_inventory_update(
    developer_id: str,
    inventory_data: Dict[str, Any],
    db: Session,
    background_tasks: BackgroundTasks
):
    """
    Process inventory update from webhook.
    
    Updates database and triggers Pinecone embedding refresh.
    """
    try:
        # Get developer
        developer = db.query(Developer).filter_by(id=developer_id).first()
        
        if not developer:
            print(f"Developer not found: {developer_id}")
            return {"success": False, "error": "Developer not found"}
        
        # Process properties
        properties = inventory_data.get("properties", [])
        updated_properties = []
        
        for prop_data in properties:
            # Check if property exists
            property_id = prop_data.get("property_id")
            unit_no = prop_data.get("unit_no")
            
            if not property_id and not unit_no:
                print("Missing property_id or unit_no")
                continue
            
            # Find property by ID or unit number
            property_query = db.query(Property)
            
            if property_id:
                property_query = property_query.filter_by(id=property_id)
            else:
                # Find by unit_no and developer_id
                property_query = property_query.filter_by(
                    unit_no=unit_no,
                    developer_id=developer_id
                )
            
            existing_property = property_query.first()
            
            if existing_property:
                # Update existing property
                for key, value in prop_data.items():
                    if key != "property_id" and hasattr(existing_property, key):
                        setattr(existing_property, key, value)
                
                # Track changes
                if "price" in prop_data:
                    # Calculate price change percentage
                    old_price = existing_property.price or 0
                    new_price = prop_data["price"]
                    
                    if old_price > 0:
                        price_change_pct = (new_price - old_price) / old_price * 100
                        existing_property.price_change_pct = price_change_pct
                
                updated_properties.append(existing_property.id)
            else:
                # Create new property
                new_property = Property(
                    developer_id=developer_id,
                    **{k: v for k, v in prop_data.items() if k != "property_id"}
                )
                db.add(new_property)
                db.flush()  # Get ID without committing
                updated_properties.append(new_property.id)
        
        # Commit changes
        db.commit()
        
        # Trigger Pinecone embedding refresh for updated properties
        for property_id in updated_properties:
            background_tasks.add_task(update_property_metadata, property_id, db)
        
        # Update developer's active units count
        from ...db.models.pricing import DeveloperPlan
        developer_plan = db.query(DeveloperPlan).filter_by(developer_id=developer_id).first()
        
        if developer_plan:
            # Count active units (status = "Available")
            active_units_count = db.query(Property).filter_by(
                developer_id=developer_id,
                status="Available"
            ).count()
            
            developer_plan.current_active_units = active_units_count
            db.commit()
        
        return {
            "success": True,
            "updated_count": len(updated_properties),
            "updated_properties": updated_properties
        }
    except Exception as e:
        db.rollback()
        print(f"Error processing inventory update: {e}")
        return {"success": False, "error": str(e)}

# Webhook endpoint
@router.post("/{developer_id}/inventory")
async def inventory_webhook(
    developer_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for real-time inventory updates.
    
    Expects a JSON payload with property data and a signature header.
    """
    # Get request body
    payload = await request.body()
    signature = request.headers.get("X-PropPulse-Signature")
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    # Validate signature
    if not validate_signature(payload, signature, developer_id, db):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        # Parse payload
        inventory_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Process inventory update
    result = await process_inventory_update(developer_id, inventory_data, db, background_tasks)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    # Return success response
    return JSONResponse(content=result)

# Webhook test endpoint
@router.get("/{developer_id}/test")
async def test_webhook(
    developer_id: str,
    db: Session = Depends(get_db)
):
    """
    Test endpoint to generate a webhook signature for testing.
    
    Returns a sample payload and signature for testing the webhook.
    """
    # Get developer
    developer = db.query(Developer).filter_by(id=developer_id).first()
    
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Generate sample payload
    sample_payload = {
        "properties": [
            {
                "unit_no": "TEST-101",
                "tower": "Test Tower",
                "floor": 1,
                "unit_type": "1BR",
                "bedrooms": 1,
                "bathrooms": 1,
                "size_ft2": 750,
                "price": 500000,
                "view": "City",
                "status": "Available"
            }
        ]
    }
    
    # Convert to JSON
    payload_bytes = json.dumps(sample_payload).encode()
    
    # Generate webhook secret
    webhook_secret = hashlib.sha256(f"proppulse-webhook-{developer_id}".encode()).hexdigest()
    
    # Generate signature
    signature = hmac.new(
        webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Return sample payload and signature
    return {
        "developer_id": developer_id,
        "webhook_url": f"/api/webhook/dev/{developer_id}/inventory",
        "payload": sample_payload,
        "signature": signature,
        "header_name": "X-PropPulse-Signature"
    }

# Bulk import endpoint
@router.post("/{developer_id}/bulk-import")
async def bulk_import(
    developer_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Bulk import endpoint for large inventory updates.
    
    Similar to the webhook but optimized for larger payloads.
    """
    # Get request body
    payload = await request.body()
    signature = request.headers.get("X-PropPulse-Signature")
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    # Validate signature
    if not validate_signature(payload, signature, developer_id, db):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        # Parse payload
        inventory_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Check payload size
    properties = inventory_data.get("properties", [])
    if len(properties) > 1000:
        raise HTTPException(status_code=400, detail="Payload too large. Maximum 1000 properties per request.")
    
    # Process inventory update
    result = await process_inventory_update(developer_id, inventory_data, db, background_tasks)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    # Return success response
    return JSONResponse(content=result)

# Webhook documentation endpoint
@router.get("/docs")
async def webhook_docs():
    """
    Documentation for the inventory webhook.
    
    Returns information about the webhook format and usage.
    """
    return {
        "webhook_format": {
            "url": "/api/webhook/dev/{developer_id}/inventory",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "X-PropPulse-Signature": "HMAC-SHA256 signature of the payload"
            },
            "payload": {
                "properties": [
                    {
                        "property_id": "Optional. If provided, updates existing property.",
                        "unit_no": "Required if property_id not provided.",
                        "tower": "Optional",
                        "floor": "Optional",
                        "unit_type": "Optional",
                        "bedrooms": "Optional",
                        "bathrooms": "Optional",
                        "size_ft2": "Optional",
                        "price": "Optional",
                        "view": "Optional",
                        "status": "Optional"
                    }
                ]
            }
        },
        "signature_generation": "HMAC-SHA256(webhook_secret, JSON.stringify(payload))",
        "testing": "Use the /api/webhook/dev/{developer_id}/test endpoint to generate a test signature."
    }
