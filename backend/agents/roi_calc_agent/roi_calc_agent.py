"""
ROIcalcAgent for PropPulse
Responsible for calculating investment metrics and ROI
"""
from typing import Dict, Any, List, Optional
import json
import math
from datetime import datetime

# Import base agent
from agents.base_agent import BaseAgent


class ROIcalcAgent(BaseAgent):
    """
    ROIcalcAgent calculates investment metrics and ROI for properties.
    
    Responsibilities:
    - Calculate ADR (Average Daily Rate)
    - Calculate Occupancy %
    - Calculate Gross Rental Income
    - Calculate Service Charge costs
    - Calculate Net Yield %
    - Calculate IRR (10-yr, pre-tax)
    - Calculate Projected Capital Appreciation (CAGR)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ROIcalcAgent"""
        super().__init__(config)
        # Default values from requirements
        self.default_management_fee_pct = self.get_config_value('management_fee_pct', 15)
        self.default_cagr = self.get_config_value('default_cagr', 7)
        self.default_occupancy = self.get_config_value('default_occupancy', 85)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate investment metrics for a property.
        
        Args:
            input_data: Dictionary containing:
                - property_data: Property details including price, size, etc.
                - investment_params: Optional custom investment parameters
                
        Returns:
            Dict containing calculated investment metrics
        """
        # Validate input
        required_keys = ['property_data']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: property_data'
            }
        
        property_data = input_data['property_data']
        investment_params = input_data.get('investment_params', {})
        
        try:
            # Extract required property data
            property_price = self._get_property_price(property_data)
            property_size = self._get_property_size(property_data)
            
            if property_price is None or property_size is None:
                return {
                    'status': 'error',
                    'error': 'Missing required property data: price or size'
                }
            
            # Get ADR (Average Daily Rate)
            adr = self._calculate_adr(property_data, investment_params)
            
            # Get Occupancy %
            occupancy = investment_params.get('occupancy', self.default_occupancy)
            
            # Calculate Gross Rental Income
            gross_rental_income = self._calculate_gross_rental_income(adr, occupancy)
            
            # Get Service Charge per ft²
            service_charge_per_sqft = self._get_service_charge(property_data, investment_params)
            
            # Calculate total service charge
            total_service_charge = service_charge_per_sqft * property_size
            
            # Calculate management fee
            management_fee_pct = investment_params.get('management_fee_pct', self.default_management_fee_pct)
            management_fee = (gross_rental_income * management_fee_pct) / 100
            
            # Calculate Net Income
            net_income = gross_rental_income - total_service_charge - management_fee
            
            # Calculate Net Yield %
            net_yield_pct = (net_income / property_price) * 100
            
            # Get CAGR (Capital Appreciation Growth Rate)
            cagr = investment_params.get('cagr', self.default_cagr)
            
            # Calculate IRR (10-yr, pre-tax)
            payment_schedule = self._get_payment_schedule(property_data, investment_params)
            irr = self._calculate_irr(payment_schedule, net_income, property_price, cagr)
            
            # Prepare results
            results = {
                'status': 'success',
                'property_id': property_data.get('property_id', 'unknown'),
                'metrics': {
                    'adr': round(adr, 2),
                    'occupancy_percentage': round(occupancy, 2),
                    'gross_rental_income': round(gross_rental_income, 2),
                    'service_charge_per_sqft': round(service_charge_per_sqft, 2),
                    'total_service_charge': round(total_service_charge, 2),
                    'management_fee': round(management_fee, 2),
                    'net_income': round(net_income, 2),
                    'net_yield_percentage': round(net_yield_pct, 2),
                    'irr_10yr': round(irr, 2),
                    'capital_appreciation_cagr': round(cagr, 2)
                },
                'inputs': {
                    'property_price': property_price,
                    'property_size': property_size,
                    'management_fee_pct': management_fee_pct,
                    'payment_schedule': payment_schedule
                }
            }
            
            return results
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error calculating ROI: {str(e)}'
            }
    
    def _get_property_price(self, property_data: Dict[str, Any]) -> Optional[float]:
        """
        Extract property price from property data.
        
        Args:
            property_data: Property details
            
        Returns:
            Property price as float or None if not found
        """
        # Try different possible keys for price
        for key in ['price', 'list_price', 'list_price_aed', 'price_aed', 'purchase_price']:
            if key in property_data:
                price = property_data[key]
                if isinstance(price, str):
                    # Remove currency symbols and commas
                    price = price.replace('AED', '').replace(',', '').strip()
                    return float(price)
                return float(price)
        
        # Try to extract from text
        if 'pricing' in property_data:
            pricing_text = property_data['pricing']
            if isinstance(pricing_text, list) and len(pricing_text) > 0:
                pricing_text = pricing_text[0].get('text', '')
            
            import re
            price_match = re.search(r'(?:AED|price:?)\s*([\d,]+)', pricing_text, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                return float(price_str)
        
        return None
    
    def _get_property_size(self, property_data: Dict[str, Any]) -> Optional[float]:
        """
        Extract property size from property data.
        
        Args:
            property_data: Property details
            
        Returns:
            Property size in square feet as float or None if not found
        """
        # Try different possible keys for size
        for key in ['size', 'size_ft2', 'area', 'area_sqft', 'sqft']:
            if key in property_data:
                size = property_data[key]
                if isinstance(size, str):
                    # Remove units and commas
                    size = size.replace('sq ft', '').replace('sqft', '').replace(',', '').strip()
                    return float(size)
                return float(size)
        
        # Try to extract from text
        if 'details' in property_data:
            details_text = property_data['details']
            if isinstance(details_text, list) and len(details_text) > 0:
                details_text = details_text[0].get('text', '')
            
            import re
            size_match = re.search(r'([\d,]+)\s*(?:sq\.?\s*ft|sqft)', details_text, re.IGNORECASE)
            if size_match:
                size_str = size_match.group(1).replace(',', '')
                return float(size_str)
        
        return None
    
    def _calculate_adr(self, property_data: Dict[str, Any], investment_params: Dict[str, Any]) -> float:
        """
        Calculate ADR (Average Daily Rate).
        
        Formula: developer's forecast if available, else market average × view premium factor
        
        Args:
            property_data: Property details
            investment_params: Investment parameters
            
        Returns:
            ADR value
        """
        # Check if developer's forecast is available
        if 'developer_adr' in property_data:
            return float(property_data['developer_adr'])
        
        if 'developer_adr' in investment_params:
            return float(investment_params['developer_adr'])
        
        # Otherwise, calculate based on market average and view premium
        market_average = investment_params.get('market_average_adr', 500)  # Default value
        
        # Determine view premium factor
        view_premium = 1.0  # Default (no premium)
        
        # Extract view information
        view = None
        if 'view' in property_data:
            view = property_data['view']
        elif 'details' in property_data:
            details_text = property_data['details']
            if isinstance(details_text, list) and len(details_text) > 0:
                details_text = details_text[0].get('text', '')
                
                # Check for view mentions
                import re
                view_match = re.search(r'view(?:s)? of ([^\.,]+)', details_text, re.IGNORECASE)
                if view_match:
                    view = view_match.group(1).strip()
        
        # Set premium based on view
        if view:
            view = view.lower()
            if 'burj khalifa' in view or 'downtown' in view:
                view_premium = 1.5
            elif 'sea' in view or 'ocean' in view or 'marina' in view:
                view_premium = 1.3
            elif 'park' in view or 'garden' in view:
                view_premium = 1.2
            elif 'city' in view or 'skyline' in view:
                view_premium = 1.1
        
        # Override with custom view premium if provided
        if 'view_premium' in investment_params:
            view_premium = float(investment_params['view_premium'])
        
        return market_average * view_premium
    
    def _calculate_gross_rental_income(self, adr: float, occupancy: float) -> float:
        """
        Calculate Gross Rental Income.
        
        Formula: ADR × 365 × Occupancy%
        
        Args:
            adr: Average Daily Rate
            occupancy: Occupancy percentage (0-100)
            
        Returns:
            Gross Rental Income
        """
        return adr * 365 * (occupancy / 100)
    
    def _get_service_charge(self, property_data: Dict[str, Any], investment_params: Dict[str, Any]) -> float:
        """
        Get Service Charge per square foot.
        
        Args:
            property_data: Property details
            investment_params: Investment parameters
            
        Returns:
            Service Charge per square foot
        """
        # Check if service charge is provided in property data or investment params
        if 'service_charge_per_sqft' in property_data:
            return float(property_data['service_charge_per_sqft'])
        
        if 'service_charge_per_sqft' in investment_params:
            return float(investment_params['service_charge_per_sqft'])
        
        # Extract from text if available
        if 'pricing' in property_data:
            pricing_text = property_data['pricing']
            if isinstance(pricing_text, list) and len(pricing_text) > 0:
                pricing_text = pricing_text[0].get('text', '')
                
                import re
                sc_match = re.search(r'service charge:?\s*(?:AED)?\s*([\d\.]+)(?:\s*per sq ft)?', pricing_text, re.IGNORECASE)
                if sc_match:
                    return float(sc_match.group(1))
        
        # Default value
        return 15.0  # AED 15 per sq ft (from requirements)
    
    def _get_payment_schedule(self, property_data: Dict[str, Any], investment_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get payment schedule for the property.
        
        Args:
            property_data: Property details
            investment_params: Investment parameters
            
        Returns:
            List of payment schedule items
        """
        property_price = self._get_property_price(property_data)
        
        # Check if payment schedule is provided in investment params
        if 'payment_schedule' in investment_params:
            return investment_params['payment_schedule']
        
        # Try to extract from property data
        if 'payment_plan' in property_data:
            payment_plan = property_data['payment_plan']
            if isinstance(payment_plan, list):
                return payment_plan
        
        # Extract from text if available
        payment_schedule = []
        if 'pricing' in property_data:
            pricing_text = property_data['pricing']
            if isinstance(pricing_text, list) and len(pricing_text) > 0:
                pricing_text = pricing_text[0].get('text', '')
                
                import re
                # Look for payment plan information
                plan_match = re.search(r'payment plan:?\s*(.+?)(?:\.|$)', pricing_text, re.IGNORECASE)
                if plan_match:
                    plan_text = plan_match.group(1)
                    
                    # Parse percentages
                    percentages = re.findall(r'(\d+)%', plan_text)
                    descriptions = re.findall(r'(\d+)%\s+([^,\.]+)', plan_text)
                    
                    if percentages:
                        # Create payment schedule based on percentages
                        for i, pct in enumerate(percentages):
                            description = "Payment " + str(i+1)
                            if i < len(descriptions):
                                description = descriptions[i][1].strip()
                            
                            payment_schedule.append({
                                'percentage': float(pct),
                                'amount': property_price * float(pct) / 100,
                                'description': description,
                                'year': 0  # Assume all payments in year 0 for simplicity
                            })
        
        # If no payment schedule found, create a default one
        if not payment_schedule:
            # Default: 20% down payment, 30% during construction, 50% on completion
            payment_schedule = [
                {
                    'percentage': 20,
                    'amount': property_price * 0.2,
                    'description': 'Down payment',
                    'year': 0
                },
                {
                    'percentage': 30,
                    'amount': property_price * 0.3,
                    'description': 'During construction',
                    'year': 0
                },
                {
                    'percentage': 50,
                    'amount': property_price * 0.5,
                    'description': 'On completion',
                    'year': 1
                }
            ]
        
        return payment_schedule
    
    def _calculate_irr(self, payment_schedule: List[Dict[str, Any]], annual_net_income: float, property_price: float, cagr: float) -> float:
        """
        Calculate IRR (Internal Rate of Return) for a 10-year period.
        
        Args:
            payment_schedule: List of payment schedule items
            annual_net_income: Annual net income
            property_price: Property purchase price
            cagr: Capital Appreciation Growth Rate percentage
            
        Returns:
            IRR percentage
        """
        # Create cash flow for 10 years
        cash_flows = []
        
        # Initial investments (negative cash flow)
        for payment in payment_schedule:
            year = payment.get('year', 0)
            
            # Extend cash_flows list if needed
            while len(cash_flows) <= year:
                cash_flows.append(0)
            
            # Add payment (negative cash flow)
            cash_flows[year] -= payment['amount']
        
        # Annual income for years 1-10
        for year in range(1, 11):
            # Extend cash_flows list if needed
            while len(cash_flows) <= year:
                cash_flows.append(0)
            
            # Add annual income
            cash_flows[year] += annual_net_income
            
            # For year 10, add property sale
            if year == 10:
                # Calculate future value: FV = PV * (1 + r)^n
                future_value = property_price * ((1 + cagr/100) ** 10)
                cash_flows[year] += future_value
        
        # Calculate IRR using Newton's method
        return self._newton_raphson_irr(cash_flows)
    
    def _newton_raphson_irr(self, cash_flows: List[float], guess: float = 0.1, tolerance: float = 1e-6, max_iterations: int = 100) -> float:
        """
        Calculate IRR using Newton-Raphson method.
        
        Args:
            cash_flows: List of cash flows
            guess: Initial guess for IRR
            tolerance: Convergence tolerance
            max_iterations: Maximum number of iterations
            
        Returns:
            IRR as percentage
        """
        rate = guess
        
        for _ in range(max_iterations):
            # Calculate NPV and its derivative
            npv = 0
            npv_derivative = 0
            
            for i, cf in enumerate(cash_flows):
                npv += cf / ((1 + rate) ** i)
                if i > 0:
                    npv_derivative -= i * cf / ((1 + rate) ** (i + 1))
            
            # Check for convergence
            if abs(npv) < tolerance:
                break
            
            # Update rate using Newton-Raphson formula
            rate = rate - npv / npv_derivative
            
            # Check for invalid rate
            if rate <= -1:
                rate = 0.1  # Reset to initial guess
        
        # Convert to percentage
        return rate * 100
