"""
Tests for the ROIcalcAgent
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from agents.roi_calc_agent.roi_calc_agent import ROIcalcAgent

class TestROIcalcAgent:
    """Test suite for ROIcalcAgent"""
    
    @pytest.fixture
    def roi_calc_agent(self):
        """Create a ROIcalcAgent instance for testing"""
        config = {
            'management_fee_pct': 15,
            'default_cagr': 7,
            'default_occupancy': 85
        }
        return ROIcalcAgent(config)
    
    @pytest.mark.asyncio
    async def test_process_missing_input(self, roi_calc_agent):
        """Test process with missing required input"""
        # Test with empty input
        result = await roi_calc_agent.process({})
        assert result['status'] == 'error'
        assert 'Missing required input' in result['error']
    
    @pytest.mark.asyncio
    async def test_process_missing_property_data(self, roi_calc_agent):
        """Test process with missing property price or size"""
        # Test with property data missing price and size
        result = await roi_calc_agent.process({
            'property_data': {
                'property_id': 'PROP_001',
                'name': 'Test Property'
            }
        })
        assert result['status'] == 'error'
        assert 'Missing required property data' in result['error']
    
    @pytest.mark.asyncio
    async def test_process_success(self, roi_calc_agent):
        """Test successful ROI calculation"""
        # Test with complete property data
        result = await roi_calc_agent.process({
            'property_data': {
                'property_id': 'PROP_001',
                'name': 'Test Property',
                'price': 1000000,
                'size_ft2': 1000,
                'view': 'Burj Khalifa'
            },
            'investment_params': {
                'occupancy': 80,
                'service_charge_per_sqft': 12,
                'cagr': 6
            }
        })
        
        # Verify result
        assert result['status'] == 'success'
        assert result['property_id'] == 'PROP_001'
        assert 'metrics' in result
        
        # Verify metrics
        metrics = result['metrics']
        assert 'adr' in metrics
        assert 'occupancy_percentage' in metrics
        assert 'gross_rental_income' in metrics
        assert 'service_charge_per_sqft' in metrics
        assert 'total_service_charge' in metrics
        assert 'management_fee' in metrics
        assert 'net_income' in metrics
        assert 'net_yield_percentage' in metrics
        assert 'irr_10yr' in metrics
        assert 'capital_appreciation_cagr' in metrics
        
        # Verify specific calculations
        assert metrics['occupancy_percentage'] == 80
        assert metrics['service_charge_per_sqft'] == 12
        assert metrics['capital_appreciation_cagr'] == 6
    
    def test_get_property_price(self, roi_calc_agent):
        """Test extracting property price from different formats"""
        # Test with direct price field
        price = roi_calc_agent._get_property_price({'price': 1000000})
        assert price == 1000000
        
        # Test with string price
        price = roi_calc_agent._get_property_price({'price': 'AED 1,000,000'})
        assert price == 1000000
        
        # Test with list_price_aed field
        price = roi_calc_agent._get_property_price({'list_price_aed': 1000000})
        assert price == 1000000
        
        # Test with pricing text
        price = roi_calc_agent._get_property_price({
            'pricing': [{'text': 'Price: AED 1,000,000. Payment plan: 20% down payment.'}]
        })
        assert price == 1000000
        
        # Test with no price information
        price = roi_calc_agent._get_property_price({'name': 'Test Property'})
        assert price is None
    
    def test_get_property_size(self, roi_calc_agent):
        """Test extracting property size from different formats"""
        # Test with direct size field
        size = roi_calc_agent._get_property_size({'size_ft2': 1000})
        assert size == 1000
        
        # Test with string size
        size = roi_calc_agent._get_property_size({'size': '1,000 sq ft'})
        assert size == 1000
        
        # Test with area field
        size = roi_calc_agent._get_property_size({'area': 1000})
        assert size == 1000
        
        # Test with details text
        size = roi_calc_agent._get_property_size({
            'details': [{'text': 'Luxury 2-bedroom apartment, 1,000 sq ft with premium finishes.'}]
        })
        assert size == 1000
        
        # Test with no size information
        size = roi_calc_agent._get_property_size({'name': 'Test Property'})
        assert size is None
    
    def test_calculate_adr(self, roi_calc_agent):
        """Test ADR calculation with different inputs"""
        # Test with developer's forecast
        adr = roi_calc_agent._calculate_adr(
            {'developer_adr': 900},
            {}
        )
        assert adr == 900
        
        # Test with developer's forecast in investment params
        adr = roi_calc_agent._calculate_adr(
            {'name': 'Test Property'},
            {'developer_adr': 900}
        )
        assert adr == 900
        
        # Test with market average and view premium
        adr = roi_calc_agent._calculate_adr(
            {'view': 'Burj Khalifa'},
            {'market_average_adr': 500}
        )
        assert adr == 750  # 500 * 1.5 (Burj Khalifa view premium)
        
        # Test with custom view premium
        adr = roi_calc_agent._calculate_adr(
            {'view': 'City'},
            {'market_average_adr': 500, 'view_premium': 1.4}
        )
        assert adr == 700  # 500 * 1.4 (custom premium)
    
    def test_calculate_gross_rental_income(self, roi_calc_agent):
        """Test gross rental income calculation"""
        income = roi_calc_agent._calculate_gross_rental_income(800, 85)
        assert income == 800 * 365 * 0.85
    
    def test_get_service_charge(self, roi_calc_agent):
        """Test service charge extraction with different inputs"""
        # Test with direct service charge field
        sc = roi_calc_agent._get_service_charge(
            {'service_charge_per_sqft': 12},
            {}
        )
        assert sc == 12
        
        # Test with service charge in investment params
        sc = roi_calc_agent._get_service_charge(
            {'name': 'Test Property'},
            {'service_charge_per_sqft': 12}
        )
        assert sc == 12
        
        # Test with pricing text
        sc = roi_calc_agent._get_service_charge(
            {'pricing': [{'text': 'Service charge: AED 12 per sq ft per year.'}]},
            {}
        )
        assert sc == 12
        
        # Test with default value
        sc = roi_calc_agent._get_service_charge(
            {'name': 'Test Property'},
            {}
        )
        assert sc == 15  # Default value
    
    def test_newton_raphson_irr(self, roi_calc_agent):
        """Test IRR calculation using Newton-Raphson method"""
        # Test with simple cash flow
        cash_flows = [-1000, 100, 100, 100, 1100]  # Initial investment + 3 years income + final sale
        irr = roi_calc_agent._newton_raphson_irr(cash_flows)
        
        # IRR should be around 10%
        assert 9.5 <= irr * 100 <= 10.5
