"""
Tests for the developer portal authentication and welcome wizard.

This module contains tests for:
1. Magic.Link authentication
2. Role-based access control
3. Welcome wizard form validation
4. Developer profile management
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ....main import app
from ....db.models.developer import Developer
from ....api.routes.auth import verify_magic_link_token

client = TestClient(app)

@pytest.fixture
def mock_magic_link():
    """Mock Magic.Link authentication service."""
    with patch("....api.routes.auth.MagicLinkClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.token.validate.return_value = {
            "email": "test@example.com",
            "issuer": "did:ethr:0x123456789",
            "publicAddress": "0x123456789",
            "claim": {
                "iat": 1620000000,
                "ext": 1620086400,
                "iss": "did:ethr:0x123456789",
                "sub": "test@example.com",
                "aud": "did:magic:123456789",
                "nbf": 1620000000,
                "tid": "123456789",
                "exp": 1620086400
            }
        }
        yield mock_instance

@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = MagicMock(spec=Session)
    
    # Mock developer query
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.first.return_value = None
    
    yield mock_session

def test_verify_magic_link_token(mock_magic_link):
    """Test verification of Magic.Link token."""
    # Arrange
    token = "test_token"
    
    # Act
    result = verify_magic_link_token(token)
    
    # Assert
    assert result["email"] == "test@example.com"
    assert result["issuer"] == "did:ethr:0x123456789"
    assert result["publicAddress"] == "0x123456789"
    mock_magic_link.token.validate.assert_called_once_with(token)

def test_login_endpoint(mock_magic_link, mock_db_session):
    """Test login endpoint with Magic.Link token."""
    # Arrange
    with patch("....api.routes.auth.get_db", return_value=mock_db_session):
        # Act
        response = client.post(
            "/api/auth/login",
            json={"token": "test_token"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

def test_welcome_wizard_validation():
    """Test welcome wizard form validation."""
    # Arrange
    valid_data = {
        "legal_name": "Test Developer LLC",
        "vat_reg_number": "123456789",
        "trade_license": "DLD-12345",
        "primary_contact_email": "contact@testdev.com",
        "primary_contact_whatsapp": "+971501234567",
        "support_phone": "+97142345678",
        "iban": "AE123456789012345678901",
        "escrow_iban": "AE987654321098765432109"
    }
    
    invalid_data = {
        "legal_name": "",  # Empty name
        "vat_reg_number": "123",  # Too short
        "trade_license": "DLD-12345",
        "primary_contact_email": "invalid-email",  # Invalid email
        "primary_contact_whatsapp": "12345",  # Invalid phone
        "support_phone": "+97142345678",
        "iban": "123",  # Invalid IBAN
        "escrow_iban": "AE987654321098765432109"
    }
    
    # Act & Assert - Valid data
    with patch("....api.routes.developer.get_db", return_value=mock_db_session):
        response = client.post(
            "/api/developer/profile",
            json=valid_data,
            headers={"Authorization": "Bearer test_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    # Act & Assert - Invalid data
    with patch("....api.routes.developer.get_db", return_value=mock_db_session):
        response = client.post(
            "/api/developer/profile",
            json=invalid_data,
            headers={"Authorization": "Bearer test_token"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "error" in data

def test_rbac_permissions():
    """Test role-based access control permissions."""
    # Arrange
    developer_admin_token = "developer_admin_token"
    staff_token = "staff_token"
    auditor_token = "auditor_token"
    
    # Mock token verification to return different roles
    def mock_verify_token(token):
        if token == developer_admin_token:
            return {"email": "admin@example.com", "role": "developer_admin"}
        elif token == staff_token:
            return {"email": "staff@example.com", "role": "staff"}
        elif token == auditor_token:
            return {"email": "auditor@example.com", "role": "auditor_readonly"}
        return None
    
    with patch("....api.routes.auth.verify_token", side_effect=mock_verify_token):
        # Act & Assert - developer_admin can access all endpoints
        response = client.get(
            "/api/developer/profile",
            headers={"Authorization": f"Bearer {developer_admin_token}"}
        )
        assert response.status_code == 200
        
        response = client.post(
            "/api/developer/profile",
            json={"legal_name": "Test Developer"},
            headers={"Authorization": f"Bearer {developer_admin_token}"}
        )
        assert response.status_code == 200
        
        # Act & Assert - staff can access but not modify
        response = client.get(
            "/api/developer/profile",
            headers={"Authorization": f"Bearer {staff_token}"}
        )
        assert response.status_code == 200
        
        response = client.post(
            "/api/developer/profile",
            json={"legal_name": "Test Developer"},
            headers={"Authorization": f"Bearer {staff_token}"}
        )
        assert response.status_code == 403
        
        # Act & Assert - auditor can only read
        response = client.get(
            "/api/developer/profile",
            headers={"Authorization": f"Bearer {auditor_token}"}
        )
        assert response.status_code == 200
        
        response = client.post(
            "/api/developer/profile",
            json={"legal_name": "Test Developer"},
            headers={"Authorization": f"Bearer {auditor_token}"}
        )
        assert response.status_code == 403
