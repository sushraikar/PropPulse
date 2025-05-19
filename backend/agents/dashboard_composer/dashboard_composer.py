"""
DashboardComposer agent for PropPulse
Responsible for pushing proposal data to client dashboards
"""
from typing import Dict, Any, List, Optional
import os
import json
import asyncio
from datetime import datetime

# Import base agent
from agents.base_agent import BaseAgent


class DashboardComposer(BaseAgent):
    """
    DashboardComposer agent pushes proposal data to client dashboards.
    
    Responsibilities:
    - Format proposal data for dashboard display
    - Push JSON data and PDF links to Supabase
    - Organize data by client for VIP dashboard access
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the DashboardComposer agent"""
        super().__init__(config)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process proposal data and push to client dashboard.
        
        Args:
            input_data: Dictionary containing:
                - proposal_id: Unique identifier for the proposal
                - contact_id: Client/contact ID
                - property_data: Property information
                - roi_metrics: ROI calculation results
                - pdf_paths: Dictionary of PDF paths by language
                
        Returns:
            Dict containing:
                - proposal_id: The proposal ID
                - dashboard_data: Data pushed to dashboard
                - status: Processing status
        """
        # Validate input
        required_keys = ['proposal_id', 'contact_id', 'property_data', 'roi_metrics']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: proposal_id, contact_id, property_data, or roi_metrics'
            }
        
        proposal_id = input_data['proposal_id']
        contact_id = input_data['contact_id']
        property_data = input_data['property_data']
        roi_metrics = input_data['roi_metrics']
        pdf_paths = input_data.get('pdf_paths', {})
        
        try:
            # Format data for dashboard
            dashboard_data = self._format_dashboard_data(
                proposal_id, contact_id, property_data, roi_metrics, pdf_paths
            )
            
            # Push data to Supabase
            await self._push_to_supabase(dashboard_data)
            
            return {
                'status': 'success',
                'proposal_id': proposal_id,
                'contact_id': contact_id,
                'dashboard_data': dashboard_data
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error pushing to dashboard: {str(e)}'
            }
    
    def _format_dashboard_data(
        self, 
        proposal_id: str, 
        contact_id: str, 
        property_data: Dict[str, Any], 
        roi_metrics: Dict[str, Any],
        pdf_paths: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Format data for dashboard display.
        
        Args:
            proposal_id: Proposal ID
            contact_id: Client/contact ID
            property_data: Property information
            roi_metrics: ROI calculation results
            pdf_paths: Dictionary of PDF paths by language
            
        Returns:
            Formatted dashboard data
        """
        # Extract property details
        property_id = property_data.get('property_id', 'unknown')
        property_name = property_data.get('name', 'Luxury Property')
        property_location = property_data.get('location', 'Dubai')
        property_developer = property_data.get('developer', 'Premium Developer')
        property_type = property_data.get('type', 'Apartment')
        property_size = property_data.get('size_ft2', 0)
        property_price = property_data.get('list_price_aed', 0)
        
        # Extract ROI metrics
        metrics = roi_metrics.get('metrics', {})
        
        # Convert PDF paths to public URLs
        pdf_urls = {}
        for language, path in pdf_paths.items():
            # In a real implementation, this would convert local paths to public URLs
            # For now, we'll use placeholder URLs
            pdf_urls[language] = f"https://storage.proppulse.ai/proposals/{os.path.basename(path)}"
        
        # Format dashboard data
        dashboard_data = {
            'proposal': {
                'id': proposal_id,
                'created_at': datetime.utcnow().isoformat(),
                'contact_id': contact_id,
                'status': 'completed'
            },
            'property': {
                'id': property_id,
                'name': property_name,
                'location': property_location,
                'developer': property_developer,
                'type': property_type,
                'size_ft2': property_size,
                'price_aed': property_price
            },
            'investment_metrics': {
                'adr': metrics.get('adr', 0),
                'occupancy_percentage': metrics.get('occupancy_percentage', 0),
                'gross_rental_income': metrics.get('gross_rental_income', 0),
                'service_charge_per_sqft': metrics.get('service_charge_per_sqft', 0),
                'net_yield_percentage': metrics.get('net_yield_percentage', 0),
                'irr_10yr': metrics.get('irr_10yr', 0),
                'capital_appreciation_cagr': metrics.get('capital_appreciation_cagr', 0)
            },
            'pdf_urls': pdf_urls
        }
        
        return dashboard_data
    
    async def _push_to_supabase(self, dashboard_data: Dict[str, Any]) -> None:
        """
        Push data to Supabase.
        
        Args:
            dashboard_data: Formatted dashboard data
        """
        # In a real implementation, this would use the Supabase client to push data
        # For now, we'll simulate the operation
        
        # Simulate API call delay
        await asyncio.sleep(0.3)
        
        # Log the operation (in a real implementation, this would be a Supabase API call)
        print(f"Pushed proposal {dashboard_data['proposal']['id']} to Supabase for contact {dashboard_data['proposal']['contact_id']}")
