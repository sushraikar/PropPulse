"""
Database models for risk assessment and market metrics
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

Base = declarative_base()

class MetricType(enum.Enum):
    """Enum for market metric types"""
    STR_REVPAR = "str_revpar"
    STR_ADR = "str_adr"
    AED_SWAP_RATE = "aed_swap_rate"
    SOFR_RATE = "sofr_rate"
    POLYGON_RENT_INDEX = "polygon_rent_index"
    DEVELOPER_DEFAULT = "developer_default"


class MarketMetric(Base):
    """Market metrics table for storing time series data"""
    __tablename__ = 'market_metrics'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    metric_subtype = Column(String(50), nullable=True, index=True)
    value = Column(Float, nullable=False)
    region = Column(String(50), nullable=True, index=True)
    property_type = Column(String(50), nullable=True)
    developer_id = Column(String(50), nullable=True, index=True)
    source = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MarketMetric(id={self.id}, timestamp={self.timestamp}, type={self.metric_type}, value={self.value})>"


class RiskGrade(enum.Enum):
    """Enum for risk grades"""
    RED = "red"
    AMBER = "amber"
    GREEN = "green"


class RiskResult(Base):
    """Risk results table for storing Monte Carlo simulation results"""
    __tablename__ = 'risk_results'

    id = Column(Integer, primary_key=True)
    property_id = Column(String(50), ForeignKey('properties.id'), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    mean_irr = Column(Float, nullable=False)
    var_5 = Column(Float, nullable=False)  # 5th percentile IRR (Value at Risk)
    var_95 = Column(Float, nullable=False)  # 95th percentile IRR
    prob_negative = Column(Float, nullable=False)  # P(IRR < 0)
    prob_above_threshold = Column(Float, nullable=False)  # P(IRR > 12%)
    breakeven_year = Column(Float, nullable=True)
    yield_on_cost_year_1 = Column(Float, nullable=True)
    risk_grade = Column(Enum(RiskGrade), nullable=False, index=True)
    simulation_count = Column(Integer, nullable=False)
    simulation_seed = Column(Integer, nullable=True)
    simulation_parameters = Column(JSON, nullable=True)
    simulation_results = Column(JSON, nullable=True)  # Summary statistics, not full results
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Property model
    property = relationship("Property", back_populates="risk_results")

    def __repr__(self):
        return f"<RiskResult(id={self.id}, property_id={self.property_id}, grade={self.risk_grade}, mean_irr={self.mean_irr})>"


class RiskGradeHistory(Base):
    """Risk grade history table for tracking changes"""
    __tablename__ = 'risk_grade_history'

    id = Column(Integer, primary_key=True)
    property_id = Column(String(50), ForeignKey('properties.id'), nullable=False, index=True)
    old_grade = Column(Enum(RiskGrade), nullable=True)
    new_grade = Column(Enum(RiskGrade), nullable=False)
    change_timestamp = Column(DateTime, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    triggered_alert = Column(Boolean, default=False)
    triggered_reprice = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Property model
    property = relationship("Property", back_populates="risk_grade_history")

    def __repr__(self):
        return f"<RiskGradeHistory(id={self.id}, property_id={self.property_id}, old={self.old_grade}, new={self.new_grade})>"


# Add risk_grade field to Property model
# This assumes Property model already exists from previous phases
class Property(Base):
    """Property model with risk assessment fields"""
    __tablename__ = 'properties'

    # Existing fields from previous phases
    id = Column(String(50), primary_key=True)
    # ... other existing fields ...

    # New fields for risk assessment
    risk_grade = Column(Enum(RiskGrade), nullable=True, index=True)
    last_risk_assessment = Column(DateTime, nullable=True)
    
    # Relationships
    risk_results = relationship("RiskResult", back_populates="property", order_by="desc(RiskResult.timestamp)")
    risk_grade_history = relationship("RiskGradeHistory", back_populates="property", order_by="desc(RiskGradeHistory.change_timestamp)")

    def __repr__(self):
        return f"<Property(id={self.id}, risk_grade={self.risk_grade})>"
