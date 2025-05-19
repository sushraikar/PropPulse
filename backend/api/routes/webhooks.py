"""
Webhook handlers for document signing status updates
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
from sqlalchemy.orm import Session
import logging
import json

from db.database import get_db
from db.models.co_investment import CapTable, SignStatus
from agents.deal_signer.deal_signer import DealSigner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Initialize DealSigner
deal_signer = DealSigner()

@webhook_router.post("/zoho-sign")
async def zoho_sign_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Webhook handler for Zoho Sign status updates
    
    Args:
        request: Request object
        background_tasks: Background tasks
        db: Database session
        
    Returns:
        Webhook processing result
    """
    try:
        # Get webhook data
        webhook_data = await request.json()
        
        logger.info(f"Received Zoho Sign webhook: {json.dumps(webhook_data)}")
        
        # Process webhook in background to return response quickly
        background_tasks.add_task(
            process_zoho_sign_webhook,
            webhook_data=webhook_data,
            db=db
        )
        
        # Return immediate response
        return {
            "status": "success",
            "message": "Webhook received and processing started"
        }
    
    except Exception as e:
        logger.error(f"Error handling Zoho Sign webhook: {str(e)}")
        return {
            "status": "error",
            "message": f"Error handling webhook: {str(e)}"
        }

@webhook_router.post("/idnow")
async def idnow_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Webhook handler for IDnow KYC status updates
    
    Args:
        request: Request object
        background_tasks: Background tasks
        db: Database session
        
    Returns:
        Webhook processing result
    """
    try:
        # Get webhook data
        webhook_data = await request.json()
        
        logger.info(f"Received IDnow webhook: {json.dumps(webhook_data)}")
        
        # Process webhook in background to return response quickly
        background_tasks.add_task(
            process_idnow_webhook,
            webhook_data=webhook_data,
            db=db
        )
        
        # Return immediate response
        return {
            "status": "success",
            "message": "Webhook received and processing started"
        }
    
    except Exception as e:
        logger.error(f"Error handling IDnow webhook: {str(e)}")
        return {
            "status": "error",
            "message": f"Error handling webhook: {str(e)}"
        }

async def process_zoho_sign_webhook(webhook_data: Dict[str, Any], db: Session) -> None:
    """
    Process Zoho Sign webhook data
    
    Args:
        webhook_data: Webhook data from Zoho Sign
        db: Database session
    """
    try:
        # Process webhook data
        result = await deal_signer.process_webhook(webhook_data, db)
        
        logger.info(f"Zoho Sign webhook processed: {json.dumps(result)}")
        
        # Check if document is signed
        if result.get('sign_status') == 'signed':
            # Get document ID
            document_id = result.get('document_id')
            
            # Find cap table entries with this document ID
            cap_table_entries = db.query(CapTable).filter(CapTable.sign_document_id == document_id).all()
            
            for entry in cap_table_entries:
                # Check if KYC is approved and document is signed
                if entry.kyc_status == 'approved' and entry.sign_status == SignStatus.SIGNED:
                    # Check if investor has wallet address
                    if entry.investor_wallet_address:
                        # Trigger token minting in background
                        from agents.tokenization_agent.token_minting_service import TokenMintingService
                        token_minting_service = TokenMintingService()
                        mint_result = await token_minting_service.mint_tokens_for_investor(entry.id, db)
                        
                        logger.info(f"Token minting triggered for investor {entry.id}: {json.dumps(mint_result)}")
    
    except Exception as e:
        logger.error(f"Error processing Zoho Sign webhook: {str(e)}")

async def process_idnow_webhook(webhook_data: Dict[str, Any], db: Session) -> None:
    """
    Process IDnow webhook data
    
    Args:
        webhook_data: Webhook data from IDnow
        db: Database session
    """
    try:
        # Process webhook data
        from integrations.idnow.idnow_api import IDnowAPI
        idnow_api = IDnowAPI()
        
        processed_data = idnow_api.process_webhook(webhook_data)
        
        logger.info(f"IDnow webhook processed: {json.dumps(processed_data)}")
        
        # Get identification ID
        identification_id = processed_data.get('identification_id')
        
        # Find cap table entry with this KYC ID
        cap_table_entry = db.query(CapTable).filter(CapTable.kyc_idnow_id == identification_id).first()
        
        if not cap_table_entry:
            logger.warning(f"Cap table entry not found for KYC ID: {identification_id}")
            return
        
        # Check if KYC is approved and document is signed
        if cap_table_entry.kyc_status == 'approved' and cap_table_entry.sign_status == SignStatus.SIGNED:
            # Check if investor has wallet address
            if cap_table_entry.investor_wallet_address:
                # Trigger token minting in background
                from agents.tokenization_agent.token_minting_service import TokenMintingService
                token_minting_service = TokenMintingService()
                mint_result = await token_minting_service.mint_tokens_for_investor(cap_table_entry.id, db)
                
                logger.info(f"Token minting triggered for investor {cap_table_entry.id}: {json.dumps(mint_result)}")
    
    except Exception as e:
        logger.error(f"Error processing IDnow webhook: {str(e)}")
