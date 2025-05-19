"""
Tests for the MonteCarloIRRAgent module

This module tests the MonteCarloIRRAgent functionality:
- Tests price appreciation scenario generation
- Tests rent growth scenario generation
- Tests interest rate scenario generation
- Tests IRR calculation
- Tests breakeven year calculation
- Tests full simulation workflow
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

from agents.monte_carlo_irr_agent.monte_carlo_irr_agent import MonteCarloIRRAgent
from db.models.risk_models import RiskResult, RiskGrade, Property

class TestMonteCarloIRRAgent:
    """Test suite for MonteCarloIRRAgent"""
    
    @pytest.fixture
    def agent(self):
        """Create MonteCarloIRRAgent instance for testing"""
        config = {
            'simulation_count': 100,  # Reduced for testing
            'price_appreciation_mean': 0.08,
            'price_appreciation_std': 0.12,
            'rent_growth_mean': 0.05,
            'rent_growth_std': 0.10,
            'rent_growth_cap': 0.25,
            'interest_rate_shocks': [-0.0150, 0.0, 0.0150, 0.0300],
            'interest_rate_shock_probs': [0.15, 0.50, 0.25, 0.10],
            'time_horizon': 10,
            'irr_threshold': 0.12
        }
        return MonteCarloIRRAgent(config)
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        session = MagicMock()
        
        # Mock property query
        mock_property = MagicMock(spec=Property)
        mock_property.id = 'UNO-611'
        mock_property.list_price_aed = 1000000
        mock_property.adr = 500
        mock_property.occupancy_rate = 80
        mock_property.service_charge_per_sqft = 15
        mock_property.size_ft2 = 800
        mock_property.developer_risk_score = 2
        
        session.query.return_value.filter.return_value.first.return_value = mock_property
        
        return session
    
    def test_generate_price_appreciation_scenarios(self, agent):
        """Test generating price appreciation scenarios"""
        # Call method
        base_price = 1000000
        num_scenarios = 100
        scenarios = agent._generate_price_appreciation_scenarios(base_price, num_scenarios)
        
        # Assertions
        assert scenarios.shape == (num_scenarios, agent.time_horizon + 1)
        assert np.all(scenarios[:, 0] == base_price)  # All initial prices should be base_price
        assert np.all(scenarios > 0)  # All prices should be positive
    
    def test_generate_rent_growth_scenarios(self, agent):
        """Test generating rent growth scenarios"""
        # Call method
        base_rent = 146000  # 500 * 365 * 0.8
        num_scenarios = 100
        scenarios = agent._generate_rent_growth_scenarios(base_rent, num_scenarios)
        
        # Assertions
        assert scenarios.shape == (num_scenarios, agent.time_horizon + 1)
        assert np.all(scenarios[:, 0] == base_rent)  # All initial rents should be base_rent
        assert np.all(scenarios > 0)  # All rents should be positive
    
    def test_generate_interest_rate_scenarios(self, agent):
        """Test generating interest rate scenarios"""
        # Call method
        base_rate = 0.05
        num_scenarios = 100
        rates = agent._generate_interest_rate_scenarios(base_rate, num_scenarios)
        
        # Assertions
        assert rates.shape == (num_scenarios,)
        assert np.all(rates >= 0)  # All rates should be non-negative
        
        # Check distribution of rates
        unique_rates = np.unique(rates)
        expected_rates = [base_rate + shock for shock in agent.interest_rate_shocks]
        for rate in unique_rates:
            assert any(np.isclose(rate, expected_rate) for expected_rate in expected_rates)
    
    def test_calculate_irr(self, agent):
        """Test calculating IRR"""
        # Test case 1: Simple investment with positive return
        cash_flows = np.array([-1000, 200, 200, 200, 200, 800])
        irr = agent._calculate_irr(cash_flows)
        assert 0.10 < irr < 0.15  # IRR should be around 12%
        
        # Test case 2: Investment with negative return
        cash_flows = np.array([-1000, 100, 100, 100, 100, 400])
        irr = agent._calculate_irr(cash_flows)
        assert irr < 0  # IRR should be negative
    
    def test_calculate_breakeven_year(self, agent):
        """Test calculating breakeven year"""
        # Test case 1: Breaks even in year 3
        cumulative_cash_flows = np.array([-1000, -800, -600, 100, 300, 500])
        breakeven_year = agent._calculate_breakeven_year(cumulative_cash_flows)
        assert 2 < breakeven_year < 3  # Should break even between years 2 and 3
        
        # Test case 2: Never breaks even
        cumulative_cash_flows = np.array([-1000, -900, -800, -700, -600, -500])
        breakeven_year = agent._calculate_breakeven_year(cumulative_cash_flows)
        assert breakeven_year == float('inf')  # Should never break even
        
        # Test case 3: Breaks even immediately
        cumulative_cash_flows = np.array([100, 200, 300, 400, 500])
        breakeven_year = agent._calculate_breakeven_year(cumulative_cash_flows)
        assert breakeven_year == 0.0  # Should break even immediately
    
    @patch.object(MonteCarloIRRAgent, '_generate_price_appreciation_scenarios')
    @patch.object(MonteCarloIRRAgent, '_generate_rent_growth_scenarios')
    @patch.object(MonteCarloIRRAgent, '_generate_interest_rate_scenarios')
    @patch.object(MonteCarloIRRAgent, 'pinecone_updater')
    async def test_run_simulation(self, mock_pinecone, mock_interest, mock_rent, mock_price, agent, mock_db_session):
        """Test running a full simulation"""
        # Mock scenario generation
        num_scenarios = 100
        time_horizon = 10
        
        mock_price.return_value = np.ones((num_scenarios, time_horizon + 1)) * 1000000 * 1.5  # 50% appreciation
        mock_rent.return_value = np.ones((num_scenarios, time_horizon + 1)) * 146000 * 1.2  # 20% rent growth
        mock_interest.return_value = np.ones(num_scenarios) * 0.05  # 5% interest rate
        
        # Mock Pinecone update
        mock_pinecone.update_property_metadata.return_value = {'status': 'success'}
        
        # Call method
        result = await agent.run_simulation('UNO-611', mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['property_id'] == 'UNO-611'
        assert 'mean_irr' in result
        assert 'var_5' in result
        assert 'prob_negative' in result
        assert 'risk_grade' in result
        
        # Check database operations
        assert mock_db_session.add.call_count == 2  # RiskResult and Property update
        assert mock_db_session.commit.call_count == 1
        
        # Check Pinecone update
        assert mock_pinecone.update_property_metadata.call_count == 1
    
    @patch.object(MonteCarloIRRAgent, 'run_simulation')
    async def test_run_batch_simulation(self, mock_run, agent, mock_db_session):
        """Test running batch simulation"""
        # Mock run_simulation
        mock_run.side_effect = [
            {'status': 'success', 'property_id': 'UNO-611'},
            {'status': 'success', 'property_id': 'UNO-612'},
            {'status': 'error', 'message': 'Test error', 'property_id': 'UNO-613'}
        ]
        
        # Call method
        property_ids = ['UNO-611', 'UNO-612', 'UNO-613']
        result = await agent.run_batch_simulation(property_ids, mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['total_properties'] == 3
        assert result['success_count'] == 2
        assert result['failure_count'] == 1
        assert len(result['results']) == 3
        
        # Check run_simulation calls
        assert mock_run.call_count == 3
    
    @patch.object(MonteCarloIRRAgent, 'pinecone_updater')
    async def test_get_risk_results(self, mock_pinecone, agent, mock_db_session):
        """Test getting risk results"""
        # Mock risk result query
        mock_risk_result = MagicMock(spec=RiskResult)
        mock_risk_result.property_id = 'UNO-611'
        mock_risk_result.mean_irr = 0.15
        mock_risk_result.var_5 = 0.05
        mock_risk_result.var_95 = 0.25
        mock_risk_result.prob_negative = 0.08
        mock_risk_result.prob_above_threshold = 0.75
        mock_risk_result.breakeven_year = 3.5
        mock_risk_result.yield_on_cost_year_1 = 0.06
        mock_risk_result.risk_grade = RiskGrade.GREEN
        mock_risk_result.simulation_count = 5000
        mock_risk_result.timestamp = datetime.utcnow()
        mock_risk_result.simulation_parameters = {'param1': 'value1'}
        mock_risk_result.simulation_results = {'result1': 'value1'}
        
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_risk_result
        
        # Call method
        result = await agent.get_risk_results('UNO-611', mock_db_session)
        
        # Assertions
        assert result['status'] == 'success'
        assert result['property_id'] == 'UNO-611'
        assert result['mean_irr'] == 0.15
        assert result['var_5'] == 0.05
        assert result['risk_grade'] == 'green'
        assert 'simulation_parameters' in result
        assert 'simulation_results' in result
