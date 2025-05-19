"""
Alembic migration for co-investment tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '0001_co_investment'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create enum types
    kyc_status = postgresql.ENUM('pending', 'in_progress', 'approved', 'rejected', 'expired', name='kycstatus')
    kyc_status.create(op.get_bind())
    
    sign_status = postgresql.ENUM('not_sent', 'sent', 'viewed', 'signed', 'rejected', 'expired', name='signstatus')
    sign_status.create(op.get_bind())
    
    token_status = postgresql.ENUM('not_minted', 'minting', 'minted', 'failed', name='tokenstatus')
    token_status.create(op.get_bind())
    
    investor_class = postgresql.ENUM('class_a', 'class_b', name='investorclass')
    investor_class.create(op.get_bind())
    
    # Create co_investment_group table
    op.create_table(
        'co_investment_group',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('property_id', sa.String(255), sa.ForeignKey('property.id'), nullable=False),
        sa.Column('target_raise', sa.Float(), nullable=False),
        sa.Column('min_tick', sa.Float(), nullable=False),
        sa.Column('current_raise', sa.Float(), default=0.0),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('token_contract_address', sa.String(255), nullable=True),
        sa.Column('token_contract_abi', sa.JSON(), nullable=True),
        sa.Column('gnosis_safe_address', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create cap_table table
    op.create_table(
        'cap_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('co_investment_group_id', sa.Integer(), sa.ForeignKey('co_investment_group.id'), nullable=False),
        sa.Column('investor_name', sa.String(255), nullable=False),
        sa.Column('investor_email', sa.String(255), nullable=False),
        sa.Column('investor_phone', sa.String(50), nullable=True),
        sa.Column('investor_wallet_address', sa.String(255), nullable=True),
        sa.Column('investment_amount', sa.Float(), nullable=False),
        sa.Column('share_percentage', sa.Float(), nullable=False),
        sa.Column('token_amount', sa.Float(), nullable=True),
        sa.Column('investor_class', sa.Enum('class_a', 'class_b', name='investorclass'), default='class_a'),
        
        # KYC fields
        sa.Column('kyc_status', sa.Enum('pending', 'in_progress', 'approved', 'rejected', 'expired', name='kycstatus'), default='pending'),
        sa.Column('kyc_idnow_id', sa.String(255), nullable=True),
        sa.Column('kyc_completed_at', sa.DateTime(), nullable=True),
        sa.Column('kyc_rejection_reason', sa.String(255), nullable=True),
        
        # Document signing fields
        sa.Column('sign_status', sa.Enum('not_sent', 'sent', 'viewed', 'signed', 'rejected', 'expired', name='signstatus'), default='not_sent'),
        sa.Column('sign_document_id', sa.String(255), nullable=True),
        sa.Column('sign_completed_at', sa.DateTime(), nullable=True),
        
        # Token fields
        sa.Column('token_status', sa.Enum('not_minted', 'minting', 'minted', 'failed', name='tokenstatus'), default='not_minted'),
        sa.Column('token_transaction_hash', sa.String(255), nullable=True),
        sa.Column('token_minted_at', sa.DateTime(), nullable=True),
        
        # Cash flow fields
        sa.Column('auto_reinvest', sa.Boolean(), default=False),
        sa.Column('total_distributions', sa.Float(), default=0.0),
        
        # Compliance fields
        sa.Column('is_us_resident', sa.Boolean(), default=False),
        sa.Column('is_pep', sa.Boolean(), default=False),
        sa.Column('is_sanctioned', sa.Boolean(), default=False),
        sa.Column('is_high_risk', sa.Boolean(), default=False),
        sa.Column('compliance_notes', sa.Text(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create payout_schedule table
    op.create_table(
        'payout_schedule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('co_investment_group_id', sa.Integer(), sa.ForeignKey('co_investment_group.id'), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('transaction_hash', sa.String(255), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create payout table
    op.create_table(
        'payout',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payout_schedule_id', sa.Integer(), sa.ForeignKey('payout_schedule.id'), nullable=False),
        sa.Column('cap_table_id', sa.Integer(), sa.ForeignKey('cap_table.id'), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('transaction_hash', sa.String(255), nullable=True),
        sa.Column('reinvested', sa.Boolean(), default=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create marketplace_listing table
    op.create_table(
        'marketplace_listing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cap_table_id', sa.Integer(), sa.ForeignKey('cap_table.id'), nullable=False),
        sa.Column('token_amount', sa.Float(), nullable=False),
        sa.Column('price_per_token', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('fee_percentage', sa.Float(), default=4.0),
        sa.Column('buyer_cap_table_id', sa.Integer(), sa.ForeignKey('cap_table.id'), nullable=True),
        sa.Column('transaction_hash', sa.String(255), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_co_investment_group_property_id', 'co_investment_group', ['property_id'])
    op.create_index('idx_cap_table_co_investment_group_id', 'cap_table', ['co_investment_group_id'])
    op.create_index('idx_cap_table_investor_email', 'cap_table', ['investor_email'])
    op.create_index('idx_cap_table_investor_wallet_address', 'cap_table', ['investor_wallet_address'])
    op.create_index('idx_payout_schedule_co_investment_group_id', 'payout_schedule', ['co_investment_group_id'])
    op.create_index('idx_payout_schedule_scheduled_date', 'payout_schedule', ['scheduled_date'])
    op.create_index('idx_payout_payout_schedule_id', 'payout', ['payout_schedule_id'])
    op.create_index('idx_payout_cap_table_id', 'payout', ['cap_table_id'])
    op.create_index('idx_marketplace_listing_cap_table_id', 'marketplace_listing', ['cap_table_id'])
    op.create_index('idx_marketplace_listing_buyer_cap_table_id', 'marketplace_listing', ['buyer_cap_table_id'])
    op.create_index('idx_marketplace_listing_status', 'marketplace_listing', ['status'])

def downgrade():
    # Drop tables
    op.drop_table('marketplace_listing')
    op.drop_table('payout')
    op.drop_table('payout_schedule')
    op.drop_table('cap_table')
    op.drop_table('co_investment_group')
    
    # Drop enum types
    op.execute('DROP TYPE investorclass')
    op.execute('DROP TYPE tokenstatus')
    op.execute('DROP TYPE signstatus')
    op.execute('DROP TYPE kycstatus')
