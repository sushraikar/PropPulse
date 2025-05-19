"""
Pinecone metadata updater for risk metrics

This module handles updating Pinecone vector store with risk metrics:
- Updates property metadata with risk_grade
- Updates property metadata with mean_irr and var_5
- Ensures metadata is searchable for risk-based queries
"""
import os
import logging
from typing import Dict, Any, List, Optional
import pinecone
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PineconeMetadataUpdater:
    """
    Pinecone metadata updater for risk metrics
    
    Updates Pinecone vector store with risk metrics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the PineconeMetadataUpdater"""
        self.config = config or {}
        
        # Azure Key Vault configuration
        self.key_vault_name = self.config.get('key_vault_name', os.getenv('KEY_VAULT_NAME'))
        self.key_vault_url = f"https://{self.key_vault_name}.vault.azure.net"
        
        # Pinecone configuration
        self.pinecone_index_name = self.config.get('pinecone_index_name', os.getenv('PINECONE_INDEX_NAME', 'proppulse'))
        
        # Initialize Azure Key Vault client
        try:
            credential = DefaultAzureCredential()
            self.key_vault_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
            logger.info(f"Initialized Azure Key Vault client for {self.key_vault_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault client: {str(e)}")
            self.key_vault_client = None
        
        # Initialize Pinecone client
        self._initialize_pinecone()
    
    async def get_secret(self, secret_name: str) -> str:
        """
        Get secret from Azure Key Vault
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value
        """
        try:
            if not self.key_vault_client:
                raise ValueError("Azure Key Vault client not initialized")
            
            secret = self.key_vault_client.get_secret(secret_name)
            return secret.value
        
        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {str(e)}")
            raise
    
    def _initialize_pinecone(self) -> None:
        """Initialize Pinecone client"""
        try:
            # Get API key from environment or Key Vault
            api_key = os.getenv('PINECONE_API_KEY')
            
            if not api_key and self.key_vault_client:
                api_key = await self.get_secret('PINECONE_API_KEY')
            
            if not api_key:
                logger.error("Pinecone API key not found")
                return
            
            # Initialize Pinecone
            pinecone.init(api_key=api_key, environment=os.getenv('PINECONE_ENVIRONMENT', 'us-west1-gcp'))
            
            # Check if index exists
            if self.pinecone_index_name not in pinecone.list_indexes():
                logger.error(f"Pinecone index {self.pinecone_index_name} not found")
                return
            
            # Connect to index
            self.index = pinecone.Index(self.pinecone_index_name)
            logger.info(f"Connected to Pinecone index {self.pinecone_index_name}")
        
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {str(e)}")
            self.index = None
    
    async def update_property_metadata(self, property_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update property metadata in Pinecone
        
        Args:
            property_id: Property ID
            metadata: Metadata to update
            
        Returns:
            Update result
        """
        try:
            if not self.index:
                self._initialize_pinecone()
                
                if not self.index:
                    return {
                        'status': 'error',
                        'message': "Pinecone index not initialized"
                    }
            
            # Get vector ID for property
            vector_id = f"property_{property_id}"
            
            # Update metadata
            self.index.update(
                id=vector_id,
                set_metadata=metadata
            )
            
            logger.info(f"Updated Pinecone metadata for property {property_id}: {metadata}")
            
            return {
                'status': 'success',
                'property_id': property_id,
                'vector_id': vector_id,
                'metadata': metadata
            }
        
        except Exception as e:
            logger.error(f"Failed to update Pinecone metadata: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to update Pinecone metadata: {str(e)}"
            }
    
    async def update_batch_property_metadata(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update metadata for multiple properties in Pinecone
        
        Args:
            updates: List of property updates, each with property_id and metadata
            
        Returns:
            Batch update result
        """
        try:
            if not self.index:
                self._initialize_pinecone()
                
                if not self.index:
                    return {
                        'status': 'error',
                        'message': "Pinecone index not initialized"
                    }
            
            # Process each update
            results = []
            for update in updates:
                property_id = update.get('property_id')
                metadata = update.get('metadata', {})
                
                if not property_id:
                    logger.warning(f"Skipping update with missing property_id: {update}")
                    continue
                
                # Update metadata
                result = await self.update_property_metadata(property_id, metadata)
                results.append(result)
            
            # Count successes and failures
            success_count = sum(1 for result in results if result.get('status') == 'success')
            failure_count = len(results) - success_count
            
            return {
                'status': 'success',
                'message': f"Batch update completed: {success_count} succeeded, {failure_count} failed",
                'total_updates': len(updates),
                'success_count': success_count,
                'failure_count': failure_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to update batch Pinecone metadata: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to update batch Pinecone metadata: {str(e)}"
            }
    
    async def query_by_risk_grade(self, risk_grade: str, limit: int = 10) -> Dict[str, Any]:
        """
        Query properties by risk grade
        
        Args:
            risk_grade: Risk grade to query (red, amber, green)
            limit: Maximum number of results
            
        Returns:
            Query results
        """
        try:
            if not self.index:
                self._initialize_pinecone()
                
                if not self.index:
                    return {
                        'status': 'error',
                        'message': "Pinecone index not initialized"
                    }
            
            # Query by metadata filter
            results = self.index.query(
                vector=[0] * 1536,  # Dummy vector for metadata-only query
                filter={
                    'risk_grade': risk_grade
                },
                top_k=limit,
                include_metadata=True
            )
            
            # Extract property IDs and metadata
            properties = []
            for match in results.get('matches', []):
                vector_id = match.get('id', '')
                
                # Extract property ID from vector ID
                property_id = vector_id.replace('property_', '') if vector_id.startswith('property_') else vector_id
                
                properties.append({
                    'property_id': property_id,
                    'score': match.get('score'),
                    'metadata': match.get('metadata', {})
                })
            
            return {
                'status': 'success',
                'risk_grade': risk_grade,
                'count': len(properties),
                'properties': properties
            }
        
        except Exception as e:
            logger.error(f"Failed to query by risk grade: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to query by risk grade: {str(e)}"
            }
