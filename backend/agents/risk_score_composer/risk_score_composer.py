"""
RiskScoreComposer for PropPulse platform

This module implements risk grading rules and persists risk scores:
- Applies rules to determine RED, AMBER, or GREEN risk grades
- Updates properties.risk_grade field
- Tracks risk grade history
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
from sqlalchemy.orm import Session

from db.models.risk_models import RiskResult, RiskGrade, RiskGradeHistory, Property
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskScoreComposer:
    """
    RiskScoreComposer for PropPulse platform
    
    Applies risk grading rules and persists risk scores
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RiskScoreComposer"""
        self.config = config or {}
        
        # Risk grading thresholds
        self.green_prob_negative_threshold = self.config.get('green_prob_negative_threshold', 0.10)
        self.green_developer_risk_threshold = self.config.get('green_developer_risk_threshold', 2)
        self.amber_prob_negative_threshold = self.config.get('amber_prob_negative_threshold', 0.25)
        
        # Initialize Pinecone metadata updater
        self.pinecone_updater = PineconeMetadataUpdater()
    
    def _determine_risk_grade(self, prob_negative: float, developer_risk_score: int) -> RiskGrade:
        """
        Determine risk grade based on rules
        
        Args:
            prob_negative: Probability of negative IRR
            developer_risk_score: Developer risk score (1-5)
            
        Returns:
            Risk grade (RED, AMBER, or GREEN)
        """
        # Apply rules:
        # Green = P(IRR<0) ≤ 10% & developer risk_score ≤ 2
        # Amber = otherwise if P(IRR<0) ≤ 25%
        # Red = everything else
        if prob_negative <= self.green_prob_negative_threshold and developer_risk_score <= self.green_developer_risk_threshold:
            return RiskGrade.GREEN
        elif prob_negative <= self.amber_prob_negative_threshold:
            return RiskGrade.AMBER
        else:
            return RiskGrade.RED
    
    async def compute_risk_grade(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Compute risk grade for a property
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Risk grade result
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
            
            # Get latest risk result
            risk_result = db_session.query(RiskResult).filter(
                RiskResult.property_id == property_id
            ).order_by(
                RiskResult.timestamp.desc()
            ).first()
            
            if not risk_result:
                logger.error(f"No risk results found for property: {property_id}")
                
                if close_session:
                    db_session.close()
                
                return {
                    'status': 'error',
                    'message': f"No risk results found for property: {property_id}"
                }
            
            # Get developer risk score
            developer_risk_score = getattr(property_data, 'developer_risk_score', 3)
            
            # Determine risk grade
            new_risk_grade = self._determine_risk_grade(risk_result.prob_negative, developer_risk_score)
            
            # Get current risk grade
            old_risk_grade = property_data.risk_grade
            
            # Check if grade has changed
            grade_changed = old_risk_grade != new_risk_grade
            
            if grade_changed:
                # Create risk grade history entry
                history_entry = RiskGradeHistory(
                    property_id=property_id,
                    old_grade=old_risk_grade,
                    new_grade=new_risk_grade,
                    change_timestamp=datetime.utcnow(),
                    reason=f"P(IRR<0)={risk_result.prob_negative:.2f}, developer_risk_score={developer_risk_score}"
                )
                db_session.add(history_entry)
            
            # Update property risk grade
            property_data.risk_grade = new_risk_grade
            property_data.last_risk_assessment = datetime.utcnow()
            
            # Commit changes
            db_session.commit()
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_property_metadata(
                property_id=property_id,
                metadata={
                    'risk_grade': new_risk_grade.value
                }
            )
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Return result
            return {
                'status': 'success',
                'property_id': property_id,
                'old_risk_grade': old_risk_grade.value if old_risk_grade else None,
                'new_risk_grade': new_risk_grade.value,
                'grade_changed': grade_changed,
                'prob_negative': risk_result.prob_negative,
                'developer_risk_score': developer_risk_score,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to compute risk grade: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to compute risk grade: {str(e)}"
            }
    
    async def compute_batch_risk_grades(self, property_ids: List[str], db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Compute risk grades for multiple properties
        
        Args:
            property_ids: List of property IDs
            db_session: Database session (optional)
            
        Returns:
            Batch risk grade results
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Compute risk grades for each property
            results = []
            for property_id in property_ids:
                result = await self.compute_risk_grade(property_id, db_session)
                results.append(result)
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Count successes, failures, and grade changes
            success_count = sum(1 for result in results if result.get('status') == 'success')
            failure_count = len(results) - success_count
            grade_change_count = sum(1 for result in results if result.get('status') == 'success' and result.get('grade_changed', False))
            
            return {
                'status': 'success',
                'message': f"Batch risk grade computation completed: {success_count} succeeded, {failure_count} failed, {grade_change_count} changed",
                'total_properties': len(property_ids),
                'success_count': success_count,
                'failure_count': failure_count,
                'grade_change_count': grade_change_count,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to compute batch risk grades: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to compute batch risk grades: {str(e)}"
            }
    
    async def get_risk_grade_history(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get risk grade history for a property
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Risk grade history
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get risk grade history
            history_entries = db_session.query(RiskGradeHistory).filter(
                RiskGradeHistory.property_id == property_id
            ).order_by(
                RiskGradeHistory.change_timestamp.desc()
            ).all()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Convert to dictionaries
            history = []
            for entry in history_entries:
                history.append({
                    'id': entry.id,
                    'property_id': entry.property_id,
                    'old_grade': entry.old_grade.value if entry.old_grade else None,
                    'new_grade': entry.new_grade.value,
                    'change_timestamp': entry.change_timestamp.isoformat(),
                    'reason': entry.reason,
                    'triggered_alert': entry.triggered_alert,
                    'triggered_reprice': entry.triggered_reprice
                })
            
            return {
                'status': 'success',
                'property_id': property_id,
                'history_count': len(history),
                'history': history
            }
        
        except Exception as e:
            logger.error(f"Failed to get risk grade history: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to get risk grade history: {str(e)}"
            }
    
    async def get_risk_grade_distribution(self, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get distribution of risk grades across all properties
        
        Args:
            db_session: Database session (optional)
            
        Returns:
            Risk grade distribution
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Count properties by risk grade
            green_count = db_session.query(Property).filter(Property.risk_grade == RiskGrade.GREEN).count()
            amber_count = db_session.query(Property).filter(Property.risk_grade == RiskGrade.AMBER).count()
            red_count = db_session.query(Property).filter(Property.risk_grade == RiskGrade.RED).count()
            null_count = db_session.query(Property).filter(Property.risk_grade == None).count()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Calculate total and percentages
            total_count = green_count + amber_count + red_count + null_count
            green_percent = (green_count / total_count) * 100 if total_count > 0 else 0
            amber_percent = (amber_count / total_count) * 100 if total_count > 0 else 0
            red_percent = (red_count / total_count) * 100 if total_count > 0 else 0
            null_percent = (null_count / total_count) * 100 if total_count > 0 else 0
            
            return {
                'status': 'success',
                'total_count': total_count,
                'distribution': {
                    'green': {
                        'count': green_count,
                        'percent': green_percent
                    },
                    'amber': {
                        'count': amber_count,
                        'percent': amber_percent
                    },
                    'red': {
                        'count': red_count,
                        'percent': red_percent
                    },
                    'null': {
                        'count': null_count,
                        'percent': null_percent
                    }
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to get risk grade distribution: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to get risk grade distribution: {str(e)}"
            }
