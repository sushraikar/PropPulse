"""
Secondary marketplace integration for auto-repricing

This module handles secondary market listing updates based on risk grades:
- Updates listing prices based on risk grade changes
- Maintains price history for compliance
- Syncs with Pinecone metadata
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from db.models.risk_models import RiskGrade
from db.models.marketplace import MarketplaceListing, PriceHistory
from integrations.pinecone.pinecone_metadata_updater import PineconeMetadataUpdater
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecondaryMarketplace:
    """
    Secondary marketplace integration for auto-repricing
    
    Handles secondary market listing updates based on risk grades
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the SecondaryMarketplace"""
        self.config = config or {}
        
        # Initialize Pinecone metadata updater
        self.pinecone_updater = PineconeMetadataUpdater()
    
    async def update_listing_price(self, property_id: str, new_price: float, reason: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Update listing price for a property
        
        Args:
            property_id: Property ID
            new_price: New listing price
            reason: Reason for price change
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
            
            # Get active listing for property
            listing = db_session.query(MarketplaceListing).filter(
                MarketplaceListing.property_id == property_id,
                MarketplaceListing.status == 'active'
            ).first()
            
            if not listing:
                logger.warning(f"No active listing found for property: {property_id}")
                
                if close_session:
                    db_session.close()
                
                return {
                    'status': 'error',
                    'message': f"No active listing found for property: {property_id}"
                }
            
            # Get current price
            old_price = listing.list_price
            
            # Create price history entry
            price_history = PriceHistory(
                listing_id=listing.id,
                old_price=old_price,
                new_price=new_price,
                change_timestamp=datetime.utcnow(),
                reason=reason,
                change_percent=((new_price - old_price) / old_price) * 100 if old_price > 0 else 0
            )
            db_session.add(price_history)
            
            # Update listing price
            listing.list_price = new_price
            listing.last_price_update = datetime.utcnow()
            db_session.add(listing)
            
            # Commit changes
            db_session.commit()
            
            # Update Pinecone metadata
            await self.pinecone_updater.update_property_metadata(
                property_id=property_id,
                metadata={
                    'list_price': new_price,
                    'last_price_update': datetime.utcnow().isoformat()
                }
            )
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return {
                'status': 'success',
                'property_id': property_id,
                'listing_id': listing.id,
                'old_price': old_price,
                'new_price': new_price,
                'change_percent': ((new_price - old_price) / old_price) * 100 if old_price > 0 else 0,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to update listing price: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to update listing price: {str(e)}"
            }
    
    async def get_price_history(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get price history for a property
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Price history
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get listing for property
            listing = db_session.query(MarketplaceListing).filter(
                MarketplaceListing.property_id == property_id
            ).first()
            
            if not listing:
                logger.warning(f"No listing found for property: {property_id}")
                
                if close_session:
                    db_session.close()
                
                return {
                    'status': 'error',
                    'message': f"No listing found for property: {property_id}"
                }
            
            # Get price history
            history = db_session.query(PriceHistory).filter(
                PriceHistory.listing_id == listing.id
            ).order_by(
                PriceHistory.change_timestamp.desc()
            ).all()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Convert to dictionaries
            history_items = []
            for item in history:
                history_items.append({
                    'id': item.id,
                    'listing_id': item.listing_id,
                    'old_price': item.old_price,
                    'new_price': item.new_price,
                    'change_percent': item.change_percent,
                    'reason': item.reason,
                    'change_timestamp': item.change_timestamp.isoformat()
                })
            
            return {
                'status': 'success',
                'property_id': property_id,
                'listing_id': listing.id,
                'current_price': listing.list_price,
                'history_count': len(history_items),
                'history': history_items
            }
        
        except Exception as e:
            logger.error(f"Failed to get price history: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to get price history: {str(e)}"
            }
    
    async def get_listings_by_risk_grade(self, risk_grade: RiskGrade, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get listings by risk grade
        
        Args:
            risk_grade: Risk grade
            db_session: Database session (optional)
            
        Returns:
            Listings by risk grade
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get listings for properties with specified risk grade
            listings = db_session.query(MarketplaceListing).join(
                Property, MarketplaceListing.property_id == Property.id
            ).filter(
                Property.risk_grade == risk_grade,
                MarketplaceListing.status == 'active'
            ).all()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            # Convert to dictionaries
            listing_items = []
            for listing in listings:
                listing_items.append({
                    'id': listing.id,
                    'property_id': listing.property_id,
                    'list_price': listing.list_price,
                    'status': listing.status,
                    'created_at': listing.created_at.isoformat(),
                    'last_price_update': listing.last_price_update.isoformat() if listing.last_price_update else None
                })
            
            return {
                'status': 'success',
                'risk_grade': risk_grade.value,
                'listing_count': len(listing_items),
                'listings': listing_items
            }
        
        except Exception as e:
            logger.error(f"Failed to get listings by risk grade: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to get listings by risk grade: {str(e)}"
            }
