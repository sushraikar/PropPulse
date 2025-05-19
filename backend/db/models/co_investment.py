"""
Co-investment models for PropPulse
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class KYCStatus(enum.Enum):
    """KYC status enum for investors"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class SignStatus(enum.Enum):
    """Document signing status enum"""
    NOT_SENT = "not_sent"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    REJECTED = "rejected"
    EXPIRED = "expired"

class TokenStatus(enum.Enum):
    """Token status enum"""
    NOT_MINTED = "not_minted"
    MINTING = "minting"
    MINTED = "minted"
    FAILED = "failed"

class InvestorClass(enum.Enum):
    """Investor class enum for partitioned tranches"""
    CLASS_A = "class_a"  # Standard investors
    CLASS_B = "class_b"  # Strategic partners with special rights

class CoInvestmentGroup(Base):
    """
    Co-investment group model
    
    Represents a syndicate of investors for a specific property
    """
    __tablename__ = "co_investment_group"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    property_id = Column(String(255), ForeignKey("property.id"), nullable=False)
    target_raise = Column(Float, nullable=False)  # Target amount in AED
    min_tick = Column(Float, nullable=False)  # Minimum investment amount in AED
    current_raise = Column(Float, default=0.0)  # Current amount raised in AED
    status = Column(String(50), default="open")  # open, closed, funded, failed
    token_contract_address = Column(String(255), nullable=True)  # Ethereum address of the deployed token contract
    token_contract_abi = Column(JSON, nullable=True)  # ABI of the deployed token contract
    gnosis_safe_address = Column(String(255), nullable=True)  # Ethereum address of the Gnosis Safe
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    property = relationship("Property", back_populates="co_investment_groups")
    cap_table_entries = relationship("CapTable", back_populates="co_investment_group")
    payout_schedules = relationship("PayoutSchedule", back_populates="co_investment_group")
    
    def __repr__(self):
        return f"<CoInvestmentGroup(id={self.id}, name='{self.name}', property_id='{self.property_id}')>"

class CapTable(Base):
    """
    Cap table model
    
    Represents an investor's stake in a co-investment group
    """
    __tablename__ = "cap_table"
    
    id = Column(Integer, primary_key=True)
    co_investment_group_id = Column(Integer, ForeignKey("co_investment_group.id"), nullable=False)
    investor_name = Column(String(255), nullable=False)
    investor_email = Column(String(255), nullable=False)
    investor_phone = Column(String(50), nullable=True)
    investor_wallet_address = Column(String(255), nullable=True)  # Ethereum address of the investor
    investment_amount = Column(Float, nullable=False)  # Amount in AED
    share_percentage = Column(Float, nullable=False)  # Percentage of the total investment
    token_amount = Column(Float, nullable=True)  # Amount of tokens minted
    investor_class = Column(Enum(InvestorClass), default=InvestorClass.CLASS_A)
    
    # KYC fields
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.PENDING)
    kyc_idnow_id = Column(String(255), nullable=True)  # ID from IDnow
    kyc_completed_at = Column(DateTime, nullable=True)
    kyc_rejection_reason = Column(String(255), nullable=True)
    
    # Document signing fields
    sign_status = Column(Enum(SignStatus), default=SignStatus.NOT_SENT)
    sign_document_id = Column(String(255), nullable=True)  # ID from Zoho Sign
    sign_completed_at = Column(DateTime, nullable=True)
    
    # Token fields
    token_status = Column(Enum(TokenStatus), default=TokenStatus.NOT_MINTED)
    token_transaction_hash = Column(String(255), nullable=True)  # Transaction hash of the minting transaction
    token_minted_at = Column(DateTime, nullable=True)
    
    # Cash flow fields
    auto_reinvest = Column(Boolean, default=False)  # Whether to reinvest distributions
    total_distributions = Column(Float, default=0.0)  # Total distributions received in AED
    
    # Compliance fields
    is_us_resident = Column(Boolean, default=False)
    is_pep = Column(Boolean, default=False)
    is_sanctioned = Column(Boolean, default=False)
    is_high_risk = Column(Boolean, default=False)
    compliance_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    co_investment_group = relationship("CoInvestmentGroup", back_populates="cap_table_entries")
    payouts = relationship("Payout", back_populates="cap_table_entry")
    
    def __repr__(self):
        return f"<CapTable(id={self.id}, investor_name='{self.investor_name}', share_percentage={self.share_percentage})>"

class PayoutSchedule(Base):
    """
    Payout schedule model
    
    Represents a scheduled payout for a co-investment group
    """
    __tablename__ = "payout_schedule"
    
    id = Column(Integer, primary_key=True)
    co_investment_group_id = Column(Integer, ForeignKey("co_investment_group.id"), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)  # Total amount in AED
    description = Column(String(255), nullable=True)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    transaction_hash = Column(String(255), nullable=True)  # Transaction hash of the payout transaction
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    co_investment_group = relationship("CoInvestmentGroup", back_populates="payout_schedules")
    payouts = relationship("Payout", back_populates="payout_schedule")
    
    def __repr__(self):
        return f"<PayoutSchedule(id={self.id}, scheduled_date='{self.scheduled_date}', amount={self.amount})>"

class Payout(Base):
    """
    Payout model
    
    Represents an individual payout to an investor
    """
    __tablename__ = "payout"
    
    id = Column(Integer, primary_key=True)
    payout_schedule_id = Column(Integer, ForeignKey("payout_schedule.id"), nullable=False)
    cap_table_id = Column(Integer, ForeignKey("cap_table.id"), nullable=False)
    amount = Column(Float, nullable=False)  # Amount in AED
    status = Column(String(50), default="pending")  # pending, processing, completed, failed, reinvested
    transaction_hash = Column(String(255), nullable=True)  # Transaction hash of the payout transaction
    reinvested = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payout_schedule = relationship("PayoutSchedule", back_populates="payouts")
    cap_table_entry = relationship("CapTable", back_populates="payouts")
    
    def __repr__(self):
        return f"<Payout(id={self.id}, amount={self.amount}, status='{self.status}')>"

class MarketplaceListing(Base):
    """
    Marketplace listing model
    
    Represents a secondary market listing for tokens
    """
    __tablename__ = "marketplace_listing"
    
    id = Column(Integer, primary_key=True)
    cap_table_id = Column(Integer, ForeignKey("cap_table.id"), nullable=False)
    token_amount = Column(Float, nullable=False)  # Amount of tokens for sale
    price_per_token = Column(Float, nullable=False)  # Price per token in AED
    total_price = Column(Float, nullable=False)  # Total price in AED
    status = Column(String(50), default="active")  # active, completed, cancelled
    fee_percentage = Column(Float, default=4.0)  # Fee percentage
    buyer_cap_table_id = Column(Integer, ForeignKey("cap_table.id"), nullable=True)
    transaction_hash = Column(String(255), nullable=True)  # Transaction hash of the swap transaction
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    seller = relationship("CapTable", foreign_keys=[cap_table_id])
    buyer = relationship("CapTable", foreign_keys=[buyer_cap_table_id])
    
    def __repr__(self):
        return f"<MarketplaceListing(id={self.id}, token_amount={self.token_amount}, price_per_token={self.price_per_token})>"
