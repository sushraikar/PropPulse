"""
Tests for the DataUploadService and column mapping functionality.

This module contains tests for:
1. File validation and virus scanning
2. Drag-and-drop upload functionality
3. Column mapping with GPT-4o
4. Error handling and persistence
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock, mock_open
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ....main import app
from ....utils.file_validation import validate_file, scan_file_for_viruses
from ....api.routes.dev_upload import map_columns_with_gpt4o

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = MagicMock(spec=Session)
    
    # Mock query
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.first.return_value = None
    
    yield mock_session

@pytest.fixture
def sample_xlsx_content():
    """Sample XLSX file content for testing."""
    return b"mock xlsx content"

@pytest.fixture
def sample_pdf_content():
    """Sample PDF file content for testing."""
    return b"mock pdf content"

def test_file_validation():
    """Test file validation logic."""
    # Test valid PDF
    assert validate_file("test.pdf", 5 * 1024 * 1024, "application/pdf") is True
    
    # Test valid XLSX
    assert validate_file("test.xlsx", 2 * 1024 * 1024, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") is True
    
    # Test valid CSV
    assert validate_file("test.csv", 1 * 1024 * 1024, "text/csv") is True
    
    # Test valid IFC
    assert validate_file("test.ifc", 100 * 1024 * 1024, "application/x-step") is True
    
    # Test valid GLB
    assert validate_file("test.glb", 100 * 1024 * 1024, "model/gltf-binary") is True
    
    # Test file too large
    assert validate_file("test.pdf", 150 * 1024 * 1024, "application/pdf") is False
    
    # Test unsupported file type
    assert validate_file("test.exe", 1 * 1024 * 1024, "application/x-msdownload") is False

def test_virus_scanning():
    """Test virus scanning functionality."""
    # Mock ClamAV response
    with patch("subprocess.run") as mock_run:
        # Mock clean file
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b"test.pdf: OK"
        mock_run.return_value = mock_process
        
        assert scan_file_for_viruses("test.pdf") is True
        
        # Mock infected file
        mock_process.returncode = 1
        mock_process.stdout = b"test.pdf: Found Virus.Test FOUND"
        mock_run.return_value = mock_process
        
        assert scan_file_for_viruses("test.pdf") is False

def test_upload_endpoint(mock_db_session, sample_xlsx_content):
    """Test file upload endpoint."""
    # Mock file validation and virus scanning
    with patch("....api.routes.dev_upload.validate_file", return_value=True), \
         patch("....api.routes.dev_upload.scan_file_for_viruses", return_value=True), \
         patch("....api.routes.dev_upload.get_db", return_value=mock_db_session), \
         patch("builtins.open", mock_open(read_data=sample_xlsx_content)):
        
        # Mock file save
        with patch("os.path.exists", return_value=False), \
             patch("os.makedirs"):
            
            # Act
            response = client.post(
                "/api/dev/upload",
                files={"file": ("test.xlsx", sample_xlsx_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "file_id" in data

def test_column_mapping_with_gpt4o():
    """Test column mapping with GPT-4o."""
    # Sample Excel headers
    headers = ["Unit", "Tower", "Floor", "Type", "BHK", "Area (sq.ft)", "Price (AED)", "View Type"]
    
    # Mock OpenAI API response
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "unit_no": "Unit",
                        "tower": "Tower",
                        "floor": "Floor",
                        "unit_type": "Type",
                        "bedrooms": "BHK",
                        "size_ft2": "Area (sq.ft)",
                        "price": "Price (AED)",
                        "view": "View Type"
                    })
                }
            }
        ]
    }
    
    with patch("openai.ChatCompletion.create", return_value=mock_response):
        # Act
        mapping = map_columns_with_gpt4o(headers)
        
        # Assert
        assert mapping["unit_no"] == "Unit"
        assert mapping["tower"] == "Tower"
        assert mapping["floor"] == "Floor"
        assert mapping["unit_type"] == "Type"
        assert mapping["bedrooms"] == "BHK"
        assert mapping["size_ft2"] == "Area (sq.ft)"
        assert mapping["price"] == "Price (AED)"
        assert mapping["view"] == "View Type"

def test_failed_upload_persistence(mock_db_session, sample_pdf_content):
    """Test persistence of failed uploads."""
    # Mock file validation to fail
    with patch("....api.routes.dev_upload.validate_file", return_value=False), \
         patch("....api.routes.dev_upload.get_db", return_value=mock_db_session):
        
        # Act
        response = client.post(
            "/api/dev/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")},
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Assert
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        
        # Verify error was persisted
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

def test_resumable_upload(mock_db_session, sample_pdf_content):
    """Test resumable upload functionality."""
    # Mock chunk validation
    with patch("....api.routes.dev_upload.validate_chunk", return_value=True), \
         patch("....api.routes.dev_upload.get_db", return_value=mock_db_session), \
         patch("builtins.open", mock_open()), \
         patch("os.path.exists", return_value=True):
        
        # Act - Upload first chunk
        response = client.post(
            "/api/dev/upload/chunk",
            data={
                "resumableChunkNumber": 1,
                "resumableTotalChunks": 3,
                "resumableChunkSize": 1024 * 1024,
                "resumableTotalSize": 3 * 1024 * 1024,
                "resumableIdentifier": "test-identifier",
                "resumableFilename": "test.pdf",
                "resumableRelativePath": "test.pdf"
            },
            files={"file": ("blob", sample_pdf_content, "application/octet-stream")},
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Act - Check if upload is complete
        response = client.get(
            "/api/dev/upload/status",
            params={"identifier": "test-identifier"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["complete"] is False
        assert data["chunksUploaded"] == 1
        assert data["totalChunks"] == 3
