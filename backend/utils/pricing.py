"""
Pricing plan models and utilities for PropPulse developer portal.

This module provides:
1. Database models for developer plans and subscriptions
2. Utilities for plan management and overage calculation
3. Integration with Stripe for billing
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Get Stripe API key from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
stripe_api_key = secret_client.get_secret("STRIPE-TEST-SECRET-KEY").value

# Initialize Stripe
import stripe
stripe.api_key = stripe_api_key

# Base class for SQLAlchemy models
Base = declarative_base()

# Plan types enum
class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    UNLIMITED = "unlimited"

# Plan definitions
PLAN_DEFINITIONS = {
    PlanType.FREE: {
        "name": "Free",
        "price_monthly": 0,
        "project_limit": 1,
        "active_unit_cap": 10,
        "ai_asset_credits": 0,
        "includes_liquidity": False,
        "stripe_price_id": None,  # Free plan has no Stripe price
    },
    PlanType.PRO: {
        "name": "Pro",
        "price_monthly": 99,
        "project_limit": 5,
        "active_unit_cap": 500,
        "ai_asset_credits": 5,
        "includes_liquidity": False,
        "stripe_price_id": "price_1234567890",  # Replace with actual Stripe price ID
    },
    PlanType.UNLIMITED: {
        "name": "Unlimited",
        "price_monthly": 299,
        "project_limit": float('inf'),  # Unlimited
        "active_unit_cap": float('inf'),  # Unlimited
        "ai_asset_credits": 25,
        "includes_liquidity": True,
        "stripe_price_id": "price_0987654321",  # Replace with actual Stripe price ID
    }
}

# Overage rate per active unit
OVERAGE_RATE = 0.15  # $0.15 per active unit above cap

# Trial period in days
TRIAL_PERIOD_DAYS = 14

# Database models
class DeveloperPlan(Base):
    """Model for developer subscription plans."""
    __tablename__ = "developer_plans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    developer_id = Column(String(36), nullable=False, index=True)
    plan_type = Column(String(20), nullable=False, default=PlanType.FREE)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    trial_ends_at = Column(DateTime, nullable=True)
    current_period_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Plan limits and features
    project_limit = Column(Integer, nullable=False, default=1)
    active_unit_cap = Column(Integer, nullable=False, default=10)
    ai_asset_credits = Column(Integer, nullable=False, default=0)
    includes_liquidity = Column(Boolean, default=False)
    
    # Usage tracking
    current_projects_count = Column(Integer, nullable=False, default=0)
    current_active_units = Column(Integer, nullable=False, default=0)
    ai_credits_used = Column(Integer, nullable=False, default=0)
    
    # Billing history
    billing_history = relationship("BillingRecord", back_populates="plan")

class BillingRecord(Base):
    """Model for billing records."""
    __tablename__ = "billing_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("developer_plans.id"), nullable=False)
    invoice_id = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    description = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False)
    billing_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Detailed breakdown
    base_plan_amount = Column(Float, nullable=False)
    overage_amount = Column(Float, nullable=False, default=0)
    overage_units = Column(Integer, nullable=False, default=0)
    
    # Relationship
    plan = relationship("DeveloperPlan", back_populates="billing_history")
    
    # Metadata
    metadata = Column(JSON, nullable=True)

class AIAssetCredit(Base):
    """Model for tracking AI asset credit usage."""
    __tablename__ = "ai_asset_credits"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    developer_id = Column(String(36), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("developer_plans.id"), nullable=False)
    asset_id = Column(String(36), nullable=True)
    asset_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # For regenerations
    is_regeneration = Column(Boolean, default=False)
    original_asset_id = Column(String(36), nullable=True)
    regeneration_count = Column(Integer, nullable=False, default=0)
    
    # Cost
    credit_cost = Column(Integer, nullable=False, default=1)
    paid_amount = Column(Float, nullable=True)  # If paid separately

# Helper functions
def create_stripe_customer(developer_id: str, email: str, name: str) -> str:
    """
    Create a new Stripe customer for a developer.
    
    Returns the Stripe customer ID.
    """
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                "developer_id": developer_id
            }
        )
        return customer.id
    except Exception as e:
        print(f"Error creating Stripe customer: {e}")
        raise

def create_stripe_subscription(
    customer_id: str, 
    plan_type: PlanType,
    trial_period_days: int = TRIAL_PERIOD_DAYS
) -> Dict[str, Any]:
    """
    Create a new Stripe subscription for a customer.
    
    Returns the subscription details.
    """
    try:
        # Get plan details
        plan = PLAN_DEFINITIONS[plan_type]
        
        # Skip for free plan
        if plan_type == PlanType.FREE:
            return {
                "id": None,
                "status": "active",
                "current_period_start": datetime.utcnow(),
                "current_period_end": None,
                "trial_end": None
            }
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[
                {"price": plan["stripe_price_id"]},
            ],
            trial_period_days=trial_period_days if plan_type != PlanType.FREE else 0,
            metadata={
                "plan_type": plan_type
            }
        )
        
        # Return subscription details
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start),
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end),
            "trial_end": datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None
        }
    except Exception as e:
        print(f"Error creating Stripe subscription: {e}")
        raise

def cancel_stripe_subscription(subscription_id: str) -> bool:
    """
    Cancel a Stripe subscription.
    
    Returns True if successful, False otherwise.
    """
    try:
        # Skip for free plan
        if not subscription_id:
            return True
        
        # Cancel subscription
        stripe.Subscription.delete(subscription_id)
        return True
    except Exception as e:
        print(f"Error cancelling Stripe subscription: {e}")
        return False

def create_checkout_session(
    customer_id: str,
    plan_type: PlanType,
    success_url: str,
    cancel_url: str
) -> str:
    """
    Create a Stripe Checkout session for a plan upgrade.
    
    Returns the checkout session URL.
    """
    try:
        # Get plan details
        plan = PLAN_DEFINITIONS[plan_type]
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan["stripe_price_id"],
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "trial_period_days": TRIAL_PERIOD_DAYS,
                "metadata": {
                    "plan_type": plan_type
                }
            }
        )
        
        return checkout_session.url
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        raise

def calculate_overage(active_units: int, plan_type: PlanType) -> Dict[str, Any]:
    """
    Calculate overage charges for active units.
    
    Returns a dictionary with overage details.
    """
    # Get plan details
    plan = PLAN_DEFINITIONS[plan_type]
    
    # Calculate overage
    if active_units <= plan["active_unit_cap"]:
        return {
            "has_overage": False,
            "overage_units": 0,
            "overage_amount": 0
        }
    
    # Calculate overage
    overage_units = active_units - plan["active_unit_cap"]
    overage_amount = overage_units * OVERAGE_RATE
    
    return {
        "has_overage": True,
        "overage_units": overage_units,
        "overage_amount": overage_amount
    }

def is_unit_active(last_listed_date: datetime) -> bool:
    """
    Determine if a unit is considered active for billing purposes.
    
    A unit is active if it has been listed for at least 24 hours during the current billing cycle.
    """
    now = datetime.utcnow()
    return (now - last_listed_date).total_seconds() >= 24 * 60 * 60

def get_plan_details(plan_type: PlanType) -> Dict[str, Any]:
    """
    Get details for a specific plan type.
    
    Returns a dictionary with plan details.
    """
    return PLAN_DEFINITIONS[plan_type]

def handle_subscription_updated(subscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a subscription updated event from Stripe.
    
    Returns updated subscription details.
    """
    # Extract relevant data
    subscription_id = subscription_data.get("id")
    status = subscription_data.get("status")
    current_period_start = datetime.fromtimestamp(subscription_data.get("current_period_start"))
    current_period_end = datetime.fromtimestamp(subscription_data.get("current_period_end"))
    trial_end = datetime.fromtimestamp(subscription_data.get("trial_end")) if subscription_data.get("trial_end") else None
    
    # Get plan type from metadata
    metadata = subscription_data.get("metadata", {})
    plan_type = metadata.get("plan_type", PlanType.FREE)
    
    return {
        "subscription_id": subscription_id,
        "status": status,
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "trial_end": trial_end,
        "plan_type": plan_type
    }

def handle_invoice_paid(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle an invoice paid event from Stripe.
    
    Returns billing record details.
    """
    # Extract relevant data
    invoice_id = invoice_data.get("id")
    amount = invoice_data.get("amount_paid") / 100  # Convert from cents
    currency = invoice_data.get("currency").upper()
    description = invoice_data.get("description")
    status = invoice_data.get("status")
    
    # Get subscription ID
    subscription_id = invoice_data.get("subscription")
    
    # Get line items for detailed breakdown
    line_items = invoice_data.get("lines", {}).get("data", [])
    
    # Calculate base amount and overage
    base_amount = 0
    overage_amount = 0
    overage_units = 0
    
    for item in line_items:
        if item.get("description", "").lower().startswith("overage"):
            overage_amount += item.get("amount") / 100
            # Extract overage units from description
            description = item.get("description", "")
            try:
                overage_units = int(description.split("units")[0].strip().split(" ")[-1])
            except:
                pass
        else:
            base_amount += item.get("amount") / 100
    
    return {
        "invoice_id": invoice_id,
        "amount": amount,
        "currency": currency,
        "description": description,
        "status": status,
        "subscription_id": subscription_id,
        "base_amount": base_amount,
        "overage_amount": overage_amount,
        "overage_units": overage_units
    }

def create_ai_asset_credit_usage(
    developer_id: str,
    plan_id: str,
    asset_type: str,
    is_regeneration: bool = False,
    original_asset_id: str = None,
    regeneration_count: int = 0
) -> Dict[str, Any]:
    """
    Record usage of an AI asset credit.
    
    Returns credit usage details.
    """
    # Generate asset ID
    asset_id = str(uuid.uuid4())
    
    # Determine credit cost
    credit_cost = 1
    paid_amount = None
    
    # Regenerations beyond the limit (3) cost $5 each
    if is_regeneration and regeneration_count > 3:
        credit_cost = 0  # Don't use credits
        paid_amount = 5.0  # $5 per regeneration
    
    # Create credit usage record
    credit_usage = {
        "id": str(uuid.uuid4()),
        "developer_id": developer_id,
        "plan_id": plan_id,
        "asset_id": asset_id,
        "asset_type": asset_type,
        "created_at": datetime.utcnow(),
        "is_regeneration": is_regeneration,
        "original_asset_id": original_asset_id,
        "regeneration_count": regeneration_count,
        "credit_cost": credit_cost,
        "paid_amount": paid_amount
    }
    
    return credit_usage

def check_ai_credit_availability(developer_id: str, plan_id: str) -> Dict[str, Any]:
    """
    Check if a developer has AI asset credits available.
    
    Returns availability details.
    """
    # In a real implementation, query the database
    # For this example, we'll return a mock response
    return {
        "has_credits": True,
        "credits_remaining": 5,
        "total_credits": 10,
        "can_purchase": True
    }

def purchase_additional_ai_credits(
    customer_id: str,
    quantity: int,
    success_url: str,
    cancel_url: str
) -> str:
    """
    Create a checkout session for purchasing additional AI credits.
    
    Returns the checkout session URL.
    """
    try:
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "AI Asset Credits",
                            "description": "Additional AI asset generation credits"
                        },
                        "unit_amount": 500,  # $5.00 per credit
                    },
                    "quantity": quantity,
                },
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "credit_purchase": "true",
                "quantity": quantity
            }
        )
        
        return checkout_session.url
    except Exception as e:
        print(f"Error creating checkout session for AI credits: {e}")
        raise
