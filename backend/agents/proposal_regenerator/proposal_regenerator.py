"""
Module for handling proposal regeneration on price changes
"""
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from agents.proposal_writer.proposal_writer import ProposalWriter
from integrations.zoho.zoho_crm import ZohoCRM
from integrations.supabase.supabase_integration import SupabaseIntegration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProposalRegenerator:
    """
    ProposalRegenerator handles the regeneration of proposals when property prices change
    
    Responsibilities:
    - Find all proposals for a property
    - Regenerate proposals with updated pricing
    - Update Zoho CRM records
    - Update Supabase dashboard data
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ProposalRegenerator"""
        self.config = config or {}
        
        # Initialize ProposalWriter
        self.proposal_writer = ProposalWriter(config.get('proposal_writer_config'))
        
        # Initialize Zoho CRM client
        self.zoho_crm = ZohoCRM(config.get('zoho_config'))
        
        # Initialize Supabase client
        self.supabase = SupabaseIntegration(config.get('supabase_config'))
        
        # Price change threshold (percentage)
        self.price_change_threshold = config.get('price_change_threshold', 2.0)
    
    async def regenerate_proposals_for_property(
        self, 
        property_id: str, 
        price_change_pct: float,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Regenerate all proposals for a property
        
        Args:
            property_id: Zoho CRM Property ID
            price_change_pct: Price change percentage
            force: Force regeneration even if price change is below threshold
            
        Returns:
            Dict containing:
                - status: Processing status
                - message: Status message
                - regenerated: List of regenerated proposals
        """
        try:
            # Check if price change is significant
            significant_change = abs(price_change_pct) >= self.price_change_threshold
            
            if not significant_change and not force:
                return {
                    'status': 'info',
                    'message': f"Price change ({price_change_pct}%) is below threshold ({self.price_change_threshold}%)",
                    'regenerated': []
                }
            
            # Get property details
            property_data = await self.zoho_crm.get_property(property_id)
            unit_no = property_data.get('Unit_No', 'Unknown')
            
            # Find proposals for this property
            proposals = await self.zoho_crm.search_records('Proposals', {
                'criteria': f"Property_ID:equals:{property_id}"
            })
            
            if not proposals:
                return {
                    'status': 'info',
                    'message': f"No proposals found for property {unit_no}",
                    'regenerated': []
                }
            
            logger.info(f"Regenerating {len(proposals)} proposals for property {unit_no}")
            
            regenerated = []
            
            # Regenerate each proposal
            for proposal in proposals:
                proposal_id = proposal['id']
                contact_id = proposal.get('Contact_Name', {}).get('id')
                language = proposal.get('Language', 'en')
                
                if not contact_id:
                    logger.warning(f"No contact found for proposal {proposal_id}")
                    continue
                
                # Regenerate proposal
                result = await self.proposal_writer.process({
                    'property_id': property_id,
                    'contact_id': contact_id,
                    'language': language
                })
                
                if result['status'] != 'success':
                    logger.error(f"Failed to regenerate proposal {proposal_id}: {result['message']}")
                    continue
                
                # Update proposal in Zoho CRM
                update_data = {
                    'PDF_Link': result['pdf_url'],
                    'ROI_JSON': result['roi_json'],
                    'Created_On': datetime.now().isoformat()
                }
                
                await self.zoho_crm.update_record('Proposals', proposal_id, update_data)
                
                # Update Supabase dashboard data
                await self._update_supabase_dashboard(proposal_id, result)
                
                regenerated.append({
                    'proposal_id': proposal_id,
                    'contact_id': contact_id,
                    'language': language,
                    'pdf_url': result['pdf_url']
                })
                
                logger.info(f"Regenerated proposal {proposal_id} for property {unit_no}")
            
            return {
                'status': 'success',
                'message': f"Regenerated {len(regenerated)} proposals for property {unit_no}",
                'regenerated': regenerated
            }
            
        except Exception as e:
            logger.error(f"Error regenerating proposals: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error regenerating proposals: {str(e)}",
                'regenerated': []
            }
    
    async def _update_supabase_dashboard(self, proposal_id: str, proposal_result: Dict[str, Any]) -> None:
        """
        Update Supabase dashboard data for a proposal
        
        Args:
            proposal_id: Zoho CRM Proposal ID
            proposal_result: Result from ProposalWriter
        """
        try:
            # Extract data from proposal result
            proposal_data = {
                'proposal': {
                    'id': proposal_id,
                    'created_at': datetime.now().isoformat(),
                    'status': 'updated'
                },
                'property': proposal_result.get('property_data', {}),
                'investment_metrics': proposal_result.get('roi_data', {}),
                'pdf_urls': {
                    language: url for language, url in proposal_result.get('pdf_urls', {}).items()
                }
            }
            
            # Store in Supabase
            await self.supabase.store_proposal_data(proposal_data)
            
        except Exception as e:
            logger.error(f"Error updating Supabase dashboard for proposal {proposal_id}: {str(e)}")
    
    async def check_and_regenerate_all_proposals(
        self, 
        days_since_update: int = 30,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Check and regenerate all proposals that haven't been updated recently
        
        Args:
            days_since_update: Number of days since last update
            force: Force regeneration even if no price change
            
        Returns:
            Dict containing:
                - status: Processing status
                - message: Status message
                - regenerated: List of regenerated proposals
        """
        try:
            # Find proposals that haven't been updated recently
            date_criteria = f"Created_On:before:{days_since_update}:days"
            proposals = await self.zoho_crm.search_records('Proposals', {
                'criteria': date_criteria
            })
            
            if not proposals:
                return {
                    'status': 'info',
                    'message': f"No proposals found that need updating",
                    'regenerated': []
                }
            
            logger.info(f"Found {len(proposals)} proposals that need updating")
            
            regenerated = []
            
            # Process each proposal
            for proposal in proposals:
                proposal_id = proposal['id']
                property_id = proposal.get('Property_ID', {}).get('id')
                
                if not property_id:
                    logger.warning(f"No property found for proposal {proposal_id}")
                    continue
                
                # Regenerate proposals for this property
                result = await self.regenerate_proposals_for_property(property_id, 0, force=True)
                
                if result['status'] == 'success':
                    regenerated.extend(result['regenerated'])
            
            return {
                'status': 'success',
                'message': f"Regenerated {len(regenerated)} proposals",
                'regenerated': regenerated
            }
            
        except Exception as e:
            logger.error(f"Error checking and regenerating proposals: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error checking and regenerating proposals: {str(e)}",
                'regenerated': []
            }
