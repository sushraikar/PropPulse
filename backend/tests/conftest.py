"""
Test configuration for PropPulse backend
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define fixtures and configuration for tests
@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-openai-key',
        'PINECONE_API_KEY': 'test-pinecone-key',
        'PINECONE_ENVIRONMENT': 'test-env',
        'PINECONE_INDEX_NAME': 'test-index',
        'ZOHO_CLIENT_ID': 'test-zoho-client-id',
        'ZOHO_CLIENT_SECRET': 'test-zoho-client-secret',
        'ZOHO_REDIRECT_URI': 'https://test.proppulse.ai/zoho/callback',
        'BITOASIS_API_KEY': 'test-bitoasis-key',
        'BITOASIS_API_SECRET': 'test-bitoasis-secret',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_KEY': 'test-supabase-key',
    }):
        yield

@pytest.fixture
def mock_openai():
    """Mock OpenAI API for testing"""
    with patch('openai.Embedding.create') as mock:
        # Configure the mock to return a valid response
        mock.return_value = {
            'data': [
                {
                    'embedding': [0.1] * 1536,
                    'index': 0,
                    'object': 'embedding'
                }
            ],
            'model': 'text-embedding-3-small',
            'object': 'list',
            'usage': {
                'prompt_tokens': 8,
                'total_tokens': 8
            }
        }
        yield mock

@pytest.fixture
def mock_pinecone():
    """Mock Pinecone for testing"""
    with patch('pinecone.init'), \
         patch('pinecone.list_indexes', return_value=['test-index']), \
         patch('pinecone.Index') as mock_index:
        
        # Configure the mock index
        mock_instance = MagicMock()
        mock_instance.upsert.return_value = {'upserted_count': 5}
        mock_instance.query.return_value = {
            'matches': [
                {
                    'id': 'test-chunk-1',
                    'score': 0.95,
                    'metadata': {
                        'document_id': 'test-doc-1',
                        'text': 'This is a test chunk',
                        'page_no': 1
                    }
                }
            ],
            'namespace': 'properties'
        }
        mock_instance.delete.return_value = {'deleted_count': 1}
        mock_instance.describe_index_stats.return_value = {
            'namespaces': {'properties': {'vector_count': 100}},
            'dimension': 1536,
            'index_fullness': 0.1
        }
        
        mock_index.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_supabase():
    """Mock Supabase for testing"""
    mock_client = MagicMock()
    
    # Mock table operations
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.execute.return_value = {
        'data': [
            {
                'id': 'test-proposal-1',
                'contact_id': 'test-contact-1',
                'property_data': '{"id":"PROP_001","name":"Test Property"}',
                'investment_metrics': '{"adr":850,"occupancy_percentage":85}',
                'pdf_urls': '{"en":"https://test.url/en.pdf"}',
                'created_at': '2025-05-19T00:00:00Z',
                'status': 'completed'
            }
        ]
    }
    
    # Mock storage operations
    mock_storage = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.upload.return_value = {'Key': 'test-file.pdf'}
    mock_bucket.get_public_url.return_value = 'https://test.url/test-file.pdf'
    mock_storage.from_.return_value = mock_bucket
    
    # Configure the mock client
    mock_client.table.return_value = mock_table
    mock_client.storage = mock_storage
    
    with patch('supabase.create_client', return_value=mock_client):
        yield mock_client

@pytest.fixture
def mock_zoho():
    """Mock Zoho CRM API for testing"""
    with patch('requests.post') as mock_post, \
         patch('requests.get') as mock_get:
        
        # Configure the mock responses
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'access_token': 'test-access-token',
                'refresh_token': 'test-refresh-token',
                'expires_in': 3600
            }
        )
        
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'data': [
                    {
                        'id': 'test-record-id',
                        'Property_ID': 'PROP_001',
                        'Project_Name': 'Test Project'
                    }
                ]
            }
        )
        
        yield (mock_post, mock_get)
