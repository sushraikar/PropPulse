"""
Property model for PropPulse
"""
from sqlalchemy import Column, Integer, String, Float, Enum, JSON, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

Base = declarative_base()

class ViewOrientation(enum.Enum):
    """Enum for property view orientation"""
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"

class Property(Base):
    """Property model"""
    __tablename__ = 'properties'

    id = Column(Integer, primary_key=True)
    property_id = Column(String(50), unique=True, nullable=False)
    project_name = Column(String(100), nullable=False)
    developer = Column(String(100))
    tower_phase = Column(String(100))
    unit_no = Column(String(50))
    unit_type = Column(String(50))
    size_ft2 = Column(Float)
    view = Column(String(100))
    list_price_aed = Column(Float)
    status = Column(String(50))
    vector_id = Column(String(100))
    
    # New fields for Phase 2 - Location Intelligence
    latitude = Column(Float)
    longitude = Column(Float)
    poi_json = Column(JSON)
    view_orientation = Column(Enum(ViewOrientation))
    floor = Column(Integer)
    sunset_view_score = Column(Integer)
    
    # Tracking fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_price_update = Column(DateTime)
    price_change_percentage = Column(Float)
    
    # Relationships
    proposals = relationship("Proposal", back_populates="property")
    
    def __repr__(self):
        return f"<Property(property_id='{self.property_id}', project_name='{self.project_name}', unit_no='{self.unit_no}')>"
    
    def to_dict(self):
        """Convert property to dictionary"""
        return {
            "id": self.id,
            "property_id": self.property_id,
            "project_name": self.project_name,
            "developer": self.developer,
            "tower_phase": self.tower_phase,
            "unit_no": self.unit_no,
            "unit_type": self.unit_type,
            "size_ft2": self.size_ft2,
            "view": self.view,
            "list_price_aed": self.list_price_aed,
            "status": self.status,
            "vector_id": self.vector_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "poi_json": self.poi_json,
            "view_orientation": self.view_orientation.value if self.view_orientation else None,
            "floor": self.floor,
            "sunset_view_score": self.sunset_view_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_price_update": self.last_price_update.isoformat() if self.last_price_update else None,
            "price_change_percentage": self.price_change_percentage
        }
