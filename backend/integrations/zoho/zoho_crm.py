"""
Zoho CRM integration for PropPulse
"""
import os
import json
import time
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode


class ZohoCRM:
    """
    Zoho CRM integration for PropPulse.
    
    Handles OAuth2 authentication and API interactions with Zoho CRM,
    including custom modules for Properties and Proposals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Zoho CRM integration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # OAuth2 configuration
        self.client_id = self.config.get('client_id', os.getenv('ZOHO_CLIENT_ID'))
        self.client_secret = self.config.get('client_secret', os.getenv('ZOHO_CLIENT_SECRET'))
        self.redirect_uri = self.config.get('redirect_uri', os.getenv('ZOHO_REDIRECT_URI', 'https://auth.proppulse.ai/zoho/callback'))
        self.refresh_token = self.config.get('refresh_token', os.getenv('ZOHO_REFRESH_TOKEN'))
        
        # API endpoints
        self.accounts_url = self.config.get('accounts_url', os.getenv('ZOHO_ACCOUNTS_URL', 'https://accounts.zoho.eu'))
        self.api_domain = self.config.get('api_domain', os.getenv('ZOHO_API_DOMAIN', 'https://www.zohoapis.eu'))
        self.api_version = self.config.get('api_version', 'v2')
        
        # Token management
        self.access_token = None
        self.token_expiry = 0
    
    def get_auth_url(self, state: Optional[str] = None) -> str:
        """
        Get the OAuth2 authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'access_type': 'offline',
            'prompt': 'consent',
            'scope': 'ZohoCRM.modules.ALL,ZohoCRM.settings.ALL'
        }
        
        if state:
            params['state'] = state
        
        return f"{self.accounts_url}/oauth/v2/auth?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from OAuth2 callback
            
        Returns:
            Dictionary containing tokens and related information
        """
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post(
            f"{self.accounts_url}/oauth/v2/token",
            params=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to exchange code for tokens: {response.text}")
        
        token_data = response.json()
        
        # Store tokens
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.token_expiry = time.time() + token_data.get('expires_in', 3600)
        
        return token_data
    
    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            Dictionary containing new access token and related information
        """
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        response = requests.post(
            f"{self.accounts_url}/oauth/v2/token",
            params=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to refresh access token: {response.text}")
        
        token_data = response.json()
        
        # Update tokens
        self.access_token = token_data.get('access_token')
        self.token_expiry = time.time() + token_data.get('expires_in', 3600)
        
        return token_data
    
    async def ensure_valid_token(self) -> str:
        """
        Ensure a valid access token is available, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        if not self.access_token or time.time() >= self.token_expiry:
            await self.refresh_access_token()
        
        return self.access_token
    
    async def api_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an authenticated request to the Zoho CRM API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Optional request data
            
        Returns:
            API response data
        """
        # Ensure valid token
        access_token = await self.ensure_valid_token()
        
        # Prepare request
        url = f"{self.api_domain}/crm/{self.api_version}/{endpoint}"
        headers = {
            'Authorization': f"Zoho-oauthtoken {access_token}",
            'Content-Type': 'application/json'
        }
        
        # Make request
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=data)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, params=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Handle response
        if response.status_code >= 400:
            raise Exception(f"API request failed: {response.text}")
        
        return response.json()
    
    async def get_property(self, property_id: str) -> Dict[str, Any]:
        """
        Get property details from Zoho CRM.
        
        Args:
            property_id: Property ID
            
        Returns:
            Property details
        """
        response = await self.api_request('GET', f"Properties/{property_id}")
        return response.get('data', [{}])[0]
    
    async def create_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new property in Zoho CRM.
        
        Args:
            property_data: Property data
            
        Returns:
            Created property details
        """
        data = {
            'data': [property_data]
        }
        response = await self.api_request('POST', 'Properties', data)
        return response.get('data', [{}])[0]
    
    async def update_property(self, property_id: str, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a property in Zoho CRM.
        
        Args:
            property_id: Property ID
            property_data: Updated property data
            
        Returns:
            Updated property details
        """
        data = {
            'data': [property_data]
        }
        response = await self.api_request('PUT', f"Properties/{property_id}", data)
        return response.get('data', [{}])[0]
    
    async def get_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        Get proposal details from Zoho CRM.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Proposal details
        """
        response = await self.api_request('GET', f"Proposals/{proposal_id}")
        return response.get('data', [{}])[0]
    
    async def create_proposal(self, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new proposal in Zoho CRM.
        
        Args:
            proposal_data: Proposal data
            
        Returns:
            Created proposal details
        """
        data = {
            'data': [proposal_data]
        }
        response = await self.api_request('POST', 'Proposals', data)
        return response.get('data', [{}])[0]
    
    async def update_proposal(self, proposal_id: str, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a proposal in Zoho CRM.
        
        Args:
            proposal_id: Proposal ID
            proposal_data: Updated proposal data
            
        Returns:
            Updated proposal details
        """
        data = {
            'data': [proposal_data]
        }
        response = await self.api_request('PUT', f"Proposals/{proposal_id}", data)
        return response.get('data', [{}])[0]
    
    async def search_properties(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for properties in Zoho CRM.
        
        Args:
            criteria: Search criteria
            
        Returns:
            List of matching properties
        """
        # Convert criteria to Zoho search format
        search_params = {
            'criteria': json.dumps(criteria)
        }
        
        response = await self.api_request('GET', 'Properties/search', search_params)
        return response.get('data', [])
    
    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Get contact details from Zoho CRM.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Contact details
        """
        response = await self.api_request('GET', f"Contacts/{contact_id}")
        return response.get('data', [{}])[0]
