"""
Fractional token minting logic for PropPulse co-investment groups
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
import asyncio
from datetime import datetime

from db.models.co_investment import CoInvestmentGroup, CapTable, TokenStatus
from agents.tokenization_agent.tokenization_agent import TokenizationAgent
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenMintingService:
    """
    Service for minting fractional tokens to investors
    
    Features:
    - Mint tokens to investors as they fund
    - Track minting status in database
    - Update Pinecone metadata with token information
    - Support for partitioned tranches (CLASS_A, CLASS_B)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the TokenMintingService"""
        self.config = config or {}
        
        # Initialize TokenizationAgent
        self.tokenization_agent = TokenizationAgent(self.config.get('tokenization_agent_config'))
        
        # Initialize PineconeMetadataUpdater
        self.pinecone_updater = PineconeMetadataUpdater()
    
    async def mint_tokens_for_investor(self, cap_table_id: int, db_session) -> Dict[str, Any]:
        """
        Mint tokens for an investor
        
        Args:
            cap_table_id: Cap table entry ID
            db_session: Database session
            
        Returns:
            Minting result
        """
        try:
            # Get cap table entry
            cap_table_entry = db_session.query(CapTable).filter(CapTable.id == cap_table_id).first()
            
            if not cap_table_entry:
                raise ValueError(f"Cap table entry not found: {cap_table_id}")
            
            # Check if tokens are already minted
            if cap_table_entry.token_status == TokenStatus.MINTED:
                return {
                    "status": "success",
                    "message": "Tokens already minted",
                    "token_amount": cap_table_entry.token_amount,
                    "transaction_hash": cap_table_entry.token_transaction_hash
                }
            
            # Check if KYC is approved
            if cap_table_entry.kyc_status != 'approved':
                return {
                    "status": "error",
                    "message": f"KYC not approved: {cap_table_entry.kyc_status}",
                    "next_steps": "Complete KYC verification before minting tokens"
                }
            
            # Check if investor wallet address is set
            if not cap_table_entry.investor_wallet_address:
                return {
                    "status": "error",
                    "message": "Investor wallet address not set",
                    "next_steps": "Set investor wallet address before minting tokens"
                }
            
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.id == cap_table_entry.co_investment_group_id
            ).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {cap_table_entry.co_investment_group_id}")
            
            # Check if token contract is deployed
            if not co_investment_group.token_contract_address:
                return {
                    "status": "error",
                    "message": "Token contract not deployed",
                    "next_steps": "Deploy token contract before minting tokens"
                }
            
            # Update token status to minting
            cap_table_entry.token_status = TokenStatus.MINTING
            db_session.commit()
            
            # Mint tokens
            mint_result = await self.tokenization_agent.mint_tokens(cap_table_id, db_session)
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_investor_token_metadata(
                property_id=co_investment_group.property_id,
                token_address=co_investment_group.token_contract_address,
                investor_wallet=cap_table_entry.investor_wallet_address,
                token_amount=cap_table_entry.token_amount,
                investor_class=cap_table_entry.investor_class.value
            )
            
            return mint_result
        
        except Exception as e:
            logger.error(f"Failed to mint tokens for investor: {str(e)}")
            
            # Update cap table entry with failure if it exists
            if 'cap_table_entry' in locals() and cap_table_entry:
                cap_table_entry.token_status = TokenStatus.FAILED
                db_session.commit()
            
            return {
                "status": "error",
                "message": f"Failed to mint tokens: {str(e)}"
            }
    
    async def mint_tokens_for_group(self, group_id: int, db_session) -> Dict[str, Any]:
        """
        Mint tokens for all eligible investors in a co-investment group
        
        Args:
            group_id: Co-investment group ID
            db_session: Database session
            
        Returns:
            Minting results
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {group_id}")
            
            # Check if token contract is deployed
            if not co_investment_group.token_contract_address:
                return {
                    "status": "error",
                    "message": "Token contract not deployed",
                    "next_steps": "Deploy token contract before minting tokens"
                }
            
            # Get eligible cap table entries
            eligible_entries = db_session.query(CapTable).filter(
                CapTable.co_investment_group_id == group_id,
                CapTable.kyc_status == 'approved',
                CapTable.investor_wallet_address != None,
                CapTable.token_status != TokenStatus.MINTED
            ).all()
            
            if not eligible_entries:
                return {
                    "status": "success",
                    "message": "No eligible investors found for token minting",
                    "minted_count": 0,
                    "total_count": 0
                }
            
            # Mint tokens for each eligible investor
            results = []
            for entry in eligible_entries:
                mint_result = await self.mint_tokens_for_investor(entry.id, db_session)
                results.append({
                    "cap_table_id": entry.id,
                    "investor_name": entry.investor_name,
                    "result": mint_result
                })
            
            # Count successful mints
            successful_mints = sum(1 for r in results if r["result"]["status"] == "success")
            
            return {
                "status": "success",
                "message": f"Minted tokens for {successful_mints} out of {len(eligible_entries)} eligible investors",
                "minted_count": successful_mints,
                "total_count": len(eligible_entries),
                "results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to mint tokens for group: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to mint tokens for group: {str(e)}"
            }
    
    async def check_minting_status(self, cap_table_id: int, db_session) -> Dict[str, Any]:
        """
        Check token minting status for an investor
        
        Args:
            cap_table_id: Cap table entry ID
            db_session: Database session
            
        Returns:
            Minting status
        """
        try:
            # Get cap table entry
            cap_table_entry = db_session.query(CapTable).filter(CapTable.id == cap_table_id).first()
            
            if not cap_table_entry:
                raise ValueError(f"Cap table entry not found: {cap_table_id}")
            
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.id == cap_table_entry.co_investment_group_id
            ).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {cap_table_entry.co_investment_group_id}")
            
            # Check if token contract is deployed
            if not co_investment_group.token_contract_address:
                return {
                    "status": "pending",
                    "message": "Token contract not deployed",
                    "token_status": None,
                    "next_steps": "Deploy token contract before minting tokens"
                }
            
            # Check token status
            token_status = cap_table_entry.token_status.value if cap_table_entry.token_status else None
            
            # If tokens are minted, get on-chain balance
            token_balance = None
            if token_status == "minted" and cap_table_entry.investor_wallet_address:
                try:
                    balance_result = await self.tokenization_agent.get_token_balance(
                        co_investment_group.token_contract_address,
                        cap_table_entry.investor_wallet_address
                    )
                    token_balance = balance_result.get("total_balance")
                except Exception as e:
                    logger.warning(f"Failed to get token balance: {str(e)}")
            
            return {
                "status": "success",
                "token_status": token_status,
                "token_amount": cap_table_entry.token_amount,
                "token_transaction_hash": cap_table_entry.token_transaction_hash,
                "token_minted_at": cap_table_entry.token_minted_at.isoformat() if cap_table_entry.token_minted_at else None,
                "on_chain_balance": token_balance,
                "investor_wallet_address": cap_table_entry.investor_wallet_address,
                "token_contract_address": co_investment_group.token_contract_address
            }
        
        except Exception as e:
            logger.error(f"Failed to check minting status: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to check minting status: {str(e)}"
            }
    
    async def retry_failed_minting(self, cap_table_id: int, db_session) -> Dict[str, Any]:
        """
        Retry failed token minting for an investor
        
        Args:
            cap_table_id: Cap table entry ID
            db_session: Database session
            
        Returns:
            Minting result
        """
        try:
            # Get cap table entry
            cap_table_entry = db_session.query(CapTable).filter(CapTable.id == cap_table_id).first()
            
            if not cap_table_entry:
                raise ValueError(f"Cap table entry not found: {cap_table_id}")
            
            # Check if token status is failed
            if cap_table_entry.token_status != TokenStatus.FAILED:
                return {
                    "status": "error",
                    "message": f"Cannot retry minting: token status is {cap_table_entry.token_status.value}",
                    "next_steps": "Only failed minting operations can be retried"
                }
            
            # Reset token status to pending
            cap_table_entry.token_status = TokenStatus.NOT_MINTED
            db_session.commit()
            
            # Mint tokens
            return await self.mint_tokens_for_investor(cap_table_id, db_session)
        
        except Exception as e:
            logger.error(f"Failed to retry minting: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to retry minting: {str(e)}"
            }
