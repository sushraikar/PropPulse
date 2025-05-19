"""
Tests for the API routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

from main import app

client = TestClient(app)

class TestHealthEndpoint:
    """Test suite for health check endpoint"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'version' in data
        assert 'timestamp' in data

class TestDocumentsEndpoint:
    """Test suite for documents endpoints"""
    
    def test_add_document_invalid_type(self):
        """Test adding document with invalid file type"""
        # Create test file with invalid extension
        files = {'file': ('test.doc', b'test content', 'application/msword')}
        data = {'project_code': 'TEST01', 'developer': 'Test Developer'}
        
        # Add document
        response = client.post("/documents/add", files=files, data=data)
        
        # Verify response
        assert response.status_code == 400
        assert 'Unsupported file type' in response.json()['detail']
    
    @patch('api.routes.documents.BackgroundTasks')
    def test_add_document_success(self, mock_background_tasks):
        """Test adding document successfully"""
        # Create test file
        files = {'file': ('test.pdf', b'test content', 'application/pdf')}
        data = {'project_code': 'TEST01', 'developer': 'Test Developer'}
        
        # Add document
        response = client.post("/documents/add", files=files, data=data)
        
        # Verify response
        assert response.status_code == 202
        data = response.json()
        assert data['status'] == 'processing'
        assert 'document_id' in data
        assert 'message' in data
    
    def test_get_document_not_found(self):
        """Test getting non-existent document"""
        response = client.get("/documents/invalid_id")
        
        # Verify response
        assert response.status_code == 404
        assert 'not found' in response.json()['detail']
    
    def test_get_document_success(self):
        """Test getting document successfully"""
        # Get document with valid ID format
        response = client.get("/documents/doc_20250519123456")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['document_id'] == 'doc_20250519123456'
        assert 'filename' in data
        assert 'file_type' in data
        assert 'project_code' in data
        assert 'developer' in data
        assert 'upload_timestamp' in data
        assert 'status' in data
        assert 'vector_ids' in data

class TestProposalsEndpoint:
    """Test suite for proposals endpoints"""
    
    def test_generate_proposal_invalid_language(self):
        """Test generating proposal with invalid language"""
        # Create test request
        request_data = {
            'contact_id': 'ZOHO_CONTACT_123',
            'property_ids': ['PROP_001', 'PROP_002'],
            'language': 'invalid_language',
            'investment_parameters': {}
        }
        
        # Generate proposal
        response = client.post("/proposals/propose", json=request_data)
        
        # Verify response
        assert response.status_code == 400
        assert 'Unsupported language' in response.json()['detail']
    
    @patch('api.routes.proposals.BackgroundTasks')
    def test_generate_proposal_success(self, mock_background_tasks):
        """Test generating proposal successfully"""
        # Create test request
        request_data = {
            'contact_id': 'ZOHO_CONTACT_123',
            'property_ids': ['PROP_001', 'PROP_002'],
            'language': 'english',
            'investment_parameters': {
                'adr': 900,
                'occupancy_percentage': 80
            }
        }
        
        # Generate proposal
        response = client.post("/proposals/propose", json=request_data)
        
        # Verify response
        assert response.status_code == 202
        data = response.json()
        assert data['status'] == 'processing'
        assert 'proposal_id' in data
        assert 'message' in data
        assert 'estimated_completion_time' in data
    
    def test_get_proposal_not_found(self):
        """Test getting non-existent proposal"""
        response = client.get("/proposals/invalid_id")
        
        # Verify response
        assert response.status_code == 404
        assert 'not found' in response.json()['detail']
    
    def test_get_proposal_success(self):
        """Test getting proposal successfully"""
        # Get proposal with valid ID format
        response = client.get("/proposals/prop_123abc456def")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data['proposal_id'] == 'prop_123abc456def'
        assert 'contact_id' in data
        assert 'property_ids' in data
        assert 'language' in data
        assert 'status' in data
        assert 'created_at' in data
        assert 'completed_at' in data
        assert 'pdf_url' in data
        assert 'investment_metrics' in data
        assert 'zoho_crm_sync_status' in data
