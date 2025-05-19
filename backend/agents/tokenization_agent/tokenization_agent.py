"""
TokenizationAgent for PropPulse

Handles the deployment and management of ERC-1400 tokens for property tokenization
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.signers.local import LocalAccount
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from db.models.co_investment import CoInvestmentGroup, CapTable, TokenStatus
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenizationAgent:
    """
    Agent for tokenizing real estate properties using ERC-1400 tokens
    
    Features:
    - Deploy ERC-1400 tokens on Polygon PoS
    - Mint fractional tokens for investors
    - Manage token transfers and compliance
    - Update Pinecone metadata with token information
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the TokenizationAgent"""
        self.config = config or {}
        
        # Web3 configuration
        self.chainstack_url = self.config.get('chainstack_url', os.getenv('CHAINSTACK_URL', 'https://nd-123-456-789.polygon-edge.chainstacklabs.com'))
        self.chain_id = self.config.get('chain_id', int(os.getenv('POLYGON_CHAIN_ID', '80001')))  # Default to Mumbai testnet
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.chainstack_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Check connection
        if not self.w3.is_connected():
            logger.error(f"Failed to connect to Polygon node at {self.chainstack_url}")
            raise ConnectionError(f"Failed to connect to Polygon node at {self.chainstack_url}")
        
        # Load contract ABIs
        self.token_abi = self._load_contract_abi('PropPulseToken.json')
        self.token_bytecode = self._load_contract_bytecode('PropPulseToken.json')
        
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
    
    def _load_contract_bytecode(self, filename: str) -> str:
        """
        Load contract bytecode from file
        
        Args:
            filename: Contract JSON filename
            
        Returns:
            Contract bytecode
        """
        try:
            contract_path = os.path.join(os.path.dirname(__file__), '..', '..', 'contracts', 'build', filename)
            with open(contract_path, 'r') as f:
                contract_json = json.load(f)
                return contract_json['bytecode']
        except Exception as e:
            logger.error(f"Failed to load contract bytecode from {filename}: {str(e)}")
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
    
    async def _get_account(self, key_name: str = 'DEPLOYER_PRIVATE_KEY') -> LocalAccount:
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
    
    async def deploy_token(self, co_investment_group_id: int, property_data: Dict[str, Any], db_session) -> Dict[str, Any]:
        """
        Deploy ERC-1400 token for a property
        
        Args:
            co_investment_group_id: Co-investment group ID
            property_data: Property data
            db_session: Database session
            
        Returns:
            Deployment result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == co_investment_group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {co_investment_group_id}")
            
            # Check if token is already deployed
            if co_investment_group.token_contract_address:
                return {
                    "status": "success",
                    "message": "Token already deployed",
                    "token_address": co_investment_group.token_contract_address
                }
            
            # Get deployer account
            deployer = await self._get_account()
            
            # Get controller account (for regulatory compliance)
            controller = await self._get_account('CONTROLLER_PRIVATE_KEY')
            
            # Prepare token name and symbol
            token_name = f"PropPulse {property_data.get('Unit_No', 'Unknown')}"
            token_symbol = f"PP{property_data.get('Unit_No', 'UNK').replace('-', '')}"
            
            # Prepare property metadata
            property_id = property_data.get('id', '')
            unit_no = property_data.get('Unit_No', '')
            project_name = property_data.get('Project_Name', '')
            property_value = int(float(property_data.get('List_Price_AED', '0')))
            
            # Deploy token contract
            token_contract = self.w3.eth.contract(abi=self.token_abi, bytecode=self.token_bytecode)
            
            # Prepare transaction
            nonce = self.w3.eth.get_transaction_count(deployer.address)
            
            # Estimate gas for deployment
            gas_estimate = token_contract.constructor().estimate_gas({
                'from': deployer.address,
                'nonce': nonce
            })
            
            # Build transaction
            transaction = {
                'from': deployer.address,
                'gas': int(gas_estimate * 1.2),  # Add 20% buffer
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            }
            
            # Deploy contract
            tx_hash = token_contract.constructor().transact(transaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get contract address
            token_address = tx_receipt.contractAddress
            
            # Initialize token
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            
            # Prepare initialization transaction
            nonce = self.w3.eth.get_transaction_count(deployer.address)
            
            # Initialize token
            tx_hash = token_contract.functions.initialize(
                token_name,
                token_symbol,
                deployer.address,
                controller.address,
                property_id,
                unit_no,
                project_name,
                property_value
            ).transact({
                'from': deployer.address,
                'gas': 5000000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Update co-investment group
            co_investment_group.token_contract_address = token_address
            co_investment_group.token_contract_abi = self.token_abi
            db_session.commit()
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_property_token_metadata(
                property_id=property_id,
                token_address=token_address,
                token_name=token_name,
                token_symbol=token_symbol
            )
            
            return {
                "status": "success",
                "message": "Token deployed successfully",
                "token_address": token_address,
                "token_name": token_name,
                "token_symbol": token_symbol,
                "transaction_hash": tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to deploy token: {str(e)}")
            raise
    
    async def mint_tokens(self, cap_table_id: int, db_session) -> Dict[str, Any]:
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
                    "message": f"KYC not approved: {cap_table_entry.kyc_status}"
                }
            
            # Check if investor wallet address is set
            if not cap_table_entry.investor_wallet_address:
                return {
                    "status": "error",
                    "message": "Investor wallet address not set"
                }
            
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.id == cap_table_entry.co_investment_group_id
            ).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {cap_table_entry.co_investment_group_id}")
            
            # Check if token is deployed
            if not co_investment_group.token_contract_address:
                return {
                    "status": "error",
                    "message": "Token not deployed"
                }
            
            # Get deployer account
            deployer = await self._get_account()
            
            # Initialize token contract
            token_contract = self.w3.eth.contract(
                address=co_investment_group.token_contract_address,
                abi=co_investment_group.token_contract_abi
            )
            
            # Calculate token amount (18 decimals)
            # Token amount is proportional to investment amount
            # 1 token = 1 AED
            token_amount = int(cap_table_entry.investment_amount * 10**18)
            
            # Determine partition based on investor class
            partition = token_contract.functions.PARTITION_CLASS_A().call()
            if cap_table_entry.investor_class == 'class_b':
                partition = token_contract.functions.PARTITION_CLASS_B().call()
            
            # Add investor to whitelist
            nonce = self.w3.eth.get_transaction_count(deployer.address)
            tx_hash = token_contract.functions.addToWhitelist(
                cap_table_entry.investor_wallet_address
            ).transact({
                'from': deployer.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            # Wait for transaction receipt
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Mint tokens
            nonce = self.w3.eth.get_transaction_count(deployer.address)
            tx_hash = token_contract.functions.issueByPartition(
                partition,
                cap_table_entry.investor_wallet_address,
                token_amount,
                b''
            ).transact({
                'from': deployer.address,
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Update cap table entry
            cap_table_entry.token_status = TokenStatus.MINTED
            cap_table_entry.token_amount = token_amount / 10**18  # Store as decimal
            cap_table_entry.token_transaction_hash = tx_receipt.transactionHash.hex()
            cap_table_entry.token_minted_at = self.w3.eth.get_block(tx_receipt.blockNumber).timestamp
            db_session.commit()
            
            return {
                "status": "success",
                "message": "Tokens minted successfully",
                "token_amount": cap_table_entry.token_amount,
                "transaction_hash": cap_table_entry.token_transaction_hash
            }
        
        except Exception as e:
            logger.error(f"Failed to mint tokens: {str(e)}")
            
            # Update cap table entry with failure
            if 'cap_table_entry' in locals():
                cap_table_entry.token_status = TokenStatus.FAILED
                db_session.commit()
            
            raise
    
    async def get_token_balance(self, token_address: str, wallet_address: str) -> Dict[str, Any]:
        """
        Get token balance for a wallet
        
        Args:
            token_address: Token contract address
            wallet_address: Wallet address
            
        Returns:
            Token balance data
        """
        try:
            # Initialize token contract
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            
            # Get total balance
            total_balance = token_contract.functions.balanceOf(wallet_address).call()
            
            # Get balance by partition
            partition_a = token_contract.functions.PARTITION_CLASS_A().call()
            partition_b = token_contract.functions.PARTITION_CLASS_B().call()
            
            balance_a = token_contract.functions.balanceOfByPartition(partition_a, wallet_address).call()
            balance_b = token_contract.functions.balanceOfByPartition(partition_b, wallet_address).call()
            
            return {
                "status": "success",
                "wallet_address": wallet_address,
                "token_address": token_address,
                "total_balance": total_balance / 10**18,
                "balance_by_partition": {
                    "class_a": balance_a / 10**18,
                    "class_b": balance_b / 10**18
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get token balance: {str(e)}")
            raise
    
    async def transfer_tokens(
        self,
        token_address: str,
        from_address: str,
        to_address: str,
        amount: float,
        partition: str = 'class_a',
        private_key_name: str = 'INVESTOR_PRIVATE_KEY'
    ) -> Dict[str, Any]:
        """
        Transfer tokens from one wallet to another
        
        Args:
            token_address: Token contract address
            from_address: Sender wallet address
            to_address: Recipient wallet address
            amount: Token amount
            partition: Token partition (class_a, class_b)
            private_key_name: Private key name in Azure Key Vault
            
        Returns:
            Transfer result
        """
        try:
            # Get sender account
            sender = await self._get_account(private_key_name)
            
            # Check if sender address matches account
            if sender.address.lower() != from_address.lower():
                raise ValueError(f"Sender address does not match account: {sender.address} != {from_address}")
            
            # Initialize token contract
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            
            # Determine partition
            if partition == 'class_a':
                partition_bytes = token_contract.functions.PARTITION_CLASS_A().call()
            elif partition == 'class_b':
                partition_bytes = token_contract.functions.PARTITION_CLASS_B().call()
            else:
                raise ValueError(f"Invalid partition: {partition}")
            
            # Convert amount to wei
            amount_wei = int(amount * 10**18)
            
            # Transfer tokens
            nonce = self.w3.eth.get_transaction_count(sender.address)
            tx_hash = token_contract.functions.transferByPartition(
                partition_bytes,
                to_address,
                amount_wei,
                b''
            ).transact({
                'from': sender.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "status": "success",
                "message": "Tokens transferred successfully",
                "from_address": from_address,
                "to_address": to_address,
                "amount": amount,
                "partition": partition,
                "transaction_hash": tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to transfer tokens: {str(e)}")
            raise
    
    async def controller_transfer(
        self,
        token_address: str,
        from_address: str,
        to_address: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Forced transfer by controller (for regulatory compliance)
        
        Args:
            token_address: Token contract address
            from_address: Sender wallet address
            to_address: Recipient wallet address
            amount: Token amount
            
        Returns:
            Transfer result
        """
        try:
            # Get controller account
            controller = await self._get_account('CONTROLLER_PRIVATE_KEY')
            
            # Initialize token contract
            token_contract = self.w3.eth.contract(address=token_address, abi=self.token_abi)
            
            # Convert amount to wei
            amount_wei = int(amount * 10**18)
            
            # Controller transfer
            nonce = self.w3.eth.get_transaction_count(controller.address)
            tx_hash = token_contract.functions.controllerTransfer(
                from_address,
                to_address,
                amount_wei,
                b'',
                b'Regulatory compliance transfer'
            ).transact({
                'from': controller.address,
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': self.chain_id
            })
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "status": "success",
                "message": "Controller transfer executed successfully",
                "from_address": from_address,
                "to_address": to_address,
                "amount": amount,
                "transaction_hash": tx_receipt.transactionHash.hex()
            }
        
        except Exception as e:
            logger.error(f"Failed to execute controller transfer: {str(e)}")
            raise
