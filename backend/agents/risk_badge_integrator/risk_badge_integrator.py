"""
Risk grade badge integration for proposal PDFs

This module adds risk grade badges to investment proposals:
- Integrates risk grade (RED, AMBER, GREEN) badges in proposal PDFs
- Ensures consistent visual styling across all proposals
- Includes risk metrics in the investment summary section
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from db.models.risk_models import RiskResult, RiskGrade
from agents.proposal_writer.proposal_writer import ProposalWriter
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskBadgeIntegrator:
    """
    RiskBadgeIntegrator for PropPulse platform
    
    Adds risk grade badges to investment proposals
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RiskBadgeIntegrator"""
        self.config = config or {}
        
        # Badge configuration
        self.badge_colors = {
            RiskGrade.GREEN: "#27AE60",
            RiskGrade.AMBER: "#FFC65C",
            RiskGrade.RED: "#FF6B6B"
        }
        
        # Initialize proposal writer
        self.proposal_writer = ProposalWriter()
    
    def _get_badge_html(self, risk_grade: RiskGrade) -> str:
        """
        Get HTML for risk grade badge
        
        Args:
            risk_grade: Risk grade
            
        Returns:
            HTML for badge
        """
        color = self.badge_colors.get(risk_grade, "#CCCCCC")
        label = risk_grade.value.upper()
        
        html = f"""
        <div style="display: inline-block; padding: 4px 8px; background-color: {color}; 
                    color: {'#FFFFFF' if risk_grade == RiskGrade.RED or risk_grade == RiskGrade.GREEN else '#000000'}; 
                    border-radius: 4px; font-weight: bold; font-size: 14px; margin-left: 8px;">
            {label}
        </div>
        """
        
        return html
    
    def _get_risk_metrics_html(self, risk_result: RiskResult) -> str:
        """
        Get HTML for risk metrics section
        
        Args:
            risk_result: Risk result data
            
        Returns:
            HTML for risk metrics
        """
        html = f"""
        <div style="margin-top: 20px; margin-bottom: 20px; padding: 15px; border: 1px solid #E0E0E0; border-radius: 8px; background-color: #F8F8F8;">
            <h3 style="margin-top: 0; margin-bottom: 10px; color: #333333;">Risk Assessment</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0; width: 50%;"><strong>Mean IRR:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0;">{(risk_result.mean_irr * 100):.1f}%</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0;"><strong>5th Percentile IRR (VaR):</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0;">{(risk_result.var_5 * 100):.1f}%</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0;"><strong>Probability of Negative IRR:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #E0E0E0;">{(risk_result.prob_negative * 100):.1f}%</td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>Breakeven Year:</strong></td>
                    <td style="padding: 8px;">{risk_result.breakeven_year:.1f}</td>
                </tr>
            </table>
        </div>
        """
        
        return html
    
    async def integrate_risk_badge(self, property_id: str, proposal_html: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Integrate risk badge into proposal HTML
        
        Args:
            property_id: Property ID
            proposal_html: Original proposal HTML
            db_session: Database session (optional)
            
        Returns:
            Updated proposal HTML with risk badge
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
                logger.warning(f"No risk results found for property: {property_id}")
                return {
                    'status': 'warning',
                    'message': f"No risk results found for property: {property_id}",
                    'proposal_html': proposal_html
                }
            
            # Get risk grade
            risk_grade = risk_result.risk_grade
            
            # Get badge HTML
            badge_html = self._get_badge_html(risk_grade)
            
            # Get risk metrics HTML
            risk_metrics_html = self._get_risk_metrics_html(risk_result)
            
            # Add badge to property title
            updated_html = proposal_html
            
            # Find property title heading
            title_pattern = f"<h1[^>]*>{property_id}</h1>"
            title_with_badge = f"<h1>{property_id}{badge_html}</h1>"
            
            if title_pattern in updated_html:
                updated_html = updated_html.replace(title_pattern, title_with_badge)
            else:
                # Try alternative patterns
                title_pattern = f"<h2[^>]*>{property_id}</h2>"
                title_with_badge = f"<h2>{property_id}{badge_html}</h2>"
                
                if title_pattern in updated_html:
                    updated_html = updated_html.replace(title_pattern, title_with_badge)
            
            # Add risk metrics section after investment summary
            summary_end_pattern = "</table>"
            if summary_end_pattern in updated_html:
                # Find the first occurrence after a heading that contains "Investment Summary"
                parts = updated_html.split("Investment Summary")
                if len(parts) > 1:
                    # Find the first table end after the heading
                    summary_parts = parts[1].split(summary_end_pattern, 1)
                    if len(summary_parts) > 1:
                        summary_parts[0] += summary_end_pattern
                        summary_parts[0] += risk_metrics_html
                        parts[1] = "".join(summary_parts)
                        updated_html = "Investment Summary".join(parts)
            
            return {
                'status': 'success',
                'property_id': property_id,
                'risk_grade': risk_grade.value,
                'proposal_html': updated_html
            }
        
        except Exception as e:
            logger.error(f"Failed to integrate risk badge: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to integrate risk badge: {str(e)}",
                'proposal_html': proposal_html
            }
    
    async def update_proposal_with_risk_badge(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Update existing proposal with risk badge
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Update result
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get latest proposal HTML
            proposal = await self.proposal_writer.get_latest_proposal(property_id, db_session)
            
            if not proposal or 'html_content' not in proposal:
                logger.warning(f"No proposal found for property: {property_id}")
                
                if close_session:
                    db_session.close()
                
                return {
                    'status': 'error',
                    'message': f"No proposal found for property: {property_id}"
                }
            
            # Integrate risk badge
            integration_result = await self.integrate_risk_badge(
                property_id=property_id,
                proposal_html=proposal['html_content'],
                db_session=db_session
            )
            
            if integration_result.get('status') != 'success':
                logger.warning(f"Failed to integrate risk badge: {integration_result.get('message')}")
                
                if close_session:
                    db_session.close()
                
                return integration_result
            
            # Update proposal with new HTML
            update_result = await self.proposal_writer.update_proposal(
                proposal_id=proposal['id'],
                html_content=integration_result['proposal_html'],
                db_session=db_session
            )
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return {
                'status': 'success',
                'property_id': property_id,
                'proposal_id': proposal['id'],
                'risk_grade': integration_result.get('risk_grade'),
                'update_result': update_result
            }
        
        except Exception as e:
            logger.error(f"Failed to update proposal with risk badge: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to update proposal with risk badge: {str(e)}"
            }
