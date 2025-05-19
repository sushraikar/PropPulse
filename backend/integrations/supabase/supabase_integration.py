"""
Supabase integration for PropPulse
"""
from typing import Dict, Any, List, Optional
import os
import json
import asyncio
from datetime import datetime
import supabase

class SupabaseIntegration:
    """
    Supabase integration for PropPulse.
    
    Handles dashboard data storage and file storage for proposals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Supabase integration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Supabase configuration
        self.url = self.config.get('url', os.getenv('SUPABASE_URL'))
        self.key = self.config.get('key', os.getenv('SUPABASE_KEY'))
        
        # Initialize Supabase client
        self.client = supabase.create_client(self.url, self.key)
    
    async def store_proposal_data(self, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store proposal data in Supabase.
        
        Args:
            proposal_data: Proposal data to store
            
        Returns:
            Stored proposal data with ID
        """
        # Extract key fields
        proposal_id = proposal_data.get('proposal', {}).get('id')
        contact_id = proposal_data.get('proposal', {}).get('contact_id')
        
        if not proposal_id:
            raise ValueError("Proposal ID is required")
        
        # Format data for storage
        formatted_data = {
            'id': proposal_id,
            'contact_id': contact_id,
            'property_data': json.dumps(proposal_data.get('property', {})),
            'investment_metrics': json.dumps(proposal_data.get('investment_metrics', {})),
            'pdf_urls': json.dumps(proposal_data.get('pdf_urls', {})),
            'created_at': proposal_data.get('proposal', {}).get('created_at', datetime.utcnow().isoformat()),
            'status': proposal_data.get('proposal', {}).get('status', 'completed')
        }
        
        # Store data in Supabase
        response = self.client.table('proposals').insert(formatted_data).execute()
        
        # Check for errors
        if 'error' in response:
            raise Exception(f"Error storing proposal data: {response['error']}")
        
        return response.get('data', [{}])[0]
    
    async def get_proposal_data(self, proposal_id: str) -> Dict[str, Any]:
        """
        Get proposal data from Supabase.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Proposal data
        """
        # Query Supabase
        response = self.client.table('proposals').select('*').eq('id', proposal_id).execute()
        
        # Check for errors
        if 'error' in response:
            raise Exception(f"Error getting proposal data: {response['error']}")
        
        # Check if proposal exists
        if not response.get('data'):
            raise Exception(f"Proposal not found: {proposal_id}")
        
        # Parse JSON fields
        proposal_data = response.get('data', [{}])[0]
        
        if 'property_data' in proposal_data and isinstance(proposal_data['property_data'], str):
            proposal_data['property_data'] = json.loads(proposal_data['property_data'])
        
        if 'investment_metrics' in proposal_data and isinstance(proposal_data['investment_metrics'], str):
            proposal_data['investment_metrics'] = json.loads(proposal_data['investment_metrics'])
        
        if 'pdf_urls' in proposal_data and isinstance(proposal_data['pdf_urls'], str):
            proposal_data['pdf_urls'] = json.loads(proposal_data['pdf_urls'])
        
        return proposal_data
    
    async def get_client_proposals(self, contact_id: str) -> List[Dict[str, Any]]:
        """
        Get all proposals for a client.
        
        Args:
            contact_id: Client/contact ID
            
        Returns:
            List of proposal data
        """
        # Query Supabase
        response = self.client.table('proposals').select('*').eq('contact_id', contact_id).order('created_at', desc=True).execute()
        
        # Check for errors
        if 'error' in response:
            raise Exception(f"Error getting client proposals: {response['error']}")
        
        # Parse JSON fields
        proposals = []
        for proposal_data in response.get('data', []):
            if 'property_data' in proposal_data and isinstance(proposal_data['property_data'], str):
                proposal_data['property_data'] = json.loads(proposal_data['property_data'])
            
            if 'investment_metrics' in proposal_data and isinstance(proposal_data['investment_metrics'], str):
                proposal_data['investment_metrics'] = json.loads(proposal_data['investment_metrics'])
            
            if 'pdf_urls' in proposal_data and isinstance(proposal_data['pdf_urls'], str):
                proposal_data['pdf_urls'] = json.loads(proposal_data['pdf_urls'])
            
            proposals.append(proposal_data)
        
        return proposals
    
    async def upload_file(self, file_path: str, destination_path: str) -> Dict[str, Any]:
        """
        Upload a file to Supabase Storage.
        
        Args:
            file_path: Local file path
            destination_path: Destination path in Supabase Storage
            
        Returns:
            Upload response
        """
        # Extract bucket and file path
        parts = destination_path.split('/', 1)
        bucket = parts[0]
        file_name = parts[1] if len(parts) > 1 else os.path.basename(file_path)
        
        # Read file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Upload file
        response = self.client.storage.from_(bucket).upload(file_name, file_data)
        
        # Check for errors
        if 'error' in response:
            raise Exception(f"Error uploading file: {response['error']}")
        
        # Get public URL
        public_url = self.client.storage.from_(bucket).get_public_url(file_name)
        
        return {
            'path': destination_path,
            'url': public_url
        }
    
    async def get_file_url(self, file_path: str) -> str:
        """
        Get public URL for a file in Supabase Storage.
        
        Args:
            file_path: File path in Supabase Storage
            
        Returns:
            Public URL
        """
        # Extract bucket and file path
        parts = file_path.split('/', 1)
        bucket = parts[0]
        file_name = parts[1] if len(parts) > 1 else file_path
        
        # Get public URL
        return self.client.storage.from_(bucket).get_public_url(file_name)
