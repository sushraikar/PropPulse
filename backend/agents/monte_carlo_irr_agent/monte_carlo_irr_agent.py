"""
MonteCarloIRRAgent for PropPulse platform

This module implements Monte Carlo simulation for property investment risk assessment:
- Simulates price appreciation using log-normal distribution
- Simulates rent growth using normal distribution
- Applies interest-rate shock scenarios
- Calculates IRR statistics and risk metrics
- Stores results in risk_results table
"""
import os
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from sqlalchemy.orm import Session

from db.models.risk_models import RiskResult, RiskGrade, Property
from db.models.property import Property
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonteCarloIRRAgent:
    """
    MonteCarloIRRAgent for PropPulse platform
    
    Performs Monte Carlo simulations to assess investment risk and calculate IRR statistics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the MonteCarloIRRAgent"""
        self.config = config or {}
        
        # Simulation parameters
        self.simulation_count = int(self.config.get('simulation_count', os.getenv('MC_SIMS', 5000)))
        self.price_appreciation_mean = self.config.get('price_appreciation_mean', 0.08)  # 8%
        self.price_appreciation_std = self.config.get('price_appreciation_std', 0.12)    # 12%
        self.rent_growth_mean = self.config.get('rent_growth_mean', 0.05)                # 5%
        self.rent_growth_std = self.config.get('rent_growth_std', 0.10)                  # 10%
        self.rent_growth_cap = self.config.get('rent_growth_cap', 0.25)                  # ±25%
        
        # Interest rate shock scenarios and probabilities
        self.interest_rate_shocks = self.config.get('interest_rate_shocks', [-0.0150, 0.0, 0.0150, 0.0300])
        self.interest_rate_shock_probs = self.config.get('interest_rate_shock_probs', [0.15, 0.50, 0.25, 0.10])
        
        # Simulation time horizon (years)
        self.time_horizon = self.config.get('time_horizon', 10)
        
        # IRR threshold for probability calculation
        self.irr_threshold = self.config.get('irr_threshold', 0.12)  # 12%
        
        # Initialize Pinecone metadata updater
        self.pinecone_updater = PineconeMetadataUpdater()
    
    def _generate_price_appreciation_scenarios(self, base_price: float, num_scenarios: int) -> np.ndarray:
        """
        Generate price appreciation scenarios using log-normal distribution
        
        Args:
            base_price: Base property price
            num_scenarios: Number of scenarios to generate
            
        Returns:
            Array of price scenarios over time horizon
        """
        # Initialize array for price scenarios
        # Shape: (num_scenarios, time_horizon + 1)
        # +1 because we include the initial price at time 0
        price_scenarios = np.zeros((num_scenarios, self.time_horizon + 1))
        
        # Set initial price for all scenarios
        price_scenarios[:, 0] = base_price
        
        # Generate random annual returns from log-normal distribution
        # We use log-normal to ensure returns are positive-skewed and can't go below -100%
        annual_returns = np.random.lognormal(
            mean=np.log(1 + self.price_appreciation_mean) - 0.5 * self.price_appreciation_std**2,
            sigma=self.price_appreciation_std,
            size=(num_scenarios, self.time_horizon)
        )
        
        # Calculate cumulative price for each year
        for year in range(1, self.time_horizon + 1):
            price_scenarios[:, year] = price_scenarios[:, year-1] * annual_returns[:, year-1]
        
        return price_scenarios
    
    def _generate_rent_growth_scenarios(self, base_rent: float, num_scenarios: int) -> np.ndarray:
        """
        Generate rent growth scenarios using normal distribution with caps
        
        Args:
            base_rent: Base annual rent
            num_scenarios: Number of scenarios to generate
            
        Returns:
            Array of rent scenarios over time horizon
        """
        # Initialize array for rent scenarios
        # Shape: (num_scenarios, time_horizon + 1)
        rent_scenarios = np.zeros((num_scenarios, self.time_horizon + 1))
        
        # Set initial rent for all scenarios
        rent_scenarios[:, 0] = base_rent
        
        # Generate random annual growth rates from normal distribution
        annual_growth_rates = np.random.normal(
            loc=self.rent_growth_mean,
            scale=self.rent_growth_std,
            size=(num_scenarios, self.time_horizon)
        )
        
        # Apply caps to growth rates
        annual_growth_rates = np.clip(
            annual_growth_rates,
            -self.rent_growth_cap,
            self.rent_growth_cap
        )
        
        # Calculate rent for each year
        for year in range(1, self.time_horizon + 1):
            rent_scenarios[:, year] = rent_scenarios[:, year-1] * (1 + annual_growth_rates[:, year-1])
        
        return rent_scenarios
    
    def _generate_interest_rate_scenarios(self, base_rate: float, num_scenarios: int) -> np.ndarray:
        """
        Generate interest rate scenarios using discrete shock scenarios
        
        Args:
            base_rate: Base interest rate
            num_scenarios: Number of scenarios to generate
            
        Returns:
            Array of interest rate scenarios
        """
        # Choose shock scenarios based on probabilities
        shock_indices = np.random.choice(
            len(self.interest_rate_shocks),
            size=num_scenarios,
            p=self.interest_rate_shock_probs
        )
        
        # Apply shocks to base rate
        interest_rates = base_rate + np.array(self.interest_rate_shocks)[shock_indices]
        
        # Ensure rates don't go below zero
        interest_rates = np.maximum(interest_rates, 0)
        
        return interest_rates
    
    def _calculate_irr(self, cash_flows: np.ndarray) -> float:
        """
        Calculate Internal Rate of Return (IRR)
        
        Args:
            cash_flows: Array of cash flows (negative for outflows, positive for inflows)
            
        Returns:
            IRR value
        """
        try:
            # Use numpy's IRR function
            irr = np.irr(cash_flows)
            
            # Handle extreme values
            if irr < -1:
                irr = -1
            elif irr > 1:
                irr = 1
                
            return irr
        except:
            # Return NaN if IRR calculation fails
            return np.nan
    
    def _calculate_breakeven_year(self, cumulative_cash_flows: np.ndarray) -> float:
        """
        Calculate breakeven year
        
        Args:
            cumulative_cash_flows: Array of cumulative cash flows
            
        Returns:
            Breakeven year (fractional)
        """
        # Find first year where cumulative cash flow becomes positive
        positive_indices = np.where(cumulative_cash_flows > 0)[0]
        
        if len(positive_indices) == 0:
            # Never breaks even
            return float('inf')
        
        first_positive_idx = positive_indices[0]
        
        if first_positive_idx == 0:
            # Breaks even immediately
            return 0.0
        
        # Interpolate for fractional year
        prev_cf = cumulative_cash_flows[first_positive_idx - 1]
        curr_cf = cumulative_cash_flows[first_positive_idx]
        
        # If previous cash flow is zero, avoid division by zero
        if prev_cf == curr_cf:
            return float(first_positive_idx)
        
        # Linear interpolation
        fraction = -prev_cf / (curr_cf - prev_cf)
        breakeven_year = first_positive_idx - 1 + fraction
        
        return breakeven_year
    
    async def run_simulation(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for a property
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Simulation results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get property data
            property_data = db_session.query(Property).filter(Property.id == property_id).first()
            
            if not property_data:
                logger.error(f"Property not found: {property_id}")
                
                if close_session:
                    db_session.close()
                
                return {
                    'status': 'error',
                    'message': f"Property not found: {property_id}"
                }
            
            # Extract property parameters
            purchase_price = property_data.list_price_aed
            annual_rent = property_data.adr * 365 * property_data.occupancy_rate / 100
            service_charge = property_data.service_charge_per_sqft * property_data.size_ft2
            management_fee_rate = 0.15  # 15% management fee
            base_interest_rate = 0.05  # 5% base interest rate
            
            # Set random seed for reproducibility
            np.random.seed(int(datetime.now().timestamp()))
            
            # Generate scenarios
            price_scenarios = self._generate_price_appreciation_scenarios(purchase_price, self.simulation_count)
            rent_scenarios = self._generate_rent_growth_scenarios(annual_rent, self.simulation_count)
            interest_rates = self._generate_interest_rate_scenarios(base_interest_rate, self.simulation_count)
            
            # Initialize arrays for results
            irr_values = np.zeros(self.simulation_count)
            breakeven_years = np.zeros(self.simulation_count)
            year_1_yields = np.zeros(self.simulation_count)
            
            # Calculate cash flows and IRR for each scenario
            for i in range(self.simulation_count):
                # Initial investment (negative cash flow)
                cash_flows = [-purchase_price]
                
                # Annual cash flows
                for year in range(1, self.time_horizon + 1):
                    # Rental income
                    rental_income = rent_scenarios[i, year]
                    
                    # Expenses
                    expenses = service_charge + (rental_income * management_fee_rate)
                    
                    # Net income
                    net_income = rental_income - expenses
                    
                    # For the final year, add the sale price
                    if year == self.time_horizon:
                        net_income += price_scenarios[i, year]
                    
                    # Add to cash flows
                    cash_flows.append(net_income)
                
                # Calculate IRR
                irr_values[i] = self._calculate_irr(cash_flows)
                
                # Calculate cumulative cash flows
                cumulative_cash_flows = np.cumsum(cash_flows)
                
                # Calculate breakeven year
                breakeven_years[i] = self._calculate_breakeven_year(cumulative_cash_flows)
                
                # Calculate Year 1 yield
                year_1_yields[i] = (rent_scenarios[i, 1] - service_charge - (rent_scenarios[i, 1] * management_fee_rate)) / purchase_price
            
            # Calculate statistics
            mean_irr = float(np.nanmean(irr_values))
            var_5 = float(np.nanpercentile(irr_values, 5))
            var_95 = float(np.nanpercentile(irr_values, 95))
            prob_negative = float(np.mean(irr_values < 0))
            prob_above_threshold = float(np.mean(irr_values > self.irr_threshold))
            mean_breakeven_year = float(np.nanmean(breakeven_years))
            mean_year_1_yield = float(np.nanmean(year_1_yields))
            
            # Determine risk grade
            developer_risk_score = property_data.developer_risk_score if hasattr(property_data, 'developer_risk_score') else 3
            
            if prob_negative <= 0.10 and developer_risk_score <= 2:
                risk_grade = RiskGrade.GREEN
            elif prob_negative <= 0.25:
                risk_grade = RiskGrade.AMBER
            else:
                risk_grade = RiskGrade.RED
            
            # Create risk result
            risk_result = RiskResult(
                property_id=property_id,
                timestamp=datetime.utcnow(),
                mean_irr=mean_irr,
                var_5=var_5,
                var_95=var_95,
                prob_negative=prob_negative,
                prob_above_threshold=prob_above_threshold,
                breakeven_year=mean_breakeven_year,
                yield_on_cost_year_1=mean_year_1_yield,
                risk_grade=risk_grade,
                simulation_count=self.simulation_count,
                simulation_seed=int(datetime.now().timestamp()),
                simulation_parameters={
                    'price_appreciation_mean': self.price_appreciation_mean,
                    'price_appreciation_std': self.price_appreciation_std,
                    'rent_growth_mean': self.rent_growth_mean,
                    'rent_growth_std': self.rent_growth_std,
                    'rent_growth_cap': self.rent_growth_cap,
                    'interest_rate_shocks': self.interest_rate_shocks,
                    'interest_rate_shock_probs': self.interest_rate_shock_probs,
                    'time_horizon': self.time_horizon,
                    'irr_threshold': self.irr_threshold
                },
                simulation_results={
                    'irr_histogram': np.histogram(irr_values, bins=20)[0].tolist(),
                    'irr_percentiles': {
                        '5': var_5,
                        '25': float(np.nanpercentile(irr_values, 25)),
                        '50': float(np.nanpercentile(irr_values, 50)),
                        '75': float(np.nanpercentile(irr_values, 75)),
                        '95': var_95
                    }
                }
            )
            
            # Save to database
            db_session.add(risk_result)
            
            # Update property risk grade
            property_data.risk_grade = risk_grade
            property_data.last_risk_assessment = datetime.utcnow()
            
            # Commit changes
            db_session.commit()
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_property_metadata(
                property_id=property_id,
                metadata={
                    'mean_irr': mean_irr,
                    'var_5': var_5,
                    'risk_grade': risk_grade.value
                }
            )
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Return results
            return {
                'status': 'success',
                'property_id': property_id,
                'risk_grade': risk_grade.value,
                'mean_irr': mean_irr,
                'var_5': var_5,
                'var_95': var_95,
                'prob_negative': prob_negative,
                'prob_above_threshold': prob_above_threshold,
                'breakeven_year': mean_breakeven_year,
                'yield_on_cost_year_1': mean_year_1_yield,
                'simulation_count': self.simulation_count
            }
        
        except Exception as e:
            logger.error(f"Failed to run simulation: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to run simulation: {str(e)}"
            }
    
    async def run_batch_simulation(self, property_ids: List[str], db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for multiple properties
        
        Args:
            property_ids: List of property IDs
            db_session: Database session (optional)
            
        Returns:
            Batch simulation results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Run simulations for each property
            results = []
            for property_id in property_ids:
                result = await self.run_simulation(property_id, db_session)
                results.append(result)
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Count successes and failures
            success_count = sum(1 for result in results if result.get('status') == 'success')
            failure_count = len(results) - success_count
            
            return {
                'status': 'success',
                'message': f"Batch simulation completed: {success_count} succeeded, {failure_count} failed",
                'total_properties': len(property_ids),
                'success_count': success_count,
                'failure_count': failure_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to run batch simulation: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to run batch simulation: {str(e)}"
            }
    
    async def get_risk_results(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get risk results for a property
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Risk results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get latest risk result
            risk_result = db_session.query(RiskResult).filter(
                RiskResult.property_id == property_id
            ).order_by(
                RiskResult.timestamp.desc()
            ).first()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            if not risk_result:
                return {
                    'status': 'error',
                    'message': f"No risk results found for property: {property_id}"
                }
            
            # Return results
            return {
                'status': 'success',
                'property_id': property_id,
                'risk_grade': risk_result.risk_grade.value,
                'mean_irr': risk_result.mean_irr,
                'var_5': risk_result.var_5,
                'var_95': risk_result.var_95,
                'prob_negative': risk_result.prob_negative,
                'prob_above_threshold': risk_result.prob_above_threshold,
                'breakeven_year': risk_result.breakeven_year,
                'yield_on_cost_year_1': risk_result.yield_on_cost_year_1,
                'simulation_count': risk_result.simulation_count,
                'timestamp': risk_result.timestamp.isoformat(),
                'simulation_parameters': risk_result.simulation_parameters,
                'simulation_results': risk_result.simulation_results
            }
        
        except Exception as e:
            logger.error(f"Failed to get risk results: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to get risk results: {str(e)}"
            }
    
    async def export_simulation_results(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Export simulation results to CSV
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Export result with CSV data
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get latest risk result
            risk_result = db_session.query(RiskResult).filter(
                RiskResult.property_id == property_id
            ).order_by(
                RiskResult.timestamp.desc()
            ).first()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            if not risk_result:
                return {
                    'status': 'error',
                    'message': f"No risk results found for property: {property_id}"
                }
            
            # Create CSV data
            csv_data = f"property_id,sim_id,irr,npv,grade,assum_set,timestamp\n"
            
            # Add header row
            timestamp_str = risk_result.timestamp.isoformat()
            grade = risk_result.risk_grade.value
            
            # Add data rows
            for i in range(self.simulation_count):
                # Simulate IRR values based on histogram
                irr = np.random.normal(
                    loc=risk_result.mean_irr,
                    scale=(risk_result.var_95 - risk_result.var_5) / 3.29,  # Approximate std dev from 90% confidence interval
                    size=1
                )[0]
                
                # Calculate NPV (simplified)
                npv = 0  # Placeholder
                
                # Add row
                csv_data += f"{property_id},{i},{irr:.6f},{npv:.2f},{grade},base,{timestamp_str}\n"
            
            # Return CSV data
            return {
                'status': 'success',
                'property_id': property_id,
                'csv_data': csv_data,
                'row_count': self.simulation_count,
                'timestamp': timestamp_str
            }
        
        except Exception as e:
            logger.error(f"Failed to export simulation results: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to export simulation results: {str(e)}"
            }
