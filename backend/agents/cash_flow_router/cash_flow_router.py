"""
Cash Flow Router and Gnosis Safe wallet integration for PropPulse
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
import asyncio
from datetime import datetime, timedelta
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from db.models.co_investment import CoInvestmentGroup, CapTable, PayoutSchedule, Payout

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GnosisSafeAPI:
    """
    Gnosis Safe API client
    
    Provides methods for:
    - Creating and managing Gnosis Safe wallets
    - Executing transactions
    - Checking transaction status
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Gnosis Safe API client"""
        self.config = config or {}
        
        # API configuration
        self.network = self.config.get('network', 'polygon')
        
        # Set base URL based on network
        if self.network == 'polygon':
            self.base_url = "https://safe-transaction-polygon.safe.global/api/v1"
            self.chain_id = 137
        elif self.network == 'mumbai':
            self.base_url = "https://safe-transaction-mumbai.safe.global/api/v1"
            self.chain_id = 80001
        else:
            raise ValueError(f"Unsupported network: {self.network}")
        
        # Web3 configuration
        self.web3_url = self.config.get('web3_url', os.getenv('CHAINSTACK_URL', 'https://nd-123-456-789.polygon-edge.chainstacklabs.com'))
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.web3_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Check connection
        if not self.w3.is_connected():
            logger.error(f"Failed to connect to Polygon node at {self.web3_url}")
            raise ConnectionError(f"Failed to connect to Polygon node at {self.web3_url}")
        
        # Initialize Azure Key Vault client
        self.key_vault_name = self.config.get('key_vault_name', os.getenv('KEY_VAULT_NAME'))
        self.key_vault_url = f"https://{self.key_vault_name}.vault.azure.net"
        self.key_vault_client = None
        
        if self.key_vault_name:
            try:
                credential = DefaultAzureCredential()
                self.key_vault_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
            except Exception as e:
                logger.error(f"Failed to initialize Azure Key Vault client: {str(e)}")
    
    async def _get_private_key(self, key_name: str) -> str:
        """
        Get private key from Azure Key Vault
        
        Args:
            key_name: Key name in Azure Key Vault
            
        Returns:
            Private key
        """
        if not self.key_vault_client:
            raise ValueError("Azure Key Vault client not initialized")
        
        try:
            secret = self.key_vault_client.get_secret(key_name)
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get private key from Azure Key Vault: {str(e)}")
            raise
    
    async def _get_account(self, key_name: str = 'ADMIN_PRIVATE_KEY') -> Account:
        """
        Get Ethereum account from private key
        
        Args:
            key_name: Key name in Azure Key Vault
            
        Returns:
            Ethereum account
        """
        try:
            # Try to get private key from Azure Key Vault
            if self.key_vault_client:
                private_key = await self._get_private_key(key_name)
            else:
                # Fallback to environment variable
                private_key = os.getenv(key_name)
            
            if not private_key:
                raise ValueError(f"Private key not found: {key_name}")
            
            # Add 0x prefix if missing
            if not private_key.startswith('0x'):
                private_key = f"0x{private_key}"
            
            return Account.from_key(private_key)
        except Exception as e:
            logger.error(f"Failed to get account: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Response data
        """
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Error making request to {url}: {str(e)}")
            raise
    
    async def create_safe(self, owners: List[str], threshold: int = 1) -> Dict[str, Any]:
        """
        Create Gnosis Safe wallet
        
        Args:
            owners: List of owner addresses
            threshold: Number of required confirmations
            
        Returns:
            Safe creation data
        """
        try:
            # Get admin account
            admin = await self._get_account()
            
            # Ensure admin is included in owners
            if admin.address not in owners:
                owners.append(admin.address)
            
            # Prepare safe creation data
            safe_creation_data = {
                "saltNonce": int(datetime.now().timestamp()),
                "owners": owners,
                "threshold": threshold,
                "paymentToken": "0x0000000000000000000000000000000000000000"  # ETH
            }
            
            # Make request
            endpoint = "/safes/"
            result = self._make_request('POST', endpoint, safe_creation_data)
            
            # Get safe address
            safe_address = result.get('safe')
            
            if not safe_address:
                raise ValueError(f"Failed to create safe: {result}")
            
            return {
                "status": "success",
                "safe_address": safe_address,
                "owners": owners,
                "threshold": threshold
            }
        
        except Exception as e:
            logger.error(f"Failed to create safe: {str(e)}")
            raise
    
    async def get_safe_info(self, safe_address: str) -> Dict[str, Any]:
        """
        Get Gnosis Safe wallet info
        
        Args:
            safe_address: Safe address
            
        Returns:
            Safe info
        """
        try:
            # Make request
            endpoint = f"/safes/{safe_address}/"
            return self._make_request('GET', endpoint)
        
        except Exception as e:
            logger.error(f"Failed to get safe info: {str(e)}")
            raise
    
    async def get_safe_balance(self, safe_address: str) -> Dict[str, Any]:
        """
        Get Gnosis Safe wallet balance
        
        Args:
            safe_address: Safe address
            
        Returns:
            Safe balance
        """
        try:
            # Make request
            endpoint = f"/safes/{safe_address}/balances/"
            return self._make_request('GET', endpoint)
        
        except Exception as e:
            logger.error(f"Failed to get safe balance: {str(e)}")
            raise
    
    async def create_transaction(
        self,
        safe_address: str,
        to: str,
        value: int,
        data: str = "0x",
        operation: int = 0,
        safe_tx_gas: int = 0,
        base_gas: int = 0,
        gas_price: int = 0,
        gas_token: str = "0x0000000000000000000000000000000000000000",
        refund_receiver: str = "0x0000000000000000000000000000000000000000",
        nonce: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create Gnosis Safe transaction
        
        Args:
            safe_address: Safe address
            to: Recipient address
            value: Transaction value in wei
            data: Transaction data
            operation: Operation type (0=CALL, 1=DELEGATE_CALL)
            safe_tx_gas: Gas for the safe transaction
            base_gas: Gas for data and execution
            gas_price: Gas price
            gas_token: Token for gas payment
            refund_receiver: Address for gas payment refund
            nonce: Transaction nonce
            
        Returns:
            Transaction data
        """
        try:
            # Get admin account
            admin = await self._get_account()
            
            # Get safe info
            safe_info = await self.get_safe_info(safe_address)
            
            # Get nonce if not provided
            if nonce is None:
                nonce = safe_info.get('nonce', 0)
            
            # Prepare transaction data
            transaction_data = {
                "safe": safe_address,
                "to": to,
                "value": value,
                "data": data,
                "operation": operation,
                "safeTxGas": safe_tx_gas,
                "baseGas": base_gas,
                "gasPrice": gas_price,
                "gasToken": gas_token,
                "refundReceiver": refund_receiver,
                "nonce": nonce
            }
            
            # Make request
            endpoint = f"/safes/{safe_address}/transactions/"
            result = self._make_request('POST', endpoint, transaction_data)
            
            # Get safe transaction hash
            safe_tx_hash = result.get('safeTxHash')
            
            if not safe_tx_hash:
                raise ValueError(f"Failed to create transaction: {result}")
            
            return {
                "status": "success",
                "safe_tx_hash": safe_tx_hash,
                "transaction_data": transaction_data
            }
        
        except Exception as e:
            logger.error(f"Failed to create transaction: {str(e)}")
            raise
    
    async def sign_transaction(self, safe_address: str, safe_tx_hash: str) -> Dict[str, Any]:
        """
        Sign Gnosis Safe transaction
        
        Args:
            safe_address: Safe address
            safe_tx_hash: Safe transaction hash
            
        Returns:
            Signature data
        """
        try:
            # Get admin account
            admin = await self._get_account()
            
            # Sign transaction hash
            signature = self.w3.eth.account.sign_message(
                self.w3.eth.account.encode_defunct(hexstr=safe_tx_hash),
                private_key=admin.key
            )
            
            # Format signature
            signature_data = {
                "safe": safe_address,
                "safeTxHash": safe_tx_hash,
                "signature": signature.signature.hex()
            }
            
            # Make request
            endpoint = f"/safes/{safe_address}/signatures/"
            result = self._make_request('POST', endpoint, signature_data)
            
            return {
                "status": "success",
                "signature": signature.signature.hex(),
                "result": result
            }
        
        except Exception as e:
            logger.error(f"Failed to sign transaction: {str(e)}")
            raise
    
    async def execute_transaction(self, safe_address: str, safe_tx_hash: str) -> Dict[str, Any]:
        """
        Execute Gnosis Safe transaction
        
        Args:
            safe_address: Safe address
            safe_tx_hash: Safe transaction hash
            
        Returns:
            Execution result
        """
        try:
            # Get admin account
            admin = await self._get_account()
            
            # Get transaction data
            endpoint = f"/safes/{safe_address}/transactions/{safe_tx_hash}/"
            transaction_data = self._make_request('GET', endpoint)
            
            # Prepare execution data
            execution_data = {
                "safe": safe_address,
                "safeTxHash": safe_tx_hash
            }
            
            # Make request
            endpoint = f"/safes/{safe_address}/transactions/{safe_tx_hash}/execute/"
            result = self._make_request('POST', endpoint, execution_data)
            
            # Get transaction hash
            tx_hash = result.get('txHash')
            
            if not tx_hash:
                raise ValueError(f"Failed to execute transaction: {result}")
            
            return {
                "status": "success",
                "tx_hash": tx_hash,
                "result": result
            }
        
        except Exception as e:
            logger.error(f"Failed to execute transaction: {str(e)}")
            raise

class CashFlowRouter:
    """
    Cash Flow Router for PropPulse
    
    Handles rent distribution and pro-rata payouts to investors
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the CashFlowRouter"""
        self.config = config or {}
        
        # Initialize Gnosis Safe API
        self.gnosis_safe = GnosisSafeAPI(self.config.get('gnosis_safe_config'))
        
        # Initialize Web3
        self.web3_url = self.config.get('web3_url', os.getenv('CHAINSTACK_URL', 'https://nd-123-456-789.polygon-edge.chainstacklabs.com'))
        self.w3 = Web3(Web3.HTTPProvider(self.web3_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # USDT contract address on Polygon
        self.usdt_address = self.config.get('usdt_address', '0xc2132D05D31c914a87C6611C10748AEb04B58e8F')
        
        # USDT contract ABI (minimal for transfers)
        self.usdt_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Minimum distribution amount in USDT (200 AED)
        self.min_distribution_amount = self.config.get('min_distribution_amount', 200)
    
    async def create_rent_pool_wallet(self, co_investment_group_id: int, db_session) -> Dict[str, Any]:
        """
        Create rent pool wallet for a co-investment group
        
        Args:
            co_investment_group_id: Co-investment group ID
            db_session: Database session
            
        Returns:
            Wallet creation result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == co_investment_group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {co_investment_group_id}")
            
            # Check if wallet already exists
            if co_investment_group.gnosis_safe_address:
                return {
                    "status": "success",
                    "message": "Rent pool wallet already exists",
                    "safe_address": co_investment_group.gnosis_safe_address
                }
            
            # Get admin account
            admin = await self.gnosis_safe._get_account()
            
            # Create safe with admin as owner
            safe_result = await self.gnosis_safe.create_safe([admin.address])
            
            # Get safe address
            safe_address = safe_result.get('safe_address')
            
            # Update co-investment group
            co_investment_group.gnosis_safe_address = safe_address
            db_session.commit()
            
            return {
                "status": "success",
                "message": "Rent pool wallet created successfully",
                "safe_address": safe_address,
                "owners": safe_result.get('owners')
            }
        
        except Exception as e:
            logger.error(f"Failed to create rent pool wallet: {str(e)}")
            raise
    
    async def schedule_payout(
        self,
        co_investment_group_id: int,
        amount: float,
        scheduled_date: datetime,
        description: str,
        db_session
    ) -> Dict[str, Any]:
        """
        Schedule payout for a co-investment group
        
        Args:
            co_investment_group_id: Co-investment group ID
            amount: Payout amount in AED
            scheduled_date: Scheduled date for payout
            description: Payout description
            db_session: Database session
            
        Returns:
            Payout scheduling result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == co_investment_group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {co_investment_group_id}")
            
            # Check if rent pool wallet exists
            if not co_investment_group.gnosis_safe_address:
                # Create rent pool wallet
                await self.create_rent_pool_wallet(co_investment_group_id, db_session)
            
            # Create payout schedule
            payout_schedule = PayoutSchedule(
                co_investment_group_id=co_investment_group_id,
                scheduled_date=scheduled_date,
                amount=amount,
                description=description,
                status="pending"
            )
            
            db_session.add(payout_schedule)
            db_session.commit()
            db_session.refresh(payout_schedule)
            
            return {
                "status": "success",
                "message": "Payout scheduled successfully",
                "payout_schedule_id": payout_schedule.id,
                "scheduled_date": payout_schedule.scheduled_date.isoformat(),
                "amount": payout_schedule.amount
            }
        
        except Exception as e:
            logger.error(f"Failed to schedule payout: {str(e)}")
            raise
    
    async def execute_payout(self, payout_schedule_id: int, db_session) -> Dict[str, Any]:
        """
        Execute payout for a co-investment group
        
        Args:
            payout_schedule_id: Payout schedule ID
            db_session: Database session
            
        Returns:
            Payout execution result
        """
        try:
            # Get payout schedule
            payout_schedule = db_session.query(PayoutSchedule).filter(PayoutSchedule.id == payout_schedule_id).first()
            
            if not payout_schedule:
                raise ValueError(f"Payout schedule not found: {payout_schedule_id}")
            
            # Check if payout is already completed
            if payout_schedule.status == "completed":
                return {
                    "status": "success",
                    "message": "Payout already completed",
                    "payout_schedule_id": payout_schedule.id,
                    "transaction_hash": payout_schedule.transaction_hash
                }
            
            # Check if payout is pending
            if payout_schedule.status != "pending":
                return {
                    "status": "error",
                    "message": f"Payout is not pending: {payout_schedule.status}",
                    "payout_schedule_id": payout_schedule.id
                }
            
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == payout_schedule.co_investment_group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {payout_schedule.co_investment_group_id}")
            
            # Check if rent pool wallet exists
            if not co_investment_group.gnosis_safe_address:
                return {
                    "status": "error",
                    "message": "Rent pool wallet not found",
                    "payout_schedule_id": payout_schedule.id
                }
            
            # Get safe balance
            safe_balance = await self.gnosis_safe.get_safe_balance(co_investment_group.gnosis_safe_address)
            
            # Find USDT balance
            usdt_balance = 0
            for token in safe_balance:
                if token.get('tokenAddress', '').lower() == self.usdt_address.lower():
                    usdt_balance = int(token.get('balance', '0'))
                    break
            
            # Check if balance is sufficient
            if usdt_balance < payout_schedule.amount * 10**6:  # USDT has 6 decimals
                return {
                    "status": "error",
                    "message": f"Insufficient balance: {usdt_balance / 10**6} USDT < {payout_schedule.amount} AED",
                    "payout_schedule_id": payout_schedule.id
                }
            
            # Update payout schedule status
            payout_schedule.status = "processing"
            db_session.commit()
            
            # Get cap table entries
            cap_table_entries = db_session.query(CapTable).filter(CapTable.co_investment_group_id == co_investment_group.id).all()
            
            # Calculate payouts
            payouts = []
            for entry in cap_table_entries:
                # Calculate payout amount
                payout_amount = payout_schedule.amount * (entry.share_percentage / 100)
                
                # Check if amount is above minimum
                if payout_amount < self.min_distribution_amount:
                    # Create payout record with rollover
                    payout = Payout(
                        payout_schedule_id=payout_schedule.id,
                        cap_table_id=entry.id,
                        amount=payout_amount,
                        status="pending",
                        reinvested=False
                    )
                    
                    payouts.append({
                        "cap_table_id": entry.id,
                        "investor_name": entry.investor_name,
                        "investor_wallet_address": entry.investor_wallet_address,
                        "amount": payout_amount,
                        "status": "rollover",
                        "reason": f"Amount below minimum: {payout_amount} < {self.min_distribution_amount} AED"
                    })
                
                # Check if auto-reinvest is enabled
                elif entry.auto_reinvest:
                    # Create payout record with reinvestment
                    payout = Payout(
                        payout_schedule_id=payout_schedule.id,
                        cap_table_id=entry.id,
                        amount=payout_amount,
                        status="reinvested",
                        reinvested=True
                    )
                    
                    payouts.append({
                        "cap_table_id": entry.id,
                        "investor_name": entry.investor_name,
                        "investor_wallet_address": entry.investor_wallet_address,
                        "amount": payout_amount,
                        "status": "reinvested",
                        "reason": "Auto-reinvest enabled"
                    })
                
                # Check if wallet address is set
                elif not entry.investor_wallet_address:
                    # Create payout record with pending status
                    payout = Payout(
                        payout_schedule_id=payout_schedule.id,
                        cap_table_id=entry.id,
                        amount=payout_amount,
                        status="pending",
                        reinvested=False
                    )
                    
                    payouts.append({
                        "cap_table_id": entry.id,
                        "investor_name": entry.investor_name,
                        "investor_wallet_address": None,
                        "amount": payout_amount,
                        "status": "pending",
                        "reason": "Wallet address not set"
                    })
                
                else:
                    # Create payout record with processing status
                    payout = Payout(
                        payout_schedule_id=payout_schedule.id,
                        cap_table_id=entry.id,
                        amount=payout_amount,
                        status="processing",
                        reinvested=False
                    )
                    
                    db_session.add(payout)
                    db_session.flush()
                    
                    # Execute payout
                    try:
                        # Initialize USDT contract
                        usdt_contract = self.w3.eth.contract(address=self.usdt_address, abi=self.usdt_abi)
                        
                        # Prepare transaction data
                        transfer_data = usdt_contract.functions.transfer(
                            entry.investor_wallet_address,
                            int(payout_amount * 10**6)  # USDT has 6 decimals
                        ).build_transaction({
                            'from': co_investment_group.gnosis_safe_address,
                            'gas': 100000,
                            'gasPrice': self.w3.eth.gas_price,
                            'nonce': 0  # Will be set by Gnosis Safe
                        })['data']
                        
                        # Create Gnosis Safe transaction
                        tx_result = await self.gnosis_safe.create_transaction(
                            safe_address=co_investment_group.gnosis_safe_address,
                            to=self.usdt_address,
                            value=0,
                            data=transfer_data
                        )
                        
                        # Sign transaction
                        sign_result = await self.gnosis_safe.sign_transaction(
                            safe_address=co_investment_group.gnosis_safe_address,
                            safe_tx_hash=tx_result.get('safe_tx_hash')
                        )
                        
                        # Execute transaction
                        exec_result = await self.gnosis_safe.execute_transaction(
                            safe_address=co_investment_group.gnosis_safe_address,
                            safe_tx_hash=tx_result.get('safe_tx_hash')
                        )
                        
                        # Update payout record
                        payout.status = "completed"
                        payout.transaction_hash = exec_result.get('tx_hash')
                        payout.completed_at = datetime.now()
                        
                        # Update cap table entry
                        entry.total_distributions += payout_amount
                        
                        payouts.append({
                            "cap_table_id": entry.id,
                            "investor_name": entry.investor_name,
                            "investor_wallet_address": entry.investor_wallet_address,
                            "amount": payout_amount,
                            "status": "completed",
                            "transaction_hash": exec_result.get('tx_hash')
                        })
                    
                    except Exception as e:
                        logger.error(f"Failed to execute payout for investor {entry.id}: {str(e)}")
                        
                        # Update payout record
                        payout.status = "failed"
                        
                        payouts.append({
                            "cap_table_id": entry.id,
                            "investor_name": entry.investor_name,
                            "investor_wallet_address": entry.investor_wallet_address,
                            "amount": payout_amount,
                            "status": "failed",
                            "error": str(e)
                        })
            
            # Update payout schedule
            payout_schedule.status = "completed"
            payout_schedule.completed_at = datetime.now()
            db_session.commit()
            
            return {
                "status": "success",
                "message": "Payout executed successfully",
                "payout_schedule_id": payout_schedule.id,
                "payouts": payouts
            }
        
        except Exception as e:
            logger.error(f"Failed to execute payout: {str(e)}")
            
            # Update payout schedule status if it exists
            if 'payout_schedule' in locals() and payout_schedule:
                payout_schedule.status = "failed"
                db_session.commit()
            
            raise
    
    async def check_pending_payouts(self, db_session) -> Dict[str, Any]:
        """
        Check for pending payouts
        
        Args:
            db_session: Database session
            
        Returns:
            Pending payouts
        """
        try:
            # Get current date
            current_date = datetime.now()
            
            # Get pending payout schedules
            pending_schedules = db_session.query(PayoutSchedule).filter(
                PayoutSchedule.status == "pending",
                PayoutSchedule.scheduled_date <= current_date
            ).all()
            
            return {
                "status": "success",
                "pending_count": len(pending_schedules),
                "pending_schedules": [
                    {
                        "id": schedule.id,
                        "co_investment_group_id": schedule.co_investment_group_id,
                        "scheduled_date": schedule.scheduled_date.isoformat(),
                        "amount": schedule.amount,
                        "description": schedule.description
                    }
                    for schedule in pending_schedules
                ]
            }
        
        except Exception as e:
            logger.error(f"Failed to check pending payouts: {str(e)}")
            raise
    
    async def process_pending_payouts(self, db_session) -> Dict[str, Any]:
        """
        Process all pending payouts
        
        Args:
            db_session: Database session
            
        Returns:
            Processing results
        """
        try:
            # Check pending payouts
            pending_result = await self.check_pending_payouts(db_session)
            
            # Get pending schedules
            pending_schedules = pending_result.get('pending_schedules', [])
            
            if not pending_schedules:
                return {
                    "status": "success",
                    "message": "No pending payouts found",
                    "processed_count": 0
                }
            
            # Process each pending schedule
            results = []
            for schedule in pending_schedules:
                try:
                    result = await self.execute_payout(schedule.get('id'), db_session)
                    results.append({
                        "payout_schedule_id": schedule.get('id'),
                        "status": "success",
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "payout_schedule_id": schedule.get('id'),
                        "status": "error",
                        "error": str(e)
                    })
            
            # Count successful executions
            success_count = sum(1 for r in results if r.get('status') == 'success')
            
            return {
                "status": "success",
                "message": f"Processed {success_count} out of {len(pending_schedules)} pending payouts",
                "processed_count": success_count,
                "total_count": len(pending_schedules),
                "results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process pending payouts: {str(e)}")
            raise
