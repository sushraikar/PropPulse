"""
Tests for the RiskDataIngestor module

This module tests the RiskDataIngestor functionality:
- Tests STR Global API integration
- Tests AED swap curve fetcher
- Tests DXB Rentals API integration
- Tests developer default history CSV parser
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

from agents.risk_data_ingestor.risk_data_ingestor import RiskDataIngestor
from db.models.risk_models import MarketMetric

class TestRiskDataIngestor:
    """Test suite for RiskDataIngestor"""
    
    @pytest.fixture
    def ingestor(self):
        """Create RiskDataIngestor instance for testing"""
        return RiskDataIngestor()
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session
    
    @patch('agents.risk_data_ingestor.risk_data_ingestor.requests.get')
    def test_fetch_str_global_data(self, mock_get, ingestor, mock_db_session):
        """Test fetching STR Global data"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'date': '2025-05-18', 'revpar': 850.5, 'adr': 950.2, 'region': 'Dubai'},
                {'date': '2025-05-18', 'revpar': 750.3, 'adr': 850.1, 'region': 'RAK'}
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = ingestor.fetch_str_global_data(mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['metrics']) == 4  # 2 metrics (revpar, adr) for 2 regions
        assert mock_db_session.add.call_count == 4
        assert mock_db_session.commit.call_count == 1
    
    @patch('agents.risk_data_ingestor.risk_data_ingestor.requests.get')
    def test_fetch_aed_swap_curve(self, mock_get, ingestor, mock_db_session):
        """Test fetching AED swap curve"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'rates': [
                {'tenor': '12M', 'rate': 0.0325},
                {'tenor': '3Y', 'rate': 0.0375}
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = ingestor.fetch_aed_swap_curve(mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['metrics']) == 2
        assert mock_db_session.add.call_count == 2
        assert mock_db_session.commit.call_count == 1
    
    @patch('agents.risk_data_ingestor.risk_data_ingestor.requests.get')
    def test_fetch_dxb_rentals_data(self, mock_get, ingestor, mock_db_session):
        """Test fetching DXB Rentals data"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'rental_index': [
                {'date': '2025-05-18', 'area': 'Dubai Marina', 'index': 125.5},
                {'date': '2025-05-18', 'area': 'Downtown Dubai', 'index': 135.2}
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = ingestor.fetch_dxb_rentals_data(mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['metrics']) == 2
        assert mock_db_session.add.call_count == 2
        assert mock_db_session.commit.call_count == 1
    
    @patch('builtins.open', new_callable=mock_open, read_data='developer_id,developer_name,default_date,severity_score,notes\n1,ABC Developers,2024-01-15,3,Late delivery\n2,XYZ Properties,2023-11-20,4,Financial issues')
    def test_parse_developer_default_history(self, mock_file, ingestor, mock_db_session):
        """Test parsing developer default history CSV"""
        # Call method
        result = ingestor.parse_developer_default_history('/path/to/csv', mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['metrics']) == 2
        assert mock_db_session.add.call_count == 2
        assert mock_db_session.commit.call_count == 1
    
    @patch.object(RiskDataIngestor, 'fetch_str_global_data')
    @patch.object(RiskDataIngestor, 'fetch_aed_swap_curve')
    @patch.object(RiskDataIngestor, 'fetch_dxb_rentals_data')
    def test_ingest_daily_data(self, mock_dxb, mock_aed, mock_str, ingestor, mock_db_session):
        """Test ingesting daily data"""
        # Mock return values
        mock_str.return_value = {'status': 'success', 'metrics': [1, 2]}
        mock_aed.return_value = {'status': 'success', 'metrics': [3, 4]}
        mock_dxb.return_value = {'status': 'success', 'metrics': [5, 6]}
        
        # Call method
        result = ingestor.ingest_daily_data(mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['total_metrics'] == 6
        assert mock_str.call_count == 1
        assert mock_aed.call_count == 1
        assert mock_dxb.call_count == 1
    
    @patch.object(RiskDataIngestor, 'ingest_daily_data')
    def test_historical_backfill(self, mock_ingest, ingestor, mock_db_session):
        """Test historical backfill"""
        # Mock return value
        mock_ingest.return_value = {'status': 'success', 'total_metrics': 6}
        
        # Call method
        result = ingestor.historical_backfill(mock_db_session, days=5)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['days_processed'] == 5
        assert result['total_metrics'] == 30  # 6 metrics * 5 days
        assert mock_ingest.call_count == 5
