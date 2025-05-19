"""
Tests for the Supabase integration
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio
import json

from integrations.supabase.supabase_integration import SupabaseIntegration

class TestSupabaseIntegration:
    """Test suite for Supabase integration"""
    
    @pytest.fixture
    def supabase_integration(self, mock_env_vars, mock_supabase):
        """Create a SupabaseIntegration instance for testing"""
        config = {
            'url': 'https://test.supabase.co',
            'key': 'test-supabase-key'
        }
        return SupabaseIntegration(config)
    
    @pytest.mark.asyncio
    async def test_store_proposal_data(self, supabase_integration, mock_supabase):
        """Test storing proposal data in Supabase"""
        # Create test proposal data
        proposal_data = {
            'proposal': {
                'id': 'prop-123',
                'contact_id': 'contact-456',
                'created_at': '2025-05-19T00:00:00Z',
                'status': 'completed'
            },
            'property': {
                'id': 'PROP_001',
                'name': 'Test Property',
                'developer': 'Test Developer',
                'size_ft2': 1000,
                'price_aed': 1000000
            },
            'investment_metrics': {
                'adr': 850,
                'occupancy_percentage': 85,
                'net_yield_percentage': 6.8,
                'irr_10yr': 12.5
            },
            'pdf_urls': {
                'en': 'https://storage.proppulse.ai/proposals/prop-123.pdf',
                'ar': 'https://storage.proppulse.ai/proposals/prop-123_ar.pdf'
            }
        }
        
        # Store proposal data
        result = await supabase_integration.store_proposal_data(proposal_data)
        
        # Verify result
        assert result['id'] == 'test-proposal-1'
        
        # Verify Supabase API call
        mock_supabase.table.assert_called_with('proposals')
        mock_table = mock_supabase.table.return_value
        mock_table.insert.assert_called_once()
        args, kwargs = mock_table.insert.call_args
        assert kwargs['id'] == 'prop-123'
        assert kwargs['contact_id'] == 'contact-456'
        assert json.loads(kwargs['property_data'])['id'] == 'PROP_001'
        assert json.loads(kwargs['investment_metrics'])['adr'] == 850
        assert json.loads(kwargs['pdf_urls'])['en'] == 'https://storage.proppulse.ai/proposals/prop-123.pdf'
    
    @pytest.mark.asyncio
    async def test_store_proposal_data_missing_id(self, supabase_integration):
        """Test storing proposal data without proposal ID"""
        # Create test proposal data without ID
        proposal_data = {
            'proposal': {
                'contact_id': 'contact-456'
            },
            'property': {
                'id': 'PROP_001'
            }
        }
        
        # Attempt to store proposal data
        with pytest.raises(ValueError) as excinfo:
            await supabase_integration.store_proposal_data(proposal_data)
        
        # Verify error
        assert 'Proposal ID is required' in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_proposal_data(self, supabase_integration, mock_supabase):
        """Test getting proposal data from Supabase"""
        # Get proposal data
        result = await supabase_integration.get_proposal_data('test-proposal-1')
        
        # Verify result
        assert result['id'] == 'test-proposal-1'
        assert result['contact_id'] == 'test-contact-1'
        assert result['property_data']['id'] == 'PROP_001'
        assert result['property_data']['name'] == 'Test Property'
        assert result['investment_metrics']['adr'] == 850
        assert result['investment_metrics']['occupancy_percentage'] == 85
        assert result['pdf_urls']['en'] == 'https://test.url/en.pdf'
        
        # Verify Supabase API call
        mock_supabase.table.assert_called_with('proposals')
        mock_table = mock_supabase.table.return_value
        mock_table.select.assert_called_once_with('*')
        mock_table.eq.assert_called_once_with('id', 'test-proposal-1')
    
    @pytest.mark.asyncio
    async def test_get_client_proposals(self, supabase_integration, mock_supabase):
        """Test getting all proposals for a client"""
        # Get client proposals
        results = await supabase_integration.get_client_proposals('test-contact-1')
        
        # Verify results
        assert len(results) == 1
        assert results[0]['id'] == 'test-proposal-1'
        assert results[0]['contact_id'] == 'test-contact-1'
        assert results[0]['property_data']['id'] == 'PROP_001'
        
        # Verify Supabase API call
        mock_supabase.table.assert_called_with('proposals')
        mock_table = mock_supabase.table.return_value
        mock_table.select.assert_called_once_with('*')
        mock_table.eq.assert_called_once_with('contact_id', 'test-contact-1')
        mock_table.order.assert_called_once_with('created_at', desc=True)
    
    @pytest.mark.asyncio
    async def test_upload_file(self, supabase_integration, mock_supabase):
        """Test uploading a file to Supabase Storage"""
        # Mock open function
        with patch('builtins.open', MagicMock()):
            # Upload file
            result = await supabase_integration.upload_file(
                '/path/to/local/file.pdf',
                'proposals/test-file.pdf'
            )
        
        # Verify result
        assert result['path'] == 'proposals/test-file.pdf'
        assert result['url'] == 'https://test.url/test-file.pdf'
        
        # Verify Supabase API call
        mock_supabase.storage.from_.assert_called_with('proposals')
        mock_bucket = mock_supabase.storage.from_.return_value
        mock_bucket.upload.assert_called_once()
        mock_bucket.get_public_url.assert_called_once_with('test-file.pdf')
    
    @pytest.mark.asyncio
    async def test_get_file_url(self, supabase_integration, mock_supabase):
        """Test getting public URL for a file in Supabase Storage"""
        # Get file URL
        url = await supabase_integration.get_file_url('proposals/test-file.pdf')
        
        # Verify URL
        assert url == 'https://test.url/test-file.pdf'
        
        # Verify Supabase API call
        mock_supabase.storage.from_.assert_called_with('proposals')
        mock_bucket = mock_supabase.storage.from_.return_value
        mock_bucket.get_public_url.assert_called_once_with('test-file.pdf')
