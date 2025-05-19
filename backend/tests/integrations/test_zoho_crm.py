"""
Tests for the Zoho CRM integration
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio
import time

from integrations.zoho.zoho_crm import ZohoCRM

class TestZohoCRM:
    """Test suite for Zoho CRM integration"""
    
    @pytest.fixture
    def zoho_crm(self, mock_env_vars):
        """Create a ZohoCRM instance for testing"""
        config = {
            'client_id': 'test-zoho-client-id',
            'client_secret': 'test-zoho-client-secret',
            'redirect_uri': 'https://test.proppulse.ai/zoho/callback'
        }
        return ZohoCRM(config)
    
    def test_get_auth_url(self, zoho_crm):
        """Test generating OAuth2 authorization URL"""
        # Get auth URL
        auth_url = zoho_crm.get_auth_url()
        
        # Verify URL
        assert 'https://accounts.zoho.eu/oauth/v2/auth' in auth_url
        assert 'client_id=test-zoho-client-id' in auth_url
        assert 'redirect_uri=https%3A%2F%2Ftest.proppulse.ai%2Fzoho%2Fcallback' in auth_url
        assert 'scope=ZohoCRM.modules.ALL%2CZohoCRM.settings.ALL' in auth_url
        
        # Test with state parameter
        auth_url = zoho_crm.get_auth_url('test-state')
        assert 'state=test-state' in auth_url
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens(self, zoho_crm, mock_zoho):
        """Test exchanging authorization code for tokens"""
        mock_post, _ = mock_zoho
        
        # Exchange code for tokens
        token_data = await zoho_crm.exchange_code_for_tokens('test-auth-code')
        
        # Verify token data
        assert token_data['access_token'] == 'test-access-token'
        assert token_data['refresh_token'] == 'test-refresh-token'
        assert token_data['expires_in'] == 3600
        
        # Verify Zoho API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert 'https://accounts.zoho.eu/oauth/v2/token' in args[0]
        assert kwargs['params']['client_id'] == 'test-zoho-client-id'
        assert kwargs['params']['client_secret'] == 'test-zoho-client-secret'
        assert kwargs['params']['grant_type'] == 'authorization_code'
        assert kwargs['params']['code'] == 'test-auth-code'
    
    @pytest.mark.asyncio
    async def test_refresh_access_token(self, zoho_crm, mock_zoho):
        """Test refreshing access token"""
        mock_post, _ = mock_zoho
        
        # Set refresh token
        zoho_crm.refresh_token = 'test-refresh-token'
        
        # Refresh access token
        token_data = await zoho_crm.refresh_access_token()
        
        # Verify token data
        assert token_data['access_token'] == 'test-access-token'
        assert token_data['expires_in'] == 3600
        
        # Verify Zoho API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert 'https://accounts.zoho.eu/oauth/v2/token' in args[0]
        assert kwargs['params']['client_id'] == 'test-zoho-client-id'
        assert kwargs['params']['client_secret'] == 'test-zoho-client-secret'
        assert kwargs['params']['grant_type'] == 'refresh_token'
        assert kwargs['params']['refresh_token'] == 'test-refresh-token'
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_no_refresh_token(self, zoho_crm):
        """Test refreshing access token without refresh token"""
        # Clear refresh token
        zoho_crm.refresh_token = None
        
        # Attempt to refresh access token
        with pytest.raises(Exception) as excinfo:
            await zoho_crm.refresh_access_token()
        
        # Verify error
        assert 'No refresh token available' in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_ensure_valid_token_expired(self, zoho_crm):
        """Test ensuring valid token when token is expired"""
        # Set expired token
        zoho_crm.access_token = 'expired-token'
        zoho_crm.token_expiry = time.time() - 100  # Expired 100 seconds ago
        zoho_crm.refresh_token = 'test-refresh-token'
        
        # Mock refresh_access_token
        zoho_crm.refresh_access_token = MagicMock(return_value={'access_token': 'new-token', 'expires_in': 3600})
        
        # Ensure valid token
        token = await zoho_crm.ensure_valid_token()
        
        # Verify token
        assert token == 'new-token'
        
        # Verify refresh_access_token was called
        zoho_crm.refresh_access_token.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_valid_token_valid(self, zoho_crm):
        """Test ensuring valid token when token is still valid"""
        # Set valid token
        zoho_crm.access_token = 'valid-token'
        zoho_crm.token_expiry = time.time() + 1000  # Valid for 1000 more seconds
        
        # Mock refresh_access_token
        zoho_crm.refresh_access_token = MagicMock()
        
        # Ensure valid token
        token = await zoho_crm.ensure_valid_token()
        
        # Verify token
        assert token == 'valid-token'
        
        # Verify refresh_access_token was not called
        zoho_crm.refresh_access_token.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_api_request_get(self, zoho_crm, mock_zoho):
        """Test making GET API request"""
        _, mock_get = mock_zoho
        
        # Set valid token
        zoho_crm.access_token = 'valid-token'
        zoho_crm.token_expiry = time.time() + 1000
        
        # Make API request
        response = await zoho_crm.api_request('GET', 'Properties', {'filter': 'status:Available'})
        
        # Verify response
        assert 'data' in response
        assert len(response['data']) == 1
        assert response['data'][0]['Property_ID'] == 'PROP_001'
        
        # Verify Zoho API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert 'https://www.zohoapis.eu/crm/v2/Properties' in args[0]
        assert kwargs['headers']['Authorization'] == 'Zoho-oauthtoken valid-token'
        assert kwargs['params']['filter'] == 'status:Available'
    
    @pytest.mark.asyncio
    async def test_api_request_post(self, zoho_crm, mock_zoho):
        """Test making POST API request"""
        mock_post, _ = mock_zoho
        
        # Set valid token
        zoho_crm.access_token = 'valid-token'
        zoho_crm.token_expiry = time.time() + 1000
        
        # Make API request
        data = {
            'data': [
                {
                    'Project_Name': 'Test Project',
                    'Developer': {'id': 'ACC_001'},
                    'Size_ft2': 1000
                }
            ]
        }
        response = await zoho_crm.api_request('POST', 'Properties', data)
        
        # Verify response
        assert 'data' in response
        assert len(response['data']) == 1
        assert response['data'][0]['id'] == 'test-record-id'
        
        # Verify Zoho API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert 'https://www.zohoapis.eu/crm/v2/Properties' in args[0]
        assert kwargs['headers']['Authorization'] == 'Zoho-oauthtoken valid-token'
        assert kwargs['json'] == data
    
    @pytest.mark.asyncio
    async def test_api_request_unsupported_method(self, zoho_crm):
        """Test making API request with unsupported method"""
        # Set valid token
        zoho_crm.access_token = 'valid-token'
        zoho_crm.token_expiry = time.time() + 1000
        
        # Attempt to make API request with unsupported method
        with pytest.raises(ValueError) as excinfo:
            await zoho_crm.api_request('PATCH', 'Properties', {})
        
        # Verify error
        assert 'Unsupported HTTP method' in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_property(self, zoho_crm):
        """Test getting property details"""
        # Mock api_request
        zoho_crm.api_request = MagicMock(return_value={
            'data': [
                {
                    'id': 'PROP_001',
                    'Project_Name': 'Test Project',
                    'Developer': {'name': 'Test Developer'},
                    'Size_ft2': 1000
                }
            ]
        })
        
        # Get property
        property_data = await zoho_crm.get_property('PROP_001')
        
        # Verify property data
        assert property_data['id'] == 'PROP_001'
        assert property_data['Project_Name'] == 'Test Project'
        assert property_data['Developer']['name'] == 'Test Developer'
        
        # Verify api_request was called
        zoho_crm.api_request.assert_called_once_with('GET', 'Properties/PROP_001')
    
    @pytest.mark.asyncio
    async def test_create_property(self, zoho_crm):
        """Test creating a property"""
        # Mock api_request
        zoho_crm.api_request = MagicMock(return_value={
            'data': [
                {
                    'id': 'PROP_002',
                    'Project_Name': 'New Project'
                }
            ]
        })
        
        # Create property
        property_data = {
            'Project_Name': 'New Project',
            'Developer': {'id': 'ACC_001'},
            'Size_ft2': 1200
        }
        created_property = await zoho_crm.create_property(property_data)
        
        # Verify created property
        assert created_property['id'] == 'PROP_002'
        assert created_property['Project_Name'] == 'New Project'
        
        # Verify api_request was called
        zoho_crm.api_request.assert_called_once()
        args, kwargs = zoho_crm.api_request.call_args
        assert args[0] == 'POST'
        assert args[1] == 'Properties'
        assert kwargs['data']['data'][0] == property_data
