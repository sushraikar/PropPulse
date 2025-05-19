"""
OAuth2 callback handler for Zoho CRM integration
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
import os
from typing import Optional

from integrations.zoho.zoho_crm import ZohoCRM

router = APIRouter()

# Initialize Zoho CRM client
zoho_crm = ZohoCRM()

@router.get("/callback")
async def zoho_oauth_callback(code: str, state: Optional[str] = None):
    """
    Handle OAuth2 callback from Zoho CRM
    
    Args:
        code: Authorization code from Zoho
        state: Optional state parameter for CSRF protection
        
    Returns:
        Redirect to dashboard with success message
    """
    try:
        # Exchange code for tokens
        token_data = await zoho_crm.exchange_code_for_tokens(code)
        
        # Store refresh token securely (in a real implementation)
        # This would be stored in a database or secure storage
        refresh_token = token_data.get('refresh_token')
        
        # Redirect to dashboard with success message
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/settings?zoho_connected=true",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        # Redirect to dashboard with error message
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/settings?zoho_error={str(e)}",
            status_code=status.HTTP_302_FOUND
        )

@router.get("/auth-url")
async def get_zoho_auth_url(state: Optional[str] = None):
    """
    Get Zoho CRM OAuth2 authorization URL
    
    Args:
        state: Optional state parameter for CSRF protection
        
    Returns:
        Authorization URL
    """
    auth_url = zoho_crm.get_auth_url(state)
    return {"auth_url": auth_url}
