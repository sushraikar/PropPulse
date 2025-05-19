"""
Stripe webhook handler for PropPulse developer portal.

This module provides:
1. Webhook endpoint for Stripe events
2. Handlers for subscription and invoice events
3. Database updates for developer plans
"""

import os
import json
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from ...db.models.developer import Developer
from ...utils.pricing import (
    PlanType, 
    handle_subscription_updated, 
    handle_invoice_paid,
    PLAN_DEFINITIONS
)
from ...utils.database import get_db
from ...utils.auth import get_current_user

# Initialize router
router = APIRouter(prefix="/api/dev/webhook", tags=["developer"])

# Get Stripe webhook secret from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
stripe_webhook_secret = secret_client.get_secret("STRIPE-WEBHOOK-SECRET").value

# Initialize Stripe
import stripe
stripe.api_key = secret_client.get_secret("STRIPE-TEST-SECRET-KEY").value

# Event handlers
async def handle_customer_subscription_created(event_data: Dict[str, Any], db: Session):
    """Handle customer.subscription.created event."""
    subscription_data = event_data.get("object", {})
    subscription_details = handle_subscription_updated(subscription_data)
    
    # Get customer ID
    customer_id = subscription_data.get("customer")
    
    # Find developer by Stripe customer ID
    developer = db.query(Developer).filter_by(stripe_customer_id=customer_id).first()
    
    if not developer:
        print(f"Developer not found for customer ID: {customer_id}")
        return
    
    # Get plan type
    plan_type = subscription_details.get("plan_type", PlanType.FREE)
    
    # Get plan details
    plan_details = PLAN_DEFINITIONS[plan_type]
    
    # Update or create developer plan
    from ...db.models.pricing import DeveloperPlan
    
    # Check if developer already has a plan
    existing_plan = db.query(DeveloperPlan).filter_by(developer_id=developer.id).first()
    
    if existing_plan:
        # Update existing plan
        existing_plan.plan_type = plan_type
        existing_plan.stripe_subscription_id = subscription_details.get("subscription_id")
        existing_plan.is_active = subscription_details.get("status") == "active"
        existing_plan.trial_ends_at = subscription_details.get("trial_end")
        existing_plan.current_period_start = subscription_details.get("current_period_start")
        existing_plan.current_period_end = subscription_details.get("current_period_end")
        
        # Update plan limits
        existing_plan.project_limit = plan_details.get("project_limit")
        existing_plan.active_unit_cap = plan_details.get("active_unit_cap")
        existing_plan.ai_asset_credits = plan_details.get("ai_asset_credits")
        existing_plan.includes_liquidity = plan_details.get("includes_liquidity")
    else:
        # Create new plan
        new_plan = DeveloperPlan(
            developer_id=developer.id,
            plan_type=plan_type,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_details.get("subscription_id"),
            is_active=subscription_details.get("status") == "active",
            trial_ends_at=subscription_details.get("trial_end"),
            current_period_start=subscription_details.get("current_period_start"),
            current_period_end=subscription_details.get("current_period_end"),
            project_limit=plan_details.get("project_limit"),
            active_unit_cap=plan_details.get("active_unit_cap"),
            ai_asset_credits=plan_details.get("ai_asset_credits"),
            includes_liquidity=plan_details.get("includes_liquidity")
        )
        db.add(new_plan)
    
    # Commit changes
    db.commit()

async def handle_customer_subscription_updated(event_data: Dict[str, Any], db: Session):
    """Handle customer.subscription.updated event."""
    subscription_data = event_data.get("object", {})
    subscription_details = handle_subscription_updated(subscription_data)
    
    # Get subscription ID
    subscription_id = subscription_data.get("id")
    
    # Find developer plan by subscription ID
    from ...db.models.pricing import DeveloperPlan
    developer_plan = db.query(DeveloperPlan).filter_by(stripe_subscription_id=subscription_id).first()
    
    if not developer_plan:
        print(f"Developer plan not found for subscription ID: {subscription_id}")
        return
    
    # Get plan type
    plan_type = subscription_details.get("plan_type", developer_plan.plan_type)
    
    # Get plan details
    plan_details = PLAN_DEFINITIONS[plan_type]
    
    # Update developer plan
    developer_plan.plan_type = plan_type
    developer_plan.is_active = subscription_details.get("status") == "active"
    developer_plan.trial_ends_at = subscription_details.get("trial_end")
    developer_plan.current_period_start = subscription_details.get("current_period_start")
    developer_plan.current_period_end = subscription_details.get("current_period_end")
    
    # Update plan limits
    developer_plan.project_limit = plan_details.get("project_limit")
    developer_plan.active_unit_cap = plan_details.get("active_unit_cap")
    developer_plan.ai_asset_credits = plan_details.get("ai_asset_credits")
    developer_plan.includes_liquidity = plan_details.get("includes_liquidity")
    
    # Commit changes
    db.commit()

async def handle_customer_subscription_deleted(event_data: Dict[str, Any], db: Session):
    """Handle customer.subscription.deleted event."""
    subscription_data = event_data.get("object", {})
    
    # Get subscription ID
    subscription_id = subscription_data.get("id")
    
    # Find developer plan by subscription ID
    from ...db.models.pricing import DeveloperPlan
    developer_plan = db.query(DeveloperPlan).filter_by(stripe_subscription_id=subscription_id).first()
    
    if not developer_plan:
        print(f"Developer plan not found for subscription ID: {subscription_id}")
        return
    
    # Update developer plan
    developer_plan.is_active = False
    developer_plan.plan_type = PlanType.FREE
    
    # Reset to free plan limits
    free_plan = PLAN_DEFINITIONS[PlanType.FREE]
    developer_plan.project_limit = free_plan.get("project_limit")
    developer_plan.active_unit_cap = free_plan.get("active_unit_cap")
    developer_plan.ai_asset_credits = free_plan.get("ai_asset_credits")
    developer_plan.includes_liquidity = free_plan.get("includes_liquidity")
    
    # Commit changes
    db.commit()

async def handle_invoice_paid_event(event_data: Dict[str, Any], db: Session):
    """Handle invoice.paid event."""
    invoice_data = event_data.get("object", {})
    billing_details = handle_invoice_paid(invoice_data)
    
    # Get subscription ID
    subscription_id = billing_details.get("subscription_id")
    
    if not subscription_id:
        print("No subscription ID found in invoice")
        return
    
    # Find developer plan by subscription ID
    from ...db.models.pricing import DeveloperPlan, BillingRecord
    developer_plan = db.query(DeveloperPlan).filter_by(stripe_subscription_id=subscription_id).first()
    
    if not developer_plan:
        print(f"Developer plan not found for subscription ID: {subscription_id}")
        return
    
    # Create billing record
    billing_record = BillingRecord(
        plan_id=developer_plan.id,
        invoice_id=billing_details.get("invoice_id"),
        amount=billing_details.get("amount"),
        currency=billing_details.get("currency"),
        description=billing_details.get("description"),
        status=billing_details.get("status"),
        base_plan_amount=billing_details.get("base_amount"),
        overage_amount=billing_details.get("overage_amount"),
        overage_units=billing_details.get("overage_units"),
        metadata=invoice_data
    )
    
    db.add(billing_record)
    
    # Reset AI credits if this is a new billing period
    if developer_plan.current_period_end and developer_plan.current_period_end < billing_details.get("current_period_start"):
        developer_plan.ai_credits_used = 0
    
    # Commit changes
    db.commit()

async def handle_checkout_session_completed(event_data: Dict[str, Any], db: Session):
    """Handle checkout.session.completed event."""
    session_data = event_data.get("object", {})
    
    # Check if this is a credit purchase
    metadata = session_data.get("metadata", {})
    is_credit_purchase = metadata.get("credit_purchase") == "true"
    
    if is_credit_purchase:
        # Handle credit purchase
        customer_id = session_data.get("customer")
        quantity = int(metadata.get("quantity", 0))
        
        # Find developer by Stripe customer ID
        developer = db.query(Developer).filter_by(stripe_customer_id=customer_id).first()
        
        if not developer:
            print(f"Developer not found for customer ID: {customer_id}")
            return
        
        # Find developer plan
        from ...db.models.pricing import DeveloperPlan
        developer_plan = db.query(DeveloperPlan).filter_by(developer_id=developer.id).first()
        
        if not developer_plan:
            print(f"Developer plan not found for developer ID: {developer.id}")
            return
        
        # Add credits
        developer_plan.ai_asset_credits += quantity
        
        # Commit changes
        db.commit()
    else:
        # Handle subscription checkout
        subscription_id = session_data.get("subscription")
        
        if not subscription_id:
            print("No subscription ID found in checkout session")
            return
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Process as subscription created/updated
        await handle_customer_subscription_created({"object": subscription}, db)

# Webhook endpoint
@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events."""
    # Get request body
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle event
    event_type = event.get("type")
    
    if event_type == "customer.subscription.created":
        background_tasks.add_task(handle_customer_subscription_created, event.data, db)
    elif event_type == "customer.subscription.updated":
        background_tasks.add_task(handle_customer_subscription_updated, event.data, db)
    elif event_type == "customer.subscription.deleted":
        background_tasks.add_task(handle_customer_subscription_deleted, event.data, db)
    elif event_type == "invoice.paid":
        background_tasks.add_task(handle_invoice_paid_event, event.data, db)
    elif event_type == "checkout.session.completed":
        background_tasks.add_task(handle_checkout_session_completed, event.data, db)
    
    # Return success response
    return JSONResponse(content={"status": "success"})

# Plan management endpoints
@router.get("/plans")
async def get_available_plans():
    """Get available plans."""
    plans = []
    
    for plan_type, details in PLAN_DEFINITIONS.items():
        plans.append({
            "type": plan_type,
            "name": details["name"],
            "price_monthly": details["price_monthly"],
            "project_limit": details["project_limit"],
            "active_unit_cap": details["active_unit_cap"],
            "ai_asset_credits": details["ai_asset_credits"],
            "includes_liquidity": details["includes_liquidity"],
        })
    
    return {"plans": plans}

@router.get("/current-plan")
async def get_current_plan(
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current plan for the authenticated developer."""
    # Find developer
    developer = db.query(Developer).filter_by(id=current_user["id"]).first()
    
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Find developer plan
    from ...db.models.pricing import DeveloperPlan
    developer_plan = db.query(DeveloperPlan).filter_by(developer_id=developer.id).first()
    
    if not developer_plan:
        # Create default free plan
        from ...utils.pricing import PlanType, PLAN_DEFINITIONS
        free_plan = PLAN_DEFINITIONS[PlanType.FREE]
        
        developer_plan = DeveloperPlan(
            developer_id=developer.id,
            plan_type=PlanType.FREE,
            is_active=True,
            project_limit=free_plan["project_limit"],
            active_unit_cap=free_plan["active_unit_cap"],
            ai_asset_credits=free_plan["ai_asset_credits"],
            includes_liquidity=free_plan["includes_liquidity"]
        )
        
        db.add(developer_plan)
        db.commit()
    
    # Get plan details
    plan_details = PLAN_DEFINITIONS[developer_plan.plan_type]
    
    # Return plan details
    return {
        "plan": {
            "type": developer_plan.plan_type,
            "name": plan_details["name"],
            "price_monthly": plan_details["price_monthly"],
            "is_active": developer_plan.is_active,
            "trial_ends_at": developer_plan.trial_ends_at,
            "current_period_start": developer_plan.current_period_start,
            "current_period_end": developer_plan.current_period_end,
            "project_limit": developer_plan.project_limit,
            "active_unit_cap": developer_plan.active_unit_cap,
            "ai_asset_credits": developer_plan.ai_asset_credits,
            "includes_liquidity": developer_plan.includes_liquidity,
            "current_projects_count": developer_plan.current_projects_count,
            "current_active_units": developer_plan.current_active_units,
            "ai_credits_used": developer_plan.ai_credits_used,
        }
    }

@router.post("/upgrade")
async def upgrade_plan(
    plan_type: PlanType,
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a checkout session for plan upgrade."""
    # Find developer
    developer = db.query(Developer).filter_by(id=current_user["id"]).first()
    
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Check if developer has a Stripe customer ID
    if not developer.stripe_customer_id:
        # Create Stripe customer
        from ...utils.pricing import create_stripe_customer
        developer.stripe_customer_id = create_stripe_customer(
            developer.id,
            developer.email,
            developer.legal_name
        )
        db.commit()
    
    # Create checkout session
    from ...utils.pricing import create_checkout_session
    checkout_url = create_checkout_session(
        developer.stripe_customer_id,
        plan_type,
        success_url=f"{os.getenv('FRONTEND_URL')}/dev/dashboard?upgrade=success",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/dev/dashboard?upgrade=cancelled"
    )
    
    return {"checkout_url": checkout_url}

@router.post("/buy-credits")
async def buy_ai_credits(
    quantity: int,
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a checkout session for buying AI credits."""
    # Find developer
    developer = db.query(Developer).filter_by(id=current_user["id"]).first()
    
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Check if developer has a Stripe customer ID
    if not developer.stripe_customer_id:
        # Create Stripe customer
        from ...utils.pricing import create_stripe_customer
        developer.stripe_customer_id = create_stripe_customer(
            developer.id,
            developer.email,
            developer.legal_name
        )
        db.commit()
    
    # Create checkout session
    from ...utils.pricing import purchase_additional_ai_credits
    checkout_url = purchase_additional_ai_credits(
        developer.stripe_customer_id,
        quantity,
        success_url=f"{os.getenv('FRONTEND_URL')}/dev/dashboard?credits=success",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/dev/dashboard?credits=cancelled"
    )
    
    return {"checkout_url": checkout_url}

@router.get("/billing-history")
async def get_billing_history(
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get billing history for the authenticated developer."""
    # Find developer
    developer = db.query(Developer).filter_by(id=current_user["id"]).first()
    
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Find developer plan
    from ...db.models.pricing import DeveloperPlan, BillingRecord
    developer_plan = db.query(DeveloperPlan).filter_by(developer_id=developer.id).first()
    
    if not developer_plan:
        return {"billing_history": []}
    
    # Get billing records
    billing_records = db.query(BillingRecord).filter_by(plan_id=developer_plan.id).order_by(BillingRecord.billing_date.desc()).all()
    
    # Format billing records
    formatted_records = []
    for record in billing_records:
        formatted_records.append({
            "id": record.id,
            "invoice_id": record.invoice_id,
            "amount": record.amount,
            "currency": record.currency,
            "description": record.description,
            "status": record.status,
            "billing_date": record.billing_date,
            "base_plan_amount": record.base_plan_amount,
            "overage_amount": record.overage_amount,
            "overage_units": record.overage_units,
        })
    
    return {"billing_history": formatted_records}
