"""
AlertAgent for PropPulse platform

This module handles risk grade downgrade alerts and auto-repricing:
- Detects risk grade downgrades
- Sends Zoho CRM tasks to owner agents
- Sends WhatsApp alerts to investors
- Triggers auto-repricing of secondary market listings
"""
import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models.risk_models import RiskGrade, RiskGradeHistory, Property
from db.models.co_investment import CapTable
from integrations.zoho.zoho_crm import ZohoCRM
from integrations.twilio.whatsapp_service import WhatsAppService
from integrations.secondary_marketplace.secondary_marketplace import SecondaryMarketplace
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertAgent:
    """
    AlertAgent for PropPulse platform
    
    Handles risk grade downgrade alerts and auto-repricing
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the AlertAgent"""
        self.config = config or {}
        
        # Alert throttling configuration
        self.alert_throttle_hours = self.config.get('alert_throttle_hours', 24)
        
        # Auto-repricing configuration
        self.reprice_factor_green_to_amber = self.config.get('reprice_factor_green_to_amber', 0.02)
        self.reprice_factor_amber_to_red = self.config.get('reprice_factor_amber_to_red', 0.02)
        self.reprice_factor_green_to_red = self.config.get('reprice_factor_green_to_red', 0.04)
        
        # Initialize integrations
        self.zoho_crm = ZohoCRM()
        self.whatsapp_service = WhatsAppService()
        self.secondary_marketplace = SecondaryMarketplace()
    
    def _get_grade_emoji(self, grade: RiskGrade) -> str:
        """
        Get emoji for risk grade
        
        Args:
            grade: Risk grade
            
        Returns:
            Emoji representation
        """
        if grade == RiskGrade.GREEN:
            return "🟢"
        elif grade == RiskGrade.AMBER:
            return "🟠"
        elif grade == RiskGrade.RED:
            return "🔴"
        else:
            return "⚪"
    
    def _get_action_line(self, old_grade: RiskGrade, new_grade: RiskGrade) -> str:
        """
        Get action line for risk grade change
        
        Args:
            old_grade: Old risk grade
            new_grade: New risk grade
            
        Returns:
            Action line text
        """
        if new_grade == RiskGrade.RED:
            return "Consider reviewing your investment strategy."
        elif new_grade == RiskGrade.AMBER and old_grade == RiskGrade.GREEN:
            return "Monitor performance closely."
        else:
            return "No immediate action required."
    
    def _calculate_reprice_factor(self, old_grade: RiskGrade, new_grade: RiskGrade) -> float:
        """
        Calculate reprice factor for grade change
        
        Args:
            old_grade: Old risk grade
            new_grade: New risk grade
            
        Returns:
            Reprice factor (percentage as decimal)
        """
        if old_grade == RiskGrade.GREEN and new_grade == RiskGrade.AMBER:
            return self.reprice_factor_green_to_amber
        elif old_grade == RiskGrade.AMBER and new_grade == RiskGrade.RED:
            return self.reprice_factor_amber_to_red
        elif old_grade == RiskGrade.GREEN and new_grade == RiskGrade.RED:
            return self.reprice_factor_green_to_red
        else:
            return 0.0
    
    async def check_for_downgrades(self, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Check for risk grade downgrades
        
        Args:
            db_session: Database session (optional)
            
        Returns:
            Downgrade check results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get recent risk grade history entries with downgrades
            throttle_time = datetime.utcnow() - timedelta(hours=self.alert_throttle_hours)
            
            # Find downgrades where old_grade is better than new_grade
            # and no alert has been triggered yet
            downgrades = db_session.query(RiskGradeHistory).filter(
                RiskGradeHistory.change_timestamp >= throttle_time,
                RiskGradeHistory.triggered_alert == False,
                # Check for downgrades (GREEN->AMBER, GREEN->RED, AMBER->RED)
                ((RiskGradeHistory.old_grade == RiskGrade.GREEN) & 
                 ((RiskGradeHistory.new_grade == RiskGrade.AMBER) | (RiskGradeHistory.new_grade == RiskGrade.RED))) |
                ((RiskGradeHistory.old_grade == RiskGrade.AMBER) & (RiskGradeHistory.new_grade == RiskGrade.RED))
            ).all()
            
            logger.info(f"Found {len(downgrades)} recent risk grade downgrades")
            
            # Process each downgrade
            results = []
            for downgrade in downgrades:
                # Get property details
                property_data = db_session.query(Property).filter(
                    Property.id == downgrade.property_id
                ).first()
                
                if not property_data:
                    logger.warning(f"Property not found for downgrade: {downgrade.property_id}")
                    continue
                
                # Process downgrade
                result = await self.process_downgrade(downgrade, property_data, db_session)
                results.append(result)
                
                # Mark as processed
                downgrade.triggered_alert = True
                db_session.add(downgrade)
            
            # Commit changes
            db_session.commit()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Count successes and failures
            success_count = sum(1 for result in results if result.get('status') == 'success')
            failure_count = len(results) - success_count
            
            return {
                'status': 'success',
                'message': f"Downgrade check completed: {success_count} processed, {failure_count} failed",
                'total_downgrades': len(downgrades),
                'success_count': success_count,
                'failure_count': failure_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to check for downgrades: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to check for downgrades: {str(e)}"
            }
    
    async def process_downgrade(self, downgrade: RiskGradeHistory, property_data: Property, db_session: Session) -> Dict[str, Any]:
        """
        Process a risk grade downgrade
        
        Args:
            downgrade: Risk grade history entry
            property_data: Property data
            db_session: Database session
            
        Returns:
            Processing result
        """
        try:
            property_id = downgrade.property_id
            old_grade = downgrade.old_grade
            new_grade = downgrade.new_grade
            
            logger.info(f"Processing downgrade for property {property_id}: {old_grade} -> {new_grade}")
            
            # Get latest risk result for property
            risk_result = db_session.query(RiskResult).filter(
                RiskResult.property_id == property_id
            ).order_by(
                RiskResult.timestamp.desc()
            ).first()
            
            if not risk_result:
                logger.warning(f"No risk results found for property: {property_id}")
                return {
                    'status': 'error',
                    'message': f"No risk results found for property: {property_id}"
                }
            
            # Create Zoho CRM task
            zoho_result = await self.create_zoho_task(property_data, old_grade, new_grade, risk_result)
            
            # Send WhatsApp alerts to investors
            whatsapp_result = await self.send_investor_alerts(property_data, old_grade, new_grade, risk_result, db_session)
            
            # Auto-reprice secondary market listings
            reprice_result = await self.auto_reprice_listings(property_data, old_grade, new_grade)
            
            # Mark downgrade as processed
            downgrade.triggered_alert = True
            downgrade.triggered_reprice = reprice_result.get('status') == 'success'
            
            return {
                'status': 'success',
                'property_id': property_id,
                'old_grade': old_grade.value,
                'new_grade': new_grade.value,
                'zoho_task': zoho_result,
                'whatsapp_alerts': whatsapp_result,
                'reprice_result': reprice_result
            }
        
        except Exception as e:
            logger.error(f"Failed to process downgrade: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to process downgrade: {str(e)}"
            }
    
    async def create_zoho_task(self, property_data: Property, old_grade: RiskGrade, new_grade: RiskGrade, risk_result: RiskResult) -> Dict[str, Any]:
        """
        Create Zoho CRM task for owner agent
        
        Args:
            property_data: Property data
            old_grade: Old risk grade
            new_grade: New risk grade
            risk_result: Risk result data
            
        Returns:
            Zoho task creation result
        """
        try:
            # Get owner agent from property data
            owner_agent = getattr(property_data, 'owner_agent', None)
            
            if not owner_agent:
                logger.warning(f"No owner agent found for property: {property_data.id}")
                return {
                    'status': 'error',
                    'message': f"No owner agent found for property: {property_data.id}"
                }
            
            # Create task subject
            subject = f"Risk Grade Downgrade: {property_data.id} ({old_grade.value} → {new_grade.value})"
            
            # Create task description
            description = f"""
Risk grade for property {property_data.id} has been downgraded from {old_grade.value} to {new_grade.value}.

Risk Metrics:
- P(IRR<0): {risk_result.prob_negative:.2%}
- Mean IRR: {risk_result.mean_irr:.2%}
- 5th Percentile IRR (VaR): {risk_result.var_5:.2%}
- Breakeven Year: {risk_result.breakeven_year:.1f}

Please review the property and contact investors if necessary.
"""
            
            # Create task in Zoho CRM
            task_result = await self.zoho_crm.create_task(
                subject=subject,
                description=description,
                due_date=datetime.utcnow() + timedelta(days=1),
                priority="High",
                status="Not Started",
                owner=owner_agent,
                related_to={
                    "module": "Properties",
                    "id": property_data.id
                }
            )
            
            return task_result
        
        except Exception as e:
            logger.error(f"Failed to create Zoho task: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to create Zoho task: {str(e)}"
            }
    
    async def send_investor_alerts(self, property_data: Property, old_grade: RiskGrade, new_grade: RiskGrade, risk_result: RiskResult, db_session: Session) -> Dict[str, Any]:
        """
        Send WhatsApp alerts to investors
        
        Args:
            property_data: Property data
            old_grade: Old risk grade
            new_grade: New risk grade
            risk_result: Risk result data
            db_session: Database session
            
        Returns:
            WhatsApp alert results
        """
        try:
            # Get investors for property
            investors = db_session.query(CapTable).filter(
                CapTable.co_investment_group.has(property_id=property_data.id)
            ).all()
            
            if not investors:
                logger.info(f"No investors found for property: {property_data.id}")
                return {
                    'status': 'success',
                    'message': f"No investors found for property: {property_data.id}",
                    'investor_count': 0,
                    'sent_count': 0
                }
            
            # Format message
            old_emoji = self._get_grade_emoji(old_grade)
            new_emoji = self._get_grade_emoji(new_grade)
            action_line = self._get_action_line(old_grade, new_grade)
            dashboard_link = f"https://app.proppulse.ai/dashboard?property={property_data.id}"
            
            message = f"""
*Risk Update – {property_data.id}*
Grade: {old_emoji} → {new_emoji}
P(IRR<0): {risk_result.prob_negative:.1%}
Mean IRR: {risk_result.mean_irr:.1%}
Action: {action_line}
🔗 Dashboard: {dashboard_link}
"""
            
            # Send to each investor
            results = []
            for investor in investors:
                if not investor.investor_phone:
                    logger.warning(f"No phone number for investor: {investor.investor_name}")
                    continue
                
                # Send WhatsApp message
                result = await self.whatsapp_service.send_message(
                    to=investor.investor_phone,
                    message=message
                )
                
                results.append({
                    'investor_id': investor.id,
                    'investor_name': investor.investor_name,
                    'status': result.get('status')
                })
            
            # Count successes
            sent_count = sum(1 for result in results if result.get('status') == 'success')
            
            return {
                'status': 'success',
                'property_id': property_data.id,
                'investor_count': len(investors),
                'sent_count': sent_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to send investor alerts: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to send investor alerts: {str(e)}"
            }
    
    async def auto_reprice_listings(self, property_data: Property, old_grade: RiskGrade, new_grade: RiskGrade) -> Dict[str, Any]:
        """
        Auto-reprice secondary market listings
        
        Args:
            property_data: Property data
            old_grade: Old risk grade
            new_grade: New risk grade
            
        Returns:
            Repricing result
        """
        try:
            # Calculate reprice factor
            reprice_factor = self._calculate_reprice_factor(old_grade, new_grade)
            
            if reprice_factor <= 0:
                logger.info(f"No repricing needed for property: {property_data.id}")
                return {
                    'status': 'success',
                    'message': f"No repricing needed for property: {property_data.id}",
                    'reprice_factor': reprice_factor
                }
            
            # Get current list price
            list_price = property_data.list_price_aed
            
            # Calculate new price
            new_price = list_price * (1 - reprice_factor)
            
            # Update secondary market listings
            reprice_result = await self.secondary_marketplace.update_listing_price(
                property_id=property_data.id,
                new_price=new_price,
                reason=f"Risk grade downgrade: {old_grade.value} → {new_grade.value}"
            )
            
            return {
                'status': 'success',
                'property_id': property_data.id,
                'old_price': list_price,
                'new_price': new_price,
                'reprice_factor': reprice_factor,
                'reprice_result': reprice_result
            }
        
        except Exception as e:
            logger.error(f"Failed to auto-reprice listings: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to auto-reprice listings: {str(e)}"
            }
    
    async def adjust_market_prices(self, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Adjust secondary market prices based on risk grades
        
        Args:
            db_session: Database session (optional)
            
        Returns:
            Price adjustment results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get properties with recent risk grade changes
            # that haven't triggered repricing yet
            recent_changes = db_session.query(RiskGradeHistory).filter(
                RiskGradeHistory.triggered_reprice == False,
                # Check for downgrades (GREEN->AMBER, GREEN->RED, AMBER->RED)
                ((RiskGradeHistory.old_grade == RiskGrade.GREEN) & 
                 ((RiskGradeHistory.new_grade == RiskGrade.AMBER) | (RiskGradeHistory.new_grade == RiskGrade.RED))) |
                ((RiskGradeHistory.old_grade == RiskGrade.AMBER) & (RiskGradeHistory.new_grade == RiskGrade.RED))
            ).all()
            
            logger.info(f"Found {len(recent_changes)} risk grade changes for price adjustment")
            
            # Process each change
            results = []
            for change in recent_changes:
                # Get property details
                property_data = db_session.query(Property).filter(
                    Property.id == change.property_id
                ).first()
                
                if not property_data:
                    logger.warning(f"Property not found for change: {change.property_id}")
                    continue
                
                # Auto-reprice listings
                result = await self.auto_reprice_listings(
                    property_data=property_data,
                    old_grade=change.old_grade,
                    new_grade=change.new_grade
                )
                
                results.append(result)
                
                # Mark as processed
                change.triggered_reprice = True
                db_session.add(change)
            
            # Commit changes
            db_session.commit()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Count successes and failures
            success_count = sum(1 for result in results if result.get('status') == 'success')
            failure_count = len(results) - success_count
            
            return {
                'status': 'success',
                'message': f"Price adjustment completed: {success_count} adjusted, {failure_count} failed",
                'total_changes': len(recent_changes),
                'success_count': success_count,
                'failure_count': failure_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to adjust market prices: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to adjust market prices: {str(e)}"
            }
