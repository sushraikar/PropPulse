"""
Database upsert and validation utilities for inventory data.

This module provides:
1. Functions for validating and upserting property data
2. Signature validation for secure webhook requests
3. Database transaction management for inventory updates
4. Pinecone embedding refresh triggers
"""

import os
import json
import hmac
import hashlib
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import BackgroundTasks

from ...db.models.developer import Developer
from ...db.models.property import Property
from ...integrations.pinecone.pinecone_metadata_updater import update_property_metadata

# Constants
MAX_PROPERTIES_PER_REQUEST = 1000
REQUIRED_PROPERTY_FIELDS = ["unit_no"]
OPTIONAL_PROPERTY_FIELDS = [
    "tower", "floor", "unit_type", "bedrooms", "bathrooms", 
    "size_ft2", "price", "view", "status", "completion_date",
    "payment_plan", "description", "features", "latitude", "longitude"
]

def generate_webhook_secret(developer_id: str) -> str:
    """
    Generate a deterministic webhook secret for a developer.
    
    In production, this would be a randomly generated secret stored in the database or Key Vault.
    """
    return hashlib.sha256(f"proppulse-webhook-{developer_id}".encode()).hexdigest()

def validate_webhook_signature(payload: bytes, signature: str, developer_id: str) -> bool:
    """
    Validate webhook signature using HMAC-SHA256.
    
    Returns True if signature is valid, False otherwise.
    """
    try:
        # Get webhook secret for this developer
        webhook_secret = generate_webhook_secret(developer_id)
        
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

def validate_property_data(property_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate property data for required fields and data types.
    
    Returns a tuple of (is_valid, error_message).
    """
    # Check for required fields if property_id is not provided
    if "property_id" not in property_data:
        for field in REQUIRED_PROPERTY_FIELDS:
            if field not in property_data or not property_data[field]:
                return False, f"Missing required field: {field}"
    
    # Validate data types
    type_validators = {
        "bedrooms": lambda x: isinstance(x, int),
        "bathrooms": lambda x: isinstance(x, int) or isinstance(x, float),
        "floor": lambda x: isinstance(x, int),
        "size_ft2": lambda x: isinstance(x, int) or isinstance(x, float),
        "price": lambda x: isinstance(x, int) or isinstance(x, float),
        "latitude": lambda x: isinstance(x, float),
        "longitude": lambda x: isinstance(x, float),
    }
    
    for field, validator in type_validators.items():
        if field in property_data and property_data[field] is not None:
            if not validator(property_data[field]):
                return False, f"Invalid data type for field: {field}"
    
    # Validate status values
    if "status" in property_data and property_data["status"] not in ["Available", "Booked", "Sold"]:
        return False, f"Invalid status value: {property_data['status']}"
    
    return True, None

def upsert_property(
    property_data: Dict[str, Any], 
    developer_id: str, 
    db: Session
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Upsert a property in the database.
    
    Returns a tuple of (success, error_message, property_id).
    """
    try:
        # Validate property data
        is_valid, error_message = validate_property_data(property_data)
        if not is_valid:
            return False, error_message, None
        
        # Check if property exists
        property_id = property_data.get("property_id")
        unit_no = property_data.get("unit_no")
        
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
            for key, value in property_data.items():
                if key != "property_id" and hasattr(existing_property, key):
                    setattr(existing_property, key, value)
            
            # Track price changes
            if "price" in property_data:
                # Calculate price change percentage
                old_price = existing_property.price or 0
                new_price = property_data["price"]
                
                if old_price > 0:
                    price_change_pct = (new_price - old_price) / old_price * 100
                    existing_property.price_change_pct = price_change_pct
            
            # Update last_updated timestamp
            existing_property.last_updated = time.time()
            
            return True, None, existing_property.id
        else:
            # Create new property
            new_property = Property(
                developer_id=developer_id,
                **{k: v for k, v in property_data.items() if k != "property_id"}
            )
            db.add(new_property)
            db.flush()  # Get ID without committing
            
            return True, None, new_property.id
    except SQLAlchemyError as e:
        return False, f"Database error: {str(e)}", None
    except Exception as e:
        return False, f"Error upserting property: {str(e)}", None

def process_inventory_update(
    developer_id: str,
    inventory_data: Dict[str, Any],
    db: Session,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Process inventory update from webhook.
    
    Updates database and triggers Pinecone embedding refresh.
    """
    try:
        # Get developer
        developer = db.query(Developer).filter_by(id=developer_id).first()
        
        if not developer:
            return {"success": False, "error": "Developer not found"}
        
        # Process properties
        properties = inventory_data.get("properties", [])
        
        # Validate payload size
        if len(properties) > MAX_PROPERTIES_PER_REQUEST:
            return {
                "success": False, 
                "error": f"Payload too large. Maximum {MAX_PROPERTIES_PER_REQUEST} properties per request."
            }
        
        updated_properties = []
        errors = []
        
        # Begin transaction
        for prop_data in properties:
            # Upsert property
            success, error_message, property_id = upsert_property(prop_data, developer_id, db)
            
            if success:
                updated_properties.append(property_id)
            else:
                errors.append({
                    "property_data": prop_data,
                    "error": error_message
                })
        
        # If there were any errors, rollback and return
        if errors:
            db.rollback()
            return {
                "success": False,
                "error": "One or more properties failed validation",
                "errors": errors
            }
        
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
        return {"success": False, "error": str(e)}

def generate_test_signature(developer_id: str, payload: Dict[str, Any]) -> str:
    """
    Generate a test signature for webhook testing.
    
    Returns the HMAC-SHA256 signature of the payload.
    """
    # Generate webhook secret
    webhook_secret = generate_webhook_secret(developer_id)
    
    # Convert payload to JSON bytes
    payload_bytes = json.dumps(payload).encode()
    
    # Generate signature
    signature = hmac.new(
        webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    return signature

def get_property_changes(old_property: Property, new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get changes between existing property and new data.
    
    Returns a dictionary of changed fields with old and new values.
    """
    changes = {}
    
    for key, new_value in new_data.items():
        if key != "property_id" and hasattr(old_property, key):
            old_value = getattr(old_property, key)
            
            # Check if value has changed
            if old_value != new_value:
                changes[key] = {
                    "old": old_value,
                    "new": new_value
                }
    
    return changes

def check_significant_price_change(old_price: float, new_price: float, threshold_pct: float = 2.0) -> bool:
    """
    Check if price change is significant (>= threshold_pct).
    
    Returns True if change is significant, False otherwise.
    """
    if old_price <= 0:
        return True
    
    change_pct = abs((new_price - old_price) / old_price * 100)
    return change_pct >= threshold_pct
