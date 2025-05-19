"""
Script to deploy PropPulseToken contracts to Polygon
"""
import os
import json
import asyncio
import argparse
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_private_key_from_keyvault(key_name: str) -> str:
    """
    Get private key from Azure Key Vault
    
    Args:
        key_name: Key name in Azure Key Vault
        
    Returns:
        Private key
    """
    key_vault_name = os.getenv('KEY_VAULT_NAME')
    key_vault_url = f"https://{key_vault_name}.vault.azure.net"
    
    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=key_vault_url, credential=credential)
        secret = client.get_secret(key_name)
        return secret.value
    except Exception as e:
        logger.error(f"Failed to get private key from Azure Key Vault: {str(e)}")
        raise

async def deploy_contract(
    web3: Web3,
    contract_path: str,
    constructor_args: list,
    private_key: str,
    chain_id: int
) -> dict:
    """
    Deploy contract to Polygon
    
    Args:
        web3: Web3 instance
        contract_path: Path to contract JSON file
        constructor_args: Constructor arguments
        private_key: Private key for deployment
        chain_id: Chain ID
        
    Returns:
        Deployment result
    """
    try:
        # Load contract ABI and bytecode
        with open(contract_path, 'r') as f:
            contract_json = json.load(f)
        
        abi = contract_json['abi']
        bytecode = contract_json['bytecode']
        
        # Get account from private key
        account = Account.from_key(private_key)
        
        # Create contract instance
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Prepare transaction
        nonce = web3.eth.get_transaction_count(account.address)
        
        # Estimate gas for deployment
        gas_estimate = contract.constructor(*constructor_args).estimate_gas({
            'from': account.address,
            'nonce': nonce
        })
        
        # Build transaction
        transaction = {
            'from': account.address,
            'gas': int(gas_estimate * 1.2),  # Add 20% buffer
            'gasPrice': web3.eth.gas_price,
            'nonce': nonce,
            'chainId': chain_id
        }
        
        # Sign transaction
        tx_create = contract.constructor(*constructor_args).build_transaction(transaction)
        signed_tx = account.sign_transaction(tx_create)
        
        # Send transaction
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for transaction receipt
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Get contract address
        contract_address = tx_receipt.contractAddress
        
        return {
            'status': 'success',
            'contract_address': contract_address,
            'transaction_hash': tx_receipt.transactionHash.hex(),
            'abi': abi
        }
    
    except Exception as e:
        logger.error(f"Failed to deploy contract: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

async def initialize_token(
    web3: Web3,
    contract_address: str,
    abi: list,
    token_name: str,
    token_symbol: str,
    owner_address: str,
    controller_address: str,
    property_id: str,
    unit_no: str,
    project_name: str,
    property_value: int,
    private_key: str,
    chain_id: int
) -> dict:
    """
    Initialize PropPulseToken
    
    Args:
        web3: Web3 instance
        contract_address: Contract address
        abi: Contract ABI
        token_name: Token name
        token_symbol: Token symbol
        owner_address: Owner address
        controller_address: Controller address
        property_id: Property ID
        unit_no: Unit number
        project_name: Project name
        property_value: Property value
        private_key: Private key for initialization
        chain_id: Chain ID
        
    Returns:
        Initialization result
    """
    try:
        # Get account from private key
        account = Account.from_key(private_key)
        
        # Create contract instance
        contract = web3.eth.contract(address=contract_address, abi=abi)
        
        # Prepare transaction
        nonce = web3.eth.get_transaction_count(account.address)
        
        # Build transaction
        transaction = {
            'from': account.address,
            'gas': 5000000,
            'gasPrice': web3.eth.gas_price,
            'nonce': nonce,
            'chainId': chain_id
        }
        
        # Sign transaction
        tx_create = contract.functions.initialize(
            token_name,
            token_symbol,
            owner_address,
            controller_address,
            property_id,
            unit_no,
            project_name,
            property_value
        ).build_transaction(transaction)
        signed_tx = account.sign_transaction(tx_create)
        
        # Send transaction
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for transaction receipt
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        return {
            'status': 'success',
            'transaction_hash': tx_receipt.transactionHash.hex()
        }
    
    except Exception as e:
        logger.error(f"Failed to initialize token: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Deploy PropPulseToken to Polygon')
    parser.add_argument('--property-id', required=True, help='Property ID')
    parser.add_argument('--unit-no', required=True, help='Unit number')
    parser.add_argument('--project-name', required=True, help='Project name')
    parser.add_argument('--property-value', type=int, required=True, help='Property value in AED')
    parser.add_argument('--chainstack-url', help='Chainstack URL')
    parser.add_argument('--chain-id', type=int, default=80001, help='Chain ID (default: 80001 for Mumbai testnet)')
    parser.add_argument('--use-keyvault', action='store_true', help='Use Azure Key Vault for private keys')
    args = parser.parse_args()
    
    # Get Chainstack URL
    chainstack_url = args.chainstack_url or os.getenv('CHAINSTACK_URL', 'https://nd-123-456-789.polygon-edge.chainstacklabs.com')
    
    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(chainstack_url))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    # Check connection
    if not web3.is_connected():
        logger.error(f"Failed to connect to Polygon node at {chainstack_url}")
        return
    
    logger.info(f"Connected to Polygon node at {chainstack_url}")
    
    # Get private keys
    if args.use_keyvault:
        deployer_private_key = await get_private_key_from_keyvault('DEPLOYER_PRIVATE_KEY')
        controller_private_key = await get_private_key_from_keyvault('CONTROLLER_PRIVATE_KEY')
    else:
        deployer_private_key = os.getenv('DEPLOYER_PRIVATE_KEY')
        controller_private_key = os.getenv('CONTROLLER_PRIVATE_KEY')
    
    if not deployer_private_key or not controller_private_key:
        logger.error("Private keys not found")
        return
    
    # Add 0x prefix if missing
    if not deployer_private_key.startswith('0x'):
        deployer_private_key = f"0x{deployer_private_key}"
    if not controller_private_key.startswith('0x'):
        controller_private_key = f"0x{controller_private_key}"
    
    # Get accounts
    deployer = Account.from_key(deployer_private_key)
    controller = Account.from_key(controller_private_key)
    
    logger.info(f"Deployer address: {deployer.address}")
    logger.info(f"Controller address: {controller.address}")
    
    # Prepare token name and symbol
    token_name = f"PropPulse {args.unit_no}"
    token_symbol = f"PP{args.unit_no.replace('-', '')}"
    
    # Deploy token contract
    contract_path = os.path.join(os.path.dirname(__file__), '..', 'contracts', 'build', 'PropPulseToken.json')
    
    logger.info(f"Deploying {token_name} ({token_symbol}) for property {args.property_id}")
    
    # Deploy contract
    deploy_result = await deploy_contract(
        web3=web3,
        contract_path=contract_path,
        constructor_args=[],
        private_key=deployer_private_key,
        chain_id=args.chain_id
    )
    
    if deploy_result['status'] == 'error':
        logger.error(f"Failed to deploy contract: {deploy_result['message']}")
        return
    
    logger.info(f"Contract deployed at {deploy_result['contract_address']}")
    
    # Initialize token
    init_result = await initialize_token(
        web3=web3,
        contract_address=deploy_result['contract_address'],
        abi=deploy_result['abi'],
        token_name=token_name,
        token_symbol=token_symbol,
        owner_address=deployer.address,
        controller_address=controller.address,
        property_id=args.property_id,
        unit_no=args.unit_no,
        project_name=args.project_name,
        property_value=args.property_value,
        private_key=deployer_private_key,
        chain_id=args.chain_id
    )
    
    if init_result['status'] == 'error':
        logger.error(f"Failed to initialize token: {init_result['message']}")
        return
    
    logger.info(f"Token initialized successfully")
    
    # Save deployment info
    deployment_info = {
        'token_name': token_name,
        'token_symbol': token_symbol,
        'contract_address': deploy_result['contract_address'],
        'deploy_transaction_hash': deploy_result['transaction_hash'],
        'init_transaction_hash': init_result['transaction_hash'],
        'property_id': args.property_id,
        'unit_no': args.unit_no,
        'project_name': args.project_name,
        'property_value': args.property_value,
        'deployer_address': deployer.address,
        'controller_address': controller.address,
        'abi': deploy_result['abi']
    }
    
    # Save to file
    output_file = f"deployment_{args.unit_no.replace('-', '')}.json"
    with open(output_file, 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    logger.info(f"Deployment info saved to {output_file}")

if __name__ == '__main__':
    asyncio.run(main())
