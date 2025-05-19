"""
Zoho Sign integration for PropPulse DealSigner
"""
import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

from db.models.co_investment import CoInvestmentGroup, CapTable, SignStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZohoSignAPI:
    """
    Zoho Sign API client for document signing
    
    Provides methods for:
    - Creating and sending documents for signature
    - Checking signature status
    - Handling webhooks for status updates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Zoho Sign API client"""
        self.config = config or {}
        
        # API configuration
        self.client_id = self.config.get('client_id', os.getenv('ZOHO_CLIENT_ID'))
        self.client_secret = self.config.get('client_secret', os.getenv('ZOHO_CLIENT_SECRET'))
        self.refresh_token = self.config.get('refresh_token', os.getenv('ZOHO_REFRESH_TOKEN'))
        
        # Set base URL
        self.base_url = "https://sign.zoho.eu/api/v1"
        
        # Template paths
        self.template_dir = self.config.get('template_dir', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'templates'))
        
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
        auth_url = "https://accounts.zoho.eu/oauth/v2/token"
        
        params = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(auth_url, params=params)
            response.raise_for_status()
            
            result = response.json()
            self._auth_token = result.get('access_token')
            
            # Set token expiry (1 hour)
            self._token_expiry = datetime.now() + timedelta(hours=1)
            
            return self._auth_token
        except Exception as e:
            logger.error(f"Error getting auth token: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data
            files: Request files
            
        Returns:
            Response data
        """
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._get_auth_token()}"
        }
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method.upper() == 'POST':
                if files:
                    response = requests.post(url, headers=headers, data=data, files=files)
                else:
                    headers["Content-Type"] = "application/json"
                    response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                headers["Content-Type"] = "application/json"
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
    
    def create_document(self, template_name: str, document_name: str, merge_fields: Dict[str, str], signers: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Create document from template
        
        Args:
            template_name: Template name (e.g., 'syndicate_agreement', 'spa')
            document_name: Document name
            merge_fields: Merge fields for template
            signers: List of signers
                - name: Signer name
                - email: Signer email
                - role: Signer role (e.g., 'investor', 'admin')
            
        Returns:
            Document data
        """
        # Get template file
        template_path = os.path.join(self.template_dir, f"{template_name}.pdf")
        
        if not os.path.exists(template_path):
            raise ValueError(f"Template not found: {template_path}")
        
        # Prepare request data
        data = {
            "requests": {
                "request_name": document_name,
                "actions": []
            }
        }
        
        # Add signers
        for i, signer in enumerate(signers):
            action = {
                "action_type": "SIGN",
                "recipient_name": signer['name'],
                "recipient_email": signer['email'],
                "role": signer.get('role', 'signer'),
                "action_id": f"action_{i+1}",
                "private_notes": f"Please sign the {template_name} document",
                "signing_order": i+1
            }
            data["requests"]["actions"].append(action)
        
        # Add merge fields
        data["field_data"] = {
            "field_text_data": []
        }
        
        for key, value in merge_fields.items():
            field_data = {
                "field_name": key,
                "field_value": value
            }
            data["field_data"]["field_text_data"].append(field_data)
        
        # Prepare files
        files = {
            "file": (f"{template_name}.pdf", open(template_path, 'rb'), 'application/pdf')
        }
        
        # Make request
        endpoint = "/documents"
        return self._make_request('POST', endpoint, data=data, files=files)
    
    def send_document(self, document_id: str) -> Dict[str, Any]:
        """
        Send document for signature
        
        Args:
            document_id: Document ID
            
        Returns:
            Send result
        """
        endpoint = f"/documents/{document_id}/send"
        return self._make_request('POST', endpoint)
    
    def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """
        Get document status
        
        Args:
            document_id: Document ID
            
        Returns:
            Document status
        """
        endpoint = f"/documents/{document_id}"
        return self._make_request('GET', endpoint)
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Process webhook data
        
        Args:
            webhook_data: Webhook data from Zoho Sign
            
        Returns:
            Processed webhook data
        """
        try:
            document_id = webhook_data.get('document_id')
            action_id = webhook_data.get('action_id')
            action_status = webhook_data.get('action_status')
            action_type = webhook_data.get('action_type')
            
            # Map Zoho Sign status to our status
            status_mapping = {
                "SENT": SignStatus.SENT,
                "VIEWED": SignStatus.VIEWED,
                "SIGNED": SignStatus.SIGNED,
                "DECLINED": SignStatus.REJECTED,
                "EXPIRED": SignStatus.EXPIRED
            }
            
            sign_status = status_mapping.get(action_status, SignStatus.SENT)
            
            return {
                'document_id': document_id,
                'action_id': action_id,
                'action_status': action_status,
                'action_type': action_type,
                'sign_status': sign_status.value
            }
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise

class DealSigner:
    """
    DealSigner for PropPulse
    
    Handles document generation, signing, and status tracking for:
    - Syndicate Agreements
    - Sale and Purchase Agreements (SPAs)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the DealSigner"""
        self.config = config or {}
        
        # Initialize Zoho Sign API
        self.zoho_sign = ZohoSignAPI(self.config.get('zoho_sign_config'))
    
    async def generate_syndicate_agreement(self, co_investment_group_id: int, db_session) -> Dict[str, Any]:
        """
        Generate Syndicate Agreement for a co-investment group
        
        Args:
            co_investment_group_id: Co-investment group ID
            db_session: Database session
            
        Returns:
            Document generation result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == co_investment_group_id).first()
            
            if not co_investment_group:
                raise ValueError(f"Co-investment group not found: {co_investment_group_id}")
            
            # Get property data
            property_id = co_investment_group.property_id
            
            # Get cap table entries
            cap_table_entries = db_session.query(CapTable).filter(CapTable.co_investment_group_id == co_investment_group_id).all()
            
            if not cap_table_entries:
                raise ValueError(f"No investors found for co-investment group: {co_investment_group_id}")
            
            # Prepare document name
            document_name = f"Syndicate Agreement - {co_investment_group.name}"
            
            # Prepare merge fields
            merge_fields = {
                "syndicate_name": co_investment_group.name,
                "unit_no": property_id,  # This should be the unit number, not the property ID
                "purchase_price_aed": str(co_investment_group.target_raise),
                "token_contract": co_investment_group.token_contract_address or "To be deployed"
            }
            
            # Prepare signers
            signers = []
            
            # Add admin as first signer
            admin_email = self.config.get('admin_email', os.getenv('ADMIN_EMAIL', 'admin@proppulse.ai'))
            admin_name = self.config.get('admin_name', os.getenv('ADMIN_NAME', 'PropPulse Admin'))
            
            signers.append({
                "name": admin_name,
                "email": admin_email,
                "role": "admin"
            })
            
            # Add investors as signers
            for entry in cap_table_entries:
                signers.append({
                    "name": entry.investor_name,
                    "email": entry.investor_email,
                    "role": "investor"
                })
            
            # Create document
            document_result = self.zoho_sign.create_document(
                template_name="syndicate_agreement",
                document_name=document_name,
                merge_fields=merge_fields,
                signers=signers
            )
            
            # Get document ID
            document_id = document_result.get('document_id')
            
            if not document_id:
                raise ValueError(f"Failed to create document: {document_result}")
            
            # Send document
            send_result = self.zoho_sign.send_document(document_id)
            
            # Update cap table entries
            for entry in cap_table_entries:
                entry.sign_status = SignStatus.SENT
                entry.sign_document_id = document_id
            
            db_session.commit()
            
            return {
                "status": "success",
                "message": "Syndicate Agreement generated and sent for signature",
                "document_id": document_id,
                "document_name": document_name,
                "signers_count": len(signers)
            }
        
        except Exception as e:
            logger.error(f"Failed to generate Syndicate Agreement: {str(e)}")
            raise
    
    async def generate_spa(self, cap_table_id: int, db_session) -> Dict[str, Any]:
        """
        Generate Sale and Purchase Agreement (SPA) for an investor
        
        Args:
            cap_table_id: Cap table entry ID
            db_session: Database session
            
        Returns:
            Document generation result
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
            
            # Prepare document name
            document_name = f"SPA - {co_investment_group.name} - {cap_table_entry.investor_name}"
            
            # Prepare merge fields
            merge_fields = {
                "syndicate_name": co_investment_group.name,
                "unit_no": co_investment_group.property_id,  # This should be the unit number, not the property ID
                "investor_name": cap_table_entry.investor_name,
                "investor_wallet": cap_table_entry.investor_wallet_address or "To be provided",
                "share_percent": str(cap_table_entry.share_percentage),
                "purchase_price_aed": str(cap_table_entry.investment_amount),
                "token_contract": co_investment_group.token_contract_address or "To be deployed",
                "kyc_idnow_id": cap_table_entry.kyc_idnow_id or "Not completed"
            }
            
            # Prepare signers
            signers = []
            
            # Add admin as first signer
            admin_email = self.config.get('admin_email', os.getenv('ADMIN_EMAIL', 'admin@proppulse.ai'))
            admin_name = self.config.get('admin_name', os.getenv('ADMIN_NAME', 'PropPulse Admin'))
            
            signers.append({
                "name": admin_name,
                "email": admin_email,
                "role": "admin"
            })
            
            # Add investor as signer
            signers.append({
                "name": cap_table_entry.investor_name,
                "email": cap_table_entry.investor_email,
                "role": "investor"
            })
            
            # Create document
            document_result = self.zoho_sign.create_document(
                template_name="spa",
                document_name=document_name,
                merge_fields=merge_fields,
                signers=signers
            )
            
            # Get document ID
            document_id = document_result.get('document_id')
            
            if not document_id:
                raise ValueError(f"Failed to create document: {document_result}")
            
            # Send document
            send_result = self.zoho_sign.send_document(document_id)
            
            # Update cap table entry
            cap_table_entry.sign_status = SignStatus.SENT
            cap_table_entry.sign_document_id = document_id
            db_session.commit()
            
            return {
                "status": "success",
                "message": "SPA generated and sent for signature",
                "document_id": document_id,
                "document_name": document_name,
                "investor_name": cap_table_entry.investor_name,
                "investor_email": cap_table_entry.investor_email
            }
        
        except Exception as e:
            logger.error(f"Failed to generate SPA: {str(e)}")
            raise
    
    async def check_document_status(self, document_id: str) -> Dict[str, Any]:
        """
        Check document status
        
        Args:
            document_id: Document ID
            
        Returns:
            Document status
        """
        try:
            # Get document status
            status_result = self.zoho_sign.get_document_status(document_id)
            
            return {
                "status": "success",
                "document_id": document_id,
                "document_status": status_result.get('document_status'),
                "actions": status_result.get('actions', [])
            }
        
        except Exception as e:
            logger.error(f"Failed to check document status: {str(e)}")
            raise
    
    async def process_webhook(self, webhook_data: Dict[str, Any], db_session) -> Dict[str, Any]:
        """
        Process webhook data
        
        Args:
            webhook_data: Webhook data from Zoho Sign
            db_session: Database session
            
        Returns:
            Webhook processing result
        """
        try:
            # Process webhook data
            processed_data = self.zoho_sign.process_webhook(webhook_data)
            
            # Get document ID
            document_id = processed_data.get('document_id')
            
            # Find cap table entries with this document ID
            cap_table_entries = db_session.query(CapTable).filter(CapTable.sign_document_id == document_id).all()
            
            if not cap_table_entries:
                logger.warning(f"No cap table entries found for document ID: {document_id}")
                return {
                    "status": "warning",
                    "message": f"No cap table entries found for document ID: {document_id}",
                    "processed_data": processed_data
                }
            
            # Update cap table entries
            sign_status_str = processed_data.get('sign_status')
            sign_status = SignStatus[sign_status_str.upper()] if sign_status_str else None
            
            if sign_status:
                for entry in cap_table_entries:
                    entry.sign_status = sign_status
                    
                    if sign_status == SignStatus.SIGNED:
                        entry.sign_completed_at = datetime.now()
                
                db_session.commit()
            
            return {
                "status": "success",
                "message": "Webhook processed successfully",
                "document_id": document_id,
                "sign_status": sign_status_str,
                "updated_entries": len(cap_table_entries)
            }
        
        except Exception as e:
            logger.error(f"Failed to process webhook: {str(e)}")
            raise
