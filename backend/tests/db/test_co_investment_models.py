"""
Tests for the co-investment models and database schema
"""
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from db.models.co_investment import (
    CoInvestmentGroup,
    CapTable,
    PayoutSchedule,
    TokenStatus,
    KycStatus,
    SignStatus
)

class TestCoInvestmentModels:
    """Test cases for co-investment models"""
    
    def test_co_investment_group_creation(self, db_session: Session):
        """Test creating a co-investment group"""
        # Create a new co-investment group
        group = CoInvestmentGroup(
            property_id="UNO-611",
            target_raise=1117105.0,
            min_investment=50000.0,
            max_investors=10,
            token_contract_address="0x1234567890123456789012345678901234567890",
            token_name="PropPulse UNO-611",
            token_symbol="PPUNO611",
            status="funding",
            deadline=datetime.now() + timedelta(days=30)
        )
        
        # Add to session and commit
        db_session.add(group)
        db_session.commit()
        
        # Query the group
        queried_group = db_session.query(CoInvestmentGroup).filter_by(property_id="UNO-611").first()
        
        # Assert group was created correctly
        assert queried_group is not None
        assert queried_group.property_id == "UNO-611"
        assert queried_group.target_raise == 1117105.0
        assert queried_group.min_investment == 50000.0
        assert queried_group.max_investors == 10
        assert queried_group.token_contract_address == "0x1234567890123456789012345678901234567890"
        assert queried_group.token_name == "PropPulse UNO-611"
        assert queried_group.token_symbol == "PPUNO611"
        assert queried_group.status == "funding"
        assert queried_group.deadline > datetime.now()
    
    def test_cap_table_creation(self, db_session: Session):
        """Test creating a cap table entry"""
        # Create a co-investment group first
        group = CoInvestmentGroup(
            property_id="UNO-611",
            target_raise=1117105.0,
            min_investment=50000.0,
            max_investors=10,
            token_contract_address="0x1234567890123456789012345678901234567890",
            token_name="PropPulse UNO-611",
            token_symbol="PPUNO611",
            status="funding",
            deadline=datetime.now() + timedelta(days=30)
        )
        db_session.add(group)
        db_session.flush()
        
        # Create a cap table entry
        cap_entry = CapTable(
            co_investment_group_id=group.id,
            investor_name="John Doe",
            investor_email="john.doe@example.com",
            investor_phone="+971501234567",
            investor_wallet_address="0xabcdef1234567890abcdef1234567890abcdef12",
            investment_amount=100000.0,
            share_percentage=8.95,
            token_status=TokenStatus.NOT_MINTED,
            token_amount=0.0,
            kyc_status=KycStatus.PENDING,
            sign_status=SignStatus.PENDING,
            auto_reinvest=False
        )
        
        # Add to session and commit
        db_session.add(cap_entry)
        db_session.commit()
        
        # Query the cap table entry
        queried_entry = db_session.query(CapTable).filter_by(investor_name="John Doe").first()
        
        # Assert entry was created correctly
        assert queried_entry is not None
        assert queried_entry.co_investment_group_id == group.id
        assert queried_entry.investor_name == "John Doe"
        assert queried_entry.investor_email == "john.doe@example.com"
        assert queried_entry.investor_phone == "+971501234567"
        assert queried_entry.investor_wallet_address == "0xabcdef1234567890abcdef1234567890abcdef12"
        assert queried_entry.investment_amount == 100000.0
        assert queried_entry.share_percentage == 8.95
        assert queried_entry.token_status == TokenStatus.NOT_MINTED
        assert queried_entry.token_amount == 0.0
        assert queried_entry.kyc_status == KycStatus.PENDING
        assert queried_entry.sign_status == SignStatus.PENDING
        assert queried_entry.auto_reinvest is False
    
    def test_payout_schedule_creation(self, db_session: Session):
        """Test creating a payout schedule"""
        # Create a co-investment group first
        group = CoInvestmentGroup(
            property_id="UNO-611",
            target_raise=1117105.0,
            min_investment=50000.0,
            max_investors=10,
            token_contract_address="0x1234567890123456789012345678901234567890",
            token_name="PropPulse UNO-611",
            token_symbol="PPUNO611",
            status="funding",
            deadline=datetime.now() + timedelta(days=30)
        )
        db_session.add(group)
        db_session.flush()
        
        # Create a payout schedule
        payout = PayoutSchedule(
            co_investment_group_id=group.id,
            amount=10000.0,
            scheduled_date=datetime.now() + timedelta(days=5),
            description="Monthly Rent Distribution - May 2025",
            status="pending"
        )
        
        # Add to session and commit
        db_session.add(payout)
        db_session.commit()
        
        # Query the payout schedule
        queried_payout = db_session.query(PayoutSchedule).filter_by(
            co_investment_group_id=group.id
        ).first()
        
        # Assert payout was created correctly
        assert queried_payout is not None
        assert queried_payout.co_investment_group_id == group.id
        assert queried_payout.amount == 10000.0
        assert queried_payout.description == "Monthly Rent Distribution - May 2025"
        assert queried_payout.status == "pending"
        assert queried_payout.scheduled_date > datetime.now()
    
    def test_relationships(self, db_session: Session):
        """Test relationships between models"""
        # Create a co-investment group
        group = CoInvestmentGroup(
            property_id="UNO-611",
            target_raise=1117105.0,
            min_investment=50000.0,
            max_investors=10,
            token_contract_address="0x1234567890123456789012345678901234567890",
            token_name="PropPulse UNO-611",
            token_symbol="PPUNO611",
            status="funding",
            deadline=datetime.now() + timedelta(days=30)
        )
        db_session.add(group)
        db_session.flush()
        
        # Create two cap table entries
        cap_entry1 = CapTable(
            co_investment_group_id=group.id,
            investor_name="John Doe",
            investor_email="john.doe@example.com",
            investor_wallet_address="0xabcdef1234567890abcdef1234567890abcdef12",
            investment_amount=100000.0,
            share_percentage=8.95,
            token_status=TokenStatus.NOT_MINTED,
            kyc_status=KycStatus.PENDING,
            sign_status=SignStatus.PENDING
        )
        
        cap_entry2 = CapTable(
            co_investment_group_id=group.id,
            investor_name="Jane Smith",
            investor_email="jane.smith@example.com",
            investor_wallet_address="0x9876543210fedcba9876543210fedcba98765432",
            investment_amount=200000.0,
            share_percentage=17.9,
            token_status=TokenStatus.NOT_MINTED,
            kyc_status=KycStatus.PENDING,
            sign_status=SignStatus.PENDING
        )
        
        # Create a payout schedule
        payout = PayoutSchedule(
            co_investment_group_id=group.id,
            amount=10000.0,
            scheduled_date=datetime.now() + timedelta(days=5),
            description="Monthly Rent Distribution - May 2025",
            status="pending"
        )
        
        # Add to session and commit
        db_session.add_all([cap_entry1, cap_entry2, payout])
        db_session.commit()
        
        # Query the group with relationships
        queried_group = db_session.query(CoInvestmentGroup).filter_by(id=group.id).first()
        
        # Assert relationships work correctly
        assert len(queried_group.cap_table) == 2
        assert len(queried_group.payout_schedules) == 1
        
        # Check cap table entries
        investor_names = [entry.investor_name for entry in queried_group.cap_table]
        assert "John Doe" in investor_names
        assert "Jane Smith" in investor_names
        
        # Check payout schedule
        assert queried_group.payout_schedules[0].description == "Monthly Rent Distribution - May 2025"
        
        # Check relationship from cap table to group
        queried_cap_entry = db_session.query(CapTable).filter_by(investor_name="John Doe").first()
        assert queried_cap_entry.co_investment_group.property_id == "UNO-611"
        
        # Check relationship from payout to group
        queried_payout = db_session.query(PayoutSchedule).filter_by(
            description="Monthly Rent Distribution - May 2025"
        ).first()
        assert queried_payout.co_investment_group.property_id == "UNO-611"
