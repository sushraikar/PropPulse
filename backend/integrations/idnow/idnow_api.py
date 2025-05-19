"""
IDnow API integration for PropPulse KYC verification
"""
import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IDnowAPI:
    """
    IDnow API client for KYC verification
    
    Provides methods for:
    - Creating identification requests
    - Checking verification status
    - Retrieving verification results
    - Handling webhooks
    
    Supports VideoIdent + AML/PEP package (SDD-ECDD level)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the IDnow API client"""
        self.config = config or {}
        
        # API configuration
        self.is_sandbox = self.config.get('is_sandbox', True)
        self.company_id = self.config.get('company_id', os.getenv('IDNOW_COMPANY_ID'))
        self.api_key = self.config.get('api_key', os.getenv('IDNOW_API_KEY'))
        
        # Set base URL based on environment
        if self.is_sandbox:
            self.base_url = "https://api.test.idnow.de"
        else:
            self.base_url = "https://api.idnow.de"
        
        # Verification settings
        self.verification_type = self.config.get('verification_type', 'VIDEO_IDENT')
        self.aml_pep_check = self.config.get('aml_pep_check', True)
        
        # Jurisdiction settings
        self.reject_us_residents = self.config.get('reject_us_residents', True)
        self.fatf_high_risk_filter = self.config.get('fatf_high_risk_filter', True)
        self.gdpr_compliant = self.config.get('gdpr_compliant', True)
        
        # Cache for auth tokens
        self._auth_token = None
        self._token_expiry = None
    
    def _get_auth_token(self) -> str:
        """
        Get authentication token
        
        Returns:
            Authentication token
        """
        # Check if we have a valid token
        if self._auth_token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._auth_token
        
        # Get new token
        auth_url = f"{self.base_url}/api/v1/auth"
        
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key
        }
        
        data = {
            "companyId": self.company_id
        }
        
        try:
            response = requests.post(auth_url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            self._auth_token = result.get('token')
            
            # Set token expiry (1 hour)
            self._token_expiry = datetime.now() + timedelta(hours=1)
            
            return self._auth_token
        except Exception as e:
            logger.error(f"Error getting auth token: {str(e)}")
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
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._get_auth_token()}"
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
    
    def create_identification(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create identification request
        
        Args:
            user_data: User data for identification
                - firstName: First name
                - lastName: Last name
                - email: Email address
                - mobilePhone: Mobile phone number
                - birthDate: Birth date (YYYY-MM-DD)
                - nationality: Nationality (ISO 3166-1 alpha-3)
                - address: Address object
                    - street: Street
                    - houseNumber: House number
                    - zipCode: ZIP code
                    - city: City
                    - country: Country (ISO 3166-1 alpha-3)
                
        Returns:
            Identification data including ID and redirect URL
        """
        endpoint = "/api/v1/identifications"
        
        # Check for US residents if configured to reject
        if self.reject_us_residents:
            nationality = user_data.get('nationality', '')
            country = user_data.get('address', {}).get('country', '')
            
            if nationality == 'USA' or country == 'USA':
                raise ValueError("US residents are not supported at this time")
        
        # Prepare data
        data = {
            "companyId": self.company_id,
            "identificationProcess": self.verification_type,
            "amlPepCheck": self.aml_pep_check,
            "redirectUrl": self.config.get('redirect_url', 'https://app.proppulse.ai/kyc/callback'),
            "callbackUrl": self.config.get('callback_url', 'https://api.proppulse.ai/kyc/webhook'),
            "userData": user_data
        }
        
        # Add GDPR consent if enabled
        if self.gdpr_compliant:
            data["userDataProtection"] = {
                "privacyPolicyVersion": "1.0",
                "termsOfUseVersion": "1.0",
                "privacyPolicyAccepted": True,
                "termsOfUseAccepted": True
            }
        
        return self._make_request('POST', endpoint, data)
    
    def get_identification_status(self, identification_id: str) -> Dict[str, Any]:
        """
        Get identification status
        
        Args:
            identification_id: Identification ID
            
        Returns:
            Identification status data
        """
        endpoint = f"/api/v1/identifications/{identification_id}"
        return self._make_request('GET', endpoint)
    
    def get_identification_document(self, identification_id: str, document_type: str) -> Dict[str, Any]:
        """
        Get identification document
        
        Args:
            identification_id: Identification ID
            document_type: Document type (e.g., 'pdf', 'xml')
            
        Returns:
            Document data
        """
        endpoint = f"/api/v1/identifications/{identification_id}/document/{document_type}"
        return self._make_request('GET', endpoint)
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook data
        
        Args:
            webhook_data: Webhook data from IDnow
            
        Returns:
            Processed webhook data
        """
        try:
            identification_id = webhook_data.get('identificationId')
            status = webhook_data.get('status')
            result = webhook_data.get('result')
            
            # Get detailed identification data
            identification_data = self.get_identification_status(identification_id)
            
            # Check for AML/PEP results
            aml_pep_result = identification_data.get('amlPepResult', {})
            is_pep = aml_pep_result.get('isPep', False)
            is_sanctioned = aml_pep_result.get('isSanctioned', False)
            
            # Check for high-risk countries if filter is enabled
            is_high_risk = False
            if self.fatf_high_risk_filter:
                nationality = identification_data.get('userData', {}).get('nationality', '')
                country = identification_data.get('userData', {}).get('address', {}).get('country', '')
                
                high_risk_countries = self._get_fatf_high_risk_countries()
                is_high_risk = nationality in high_risk_countries or country in high_risk_countries
            
            # Prepare result
            processed_data = {
                'identification_id': identification_id,
                'status': status,
                'result': result,
                'is_pep': is_pep,
                'is_sanctioned': is_sanctioned,
                'is_high_risk': is_high_risk,
                'raw_data': webhook_data
            }
            
            return processed_data
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise
    
    def _get_fatf_high_risk_countries(self) -> List[str]:
        """
        Get FATF high-risk countries
        
        Returns:
            List of high-risk country codes (ISO 3166-1 alpha-3)
        """
        # This list should be updated regularly based on FATF publications
        # Current list as of May 2025
        return [
            'PRK',  # North Korea
            'IRN',  # Iran
            'MMR',  # Myanmar
            'SYR',  # Syria
            'YEM',  # Yemen
            'MLI',  # Mali
            'HTI',  # Haiti
            # Add other high-risk countries as needed
        ]
    
    def validate_webhook_signature(self, signature: str, payload: str) -> bool:
        """
        Validate webhook signature
        
        Args:
            signature: Signature from X-IDnow-Signature header
            payload: Raw request body
            
        Returns:
            True if signature is valid, False otherwise
        """
        # In a real implementation, this would validate the HMAC signature
        # For now, we'll return True in sandbox mode
        if self.is_sandbox:
            return True
        
        # TODO: Implement actual signature validation for production
        logger.warning("Webhook signature validation not implemented for production")
        return True
