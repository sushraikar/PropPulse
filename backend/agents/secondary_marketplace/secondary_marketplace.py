"""
Backend integration for PropPulseMarketplace secondary swap mini-DEX
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
import asyncio
from datetime import datetime
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from db.models.co_investment import CoInvestmentGroup, CapTable, TokenStatus
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecondaryMarketplace:
    """
    Secondary marketplace for PropPulse tokens
    
    Features:
    - Integration with PropPulseMarketplace smart contract
    - Listing management for secondary market
    - Event monitoring for token swaps
    - Compliance reporting
    - Cap table updates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the SecondaryMarketplace"""
        self.config = config or {}
        
        # Web3 configuration
        self.web3_url = self.config.get('web3_url', os.getenv('CHAINSTACK_URL', 'https://nd-123-456-789.polygon-edge.chainstacklabs.com'))
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.web3_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Check connection
        if not self.w3.is_connected():
            logger.error(f"Failed to connect to Polygon node at {self.web3_url}")
            raise ConnectionError(f"Failed to connect to Polygon node at {self.web3_url}")
        
        # Marketplace contract address
        self.marketplace_address = self.config.get('marketplace_address', os.getenv('MARKETPLACE_ADDRESS'))
        
        # Load contract ABI
        self.marketplace_abi = self._load_contract_abi('PropPulseMarketplace.json')
        
        # Initialize contract
        if self.marketplace_address:
            self.marketplace_contract = self.w3.eth.contract(
                address=self.marketplace_address,
                abi=self.marketplace_abi
            )
        
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
        
        # Initialize Pinecone metadata updater
        self.pinecone_updater = PineconeMetadataUpdater()
    
    def _load_contract_abi(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load contract ABI from file
        
        Args:
            filename: Contract JSON filename
            
        Returns:
            Contract ABI
        """
        try:
            contract_path = os.path.join(os.path.dirname(__file__), '..', '..', 'contracts', 'build', filename)
            with open(contract_path, 'r') as f:
                contract_json = json.load(f)
                return contract_json['abi']
        except Exception as e:
            logger.error(f"Failed to load contract ABI from {filename}: {str(e)}")
            raise
    
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
    
    async def deploy_marketplace(self) -> Dict[str, Any]:
        """
        Deploy marketplace contract
        
        Returns:
            Deployment result
        """
        try:
            # Get admin account
            admin = await self._get_account()
            
            # Load contract bytecode
            contract_path = os.path.join(os.path.dirname(__file__), '..', '..', 'contracts', 'build', 'PropPulseMarketplace.json')
            with open(contract_path, 'r') as f:
                contract_json = json.load(f)
                bytecode = contract_json['bytecode']
            
            # Create contract instance
            marketplace_contract = self.w3.eth.contract(abi=self.marketplace_abi, bytecode=bytecode)
            
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(admin.address)
            
            # Estimate gas for deployment
            gas_estimate = marketplace_contract.constructor(admin.address).estimate_gas({
                'from': admin.address,
                'nonce': nonce
            })
            
            # Build transaction
            transaction = {
                'from': admin.address,
                'gas': int(gas_estimate * 1.2),  # Add 20% buffer
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            }
            
            # Sign transaction
            tx_create = marketplace_contract.constructor(admin.address).build_transaction(transaction)
            signed_tx = admin.sign_transaction(tx_create)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get contract address
            contract_address = tx_receipt.contractAddress
            
            # Update marketplace address
            self.marketplace_address = contract_address
            self.marketplace_contract = self.w3.eth.contract(
                address=contract_address,
                abi=self.marketplace_abi
            )
            
            return {
                'status': 'success',
                'message': 'Marketplace contract deployed successfully',
                'contract_address': contract_address,
                'transaction_hash': tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to deploy marketplace contract: {str(e)}")
            raise
    
    async def update_whitelist(self, wallet_address: str, status: bool) -> Dict[str, Any]:
        """
        Update whitelist status for a wallet
        
        Args:
            wallet_address: Wallet address
            status: Whitelist status
            
        Returns:
            Update result
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Get admin account
            admin = await self._get_account()
            
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(admin.address)
            
            # Build transaction
            tx = self.marketplace_contract.functions.updateWhitelist(
                wallet_address,
                status
            ).build_transaction({
                'from': admin.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign transaction
            signed_tx = admin.sign_transaction(tx)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'status': 'success',
                'message': f"Whitelist status updated for {wallet_address}: {status}",
                'wallet_address': wallet_address,
                'whitelist_status': status,
                'transaction_hash': tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to update whitelist: {str(e)}")
            raise
    
    async def update_token_support(self, token_address: str, status: bool) -> Dict[str, Any]:
        """
        Update support status for a token
        
        Args:
            token_address: Token address
            status: Support status
            
        Returns:
            Update result
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Get admin account
            admin = await self._get_account()
            
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(admin.address)
            
            # Build transaction
            tx = self.marketplace_contract.functions.updateTokenSupport(
                token_address,
                status
            ).build_transaction({
                'from': admin.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign transaction
            signed_tx = admin.sign_transaction(tx)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'status': 'success',
                'message': f"Token support updated for {token_address}: {status}",
                'token_address': token_address,
                'support_status': status,
                'transaction_hash': tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to update token support: {str(e)}")
            raise
    
    async def set_seller_fee(self, fee_percentage: int) -> Dict[str, Any]:
        """
        Set seller fee percentage
        
        Args:
            fee_percentage: Fee percentage in basis points (e.g., 400 = 4%)
            
        Returns:
            Update result
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Get admin account
            admin = await self._get_account()
            
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(admin.address)
            
            # Build transaction
            tx = self.marketplace_contract.functions.setSellerFeePercentage(
                fee_percentage
            ).build_transaction({
                'from': admin.address,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign transaction
            signed_tx = admin.sign_transaction(tx)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                'status': 'success',
                'message': f"Seller fee percentage updated: {fee_percentage} basis points",
                'fee_percentage': fee_percentage,
                'transaction_hash': tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to set seller fee: {str(e)}")
            raise
    
    async def get_marketplace_info(self) -> Dict[str, Any]:
        """
        Get marketplace information
        
        Returns:
            Marketplace information
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Get fee percentage
            fee_percentage = self.marketplace_contract.functions.sellerFeePercentage().call()
            
            # Get fee collector
            fee_collector = self.marketplace_contract.functions.feeCollector().call()
            
            # Get max trade value
            max_trade_value = self.marketplace_contract.functions.maxTradeValueAED().call()
            
            return {
                'status': 'success',
                'marketplace_address': self.marketplace_address,
                'fee_percentage': fee_percentage,
                'fee_percentage_decimal': fee_percentage / 10000,
                'fee_collector': fee_collector,
                'max_trade_value_aed': max_trade_value / 10**18
            }
        
        except Exception as e:
            logger.error(f"Failed to get marketplace info: {str(e)}")
            raise
    
    async def is_whitelisted(self, wallet_address: str) -> bool:
        """
        Check if a wallet is whitelisted
        
        Args:
            wallet_address: Wallet address
            
        Returns:
            Whitelist status
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Check whitelist status
            return self.marketplace_contract.functions.isWhitelisted(wallet_address).call()
        
        except Exception as e:
            logger.error(f"Failed to check whitelist status: {str(e)}")
            raise
    
    async def is_token_supported(self, token_address: str) -> bool:
        """
        Check if a token is supported
        
        Args:
            token_address: Token address
            
        Returns:
            Support status
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Check token support
            return self.marketplace_contract.functions.isTokenSupported(token_address).call()
        
        except Exception as e:
            logger.error(f"Failed to check token support: {str(e)}")
            raise
    
    async def calculate_fee(self, amount: int) -> int:
        """
        Calculate fee for a given amount
        
        Args:
            amount: Amount to calculate fee for
            
        Returns:
            Fee amount
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Calculate fee
            return self.marketplace_contract.functions.calculateFee(amount).call()
        
        except Exception as e:
            logger.error(f"Failed to calculate fee: {str(e)}")
            raise
    
    async def process_swap_event(self, event_data: Dict[str, Any], db_session) -> Dict[str, Any]:
        """
        Process TokenSwapped event
        
        Args:
            event_data: Event data
            db_session: Database session
            
        Returns:
            Processing result
        """
        try:
            # Extract event data
            token_address = event_data.get('args', {}).get('token')
            seller_address = event_data.get('args', {}).get('seller')
            buyer_address = event_data.get('args', {}).get('buyer')
            amount = event_data.get('args', {}).get('amount')
            price = event_data.get('args', {}).get('price')
            fee = event_data.get('args', {}).get('fee')
            partition = event_data.get('args', {}).get('partition')
            
            # Find token in database
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.token_contract_address == token_address
            ).first()
            
            if not co_investment_group:
                logger.warning(f"Co-investment group not found for token: {token_address}")
                return {
                    'status': 'warning',
                    'message': f"Co-investment group not found for token: {token_address}",
                    'token_address': token_address
                }
            
            # Find seller in cap table
            seller_entry = db_session.query(CapTable).filter(
                CapTable.co_investment_group_id == co_investment_group.id,
                CapTable.investor_wallet_address == seller_address
            ).first()
            
            # Find buyer in cap table
            buyer_entry = db_session.query(CapTable).filter(
                CapTable.co_investment_group_id == co_investment_group.id,
                CapTable.investor_wallet_address == buyer_address
            ).first()
            
            # If buyer not found, create new entry
            if not buyer_entry:
                buyer_entry = CapTable(
                    co_investment_group_id=co_investment_group.id,
                    investor_wallet_address=buyer_address,
                    investor_name=f"Unknown ({buyer_address[:8]}...)",
                    investor_email="unknown@example.com",
                    investment_amount=price / 10**18,
                    share_percentage=0,  # Will be updated below
                    token_status=TokenStatus.MINTED,
                    token_amount=amount / 10**18,
                    token_transaction_hash=event_data.get('transactionHash', '').hex(),
                    token_minted_at=datetime.now(),
                    kyc_status="approved",  # Assuming KYC is approved since they're whitelisted
                    sign_status="signed",   # Assuming signing is complete
                    auto_reinvest=False
                )
                db_session.add(buyer_entry)
                db_session.flush()
            else:
                # Update buyer token amount
                buyer_entry.token_amount += amount / 10**18
            
            # Update seller token amount
            if seller_entry:
                seller_entry.token_amount -= amount / 10**18
            
            # Recalculate share percentages for all investors
            cap_table_entries = db_session.query(CapTable).filter(
                CapTable.co_investment_group_id == co_investment_group.id
            ).all()
            
            total_tokens = sum(entry.token_amount for entry in cap_table_entries)
            
            for entry in cap_table_entries:
                if total_tokens > 0:
                    entry.share_percentage = (entry.token_amount / total_tokens) * 100
                else:
                    entry.share_percentage = 0
            
            # Commit changes
            db_session.commit()
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_investor_token_metadata(
                property_id=co_investment_group.property_id,
                token_address=token_address,
                investor_wallet=buyer_address,
                token_amount=buyer_entry.token_amount,
                investor_class="class_a"  # Assuming Class A for now
            )
            
            if seller_entry:
                await self.pinecone_updater.update_investor_token_metadata(
                    property_id=co_investment_group.property_id,
                    token_address=token_address,
                    investor_wallet=seller_address,
                    token_amount=seller_entry.token_amount,
                    investor_class="class_a"  # Assuming Class A for now
                )
            
            # Generate compliance report
            compliance_report = {
                'event_type': 'token_swap',
                'token_address': token_address,
                'property_id': co_investment_group.property_id,
                'seller_address': seller_address,
                'buyer_address': buyer_address,
                'amount': amount / 10**18,
                'price': price / 10**18,
                'fee': fee / 10**18,
                'timestamp': datetime.now().isoformat(),
                'transaction_hash': event_data.get('transactionHash', '').hex()
            }
            
            # Save compliance report
            compliance_path = os.path.join(os.path.dirname(__file__), '..', '..', 'compliance', 'trades')
            os.makedirs(compliance_path, exist_ok=True)
            
            report_file = os.path.join(
                compliance_path,
                f"trade_{event_data.get('transactionHash', '').hex()}.json"
            )
            
            with open(report_file, 'w') as f:
                json.dump(compliance_report, f, indent=2)
            
            return {
                'status': 'success',
                'message': 'Swap event processed successfully',
                'token_address': token_address,
                'property_id': co_investment_group.property_id,
                'seller_address': seller_address,
                'buyer_address': buyer_address,
                'amount': amount / 10**18,
                'price': price / 10**18,
                'compliance_report': report_file
            }
        
        except Exception as e:
            logger.error(f"Failed to process swap event: {str(e)}")
            raise
    
    async def listen_for_events(self, db_session) -> None:
        """
        Listen for marketplace events
        
        Args:
            db_session: Database session
        """
        try:
            # Check if marketplace contract is initialized
            if not self.marketplace_contract:
                raise ValueError("Marketplace contract not initialized")
            
            # Get latest block
            latest_block = self.w3.eth.block_number
            
            # Create event filter
            swap_filter = self.marketplace_contract.events.TokenSwapped.create_filter(
                fromBlock=latest_block
            )
            
            # Listen for events
            while True:
                for event in swap_filter.get_new_entries():
                    try:
                        # Process swap event
                        result = await self.process_swap_event(event, db_session)
                        logger.info(f"Processed swap event: {result}")
                    except Exception as e:
                        logger.error(f"Error processing swap event: {str(e)}")
                
                # Sleep for a while
                await asyncio.sleep(15)
        
        except Exception as e:
            logger.error(f"Error listening for events: {str(e)}")
            raise
