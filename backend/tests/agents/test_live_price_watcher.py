"""
Tests for the LivePriceWatcher
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, mock_open
import email
from email.message import EmailMessage
import imaplib
import json

from agents.live_price_watcher.live_price_watcher import LivePriceWatcher
from agents.data_ingestor.data_ingestor import DataIngestor
from agents.proposal_writer.proposal_writer import ProposalWriter
from integrations.zoho.zoho_crm import ZohoCRM

# Sample property data
SAMPLE_PROPERTY = {
    'id': 'test_property_id',
    'Unit_No': 'UNO-611',
    'List_Price_AED': '1000000'
}

# Sample email data
SAMPLE_EMAIL = """From: sales@whiteoakwealthglobal.com
Subject: Price Sheet Update
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain

Price sheet attached.

--boundary
Content-Type: application/pdf; name="SO_UNO_20250519.pdf"
Content-Disposition: attachment; filename="SO_UNO_20250519.pdf"
Content-Transfer-Encoding: base64

SGVsbG8gV29ybGQ=

--boundary--
"""

@pytest.fixture
def live_price_watcher():
    """Create a LivePriceWatcher instance with mocked dependencies"""
    with patch('agents.live_price_watcher.live_price_watcher.DataIngestor') as mock_ingestor:
        with patch('agents.live_price_watcher.live_price_watcher.ProposalWriter') as mock_writer:
            with patch('agents.live_price_watcher.live_price_watcher.ZohoCRM') as mock_zoho:
                # Configure mocks
                mock_ingestor_instance = MagicMock()
                mock_ingestor_instance.process.return_value = {
                    'status': 'success',
                    'extracted_data': [
                        {
                            'unit_no': 'UNO-611',
                            'list_price_aed': '1050000'
                        }
                    ]
                }
                mock_ingestor.return_value = mock_ingestor_instance
                
                mock_writer_instance = MagicMock()
                mock_writer_instance.process.return_value = {
                    'status': 'success',
                    'pdf_url': 'https://example.com/proposal.pdf',
                    'roi_json': '{"net_yield": 8.5}'
                }
                mock_writer.return_value = mock_writer_instance
                
                mock_zoho_instance = MagicMock()
                mock_zoho_instance.search_properties.return_value = [SAMPLE_PROPERTY]
                mock_zoho_instance.update_property.return_value = True
                mock_zoho_instance.search_records.return_value = [
                    {
                        'id': 'test_proposal_id',
                        'Contact_Name': {'id': 'test_contact_id'},
                        'Language': 'en'
                    }
                ]
                mock_zoho_instance.update_record.return_value = True
                mock_zoho.return_value = mock_zoho_instance
                
                # Create watcher
                watcher = LivePriceWatcher({
                    'email_config': {
                        'imap_server': 'test.server.com',
                        'email_address': 'test@example.com',
                        'email_password': 'password',
                        'mailbox': 'INBOX'
                    },
                    'data_ingestor_config': {},
                    'proposal_writer_config': {},
                    'zoho_config': {},
                    'polling_interval': 10
                })
                
                yield watcher

@pytest.mark.asyncio
async def test_process_start_command(live_price_watcher):
    """Test processing start command"""
    # Mock the watcher thread
    with patch('agents.live_price_watcher.live_price_watcher.threading.Thread') as mock_thread:
        # Call the process method
        result = await live_price_watcher.process({
            'command': 'start'
        })
        
        # Verify the result
        assert result['status'] == 'success'
        assert 'Watcher started' in result['message']
        
        # Verify thread creation
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

@pytest.mark.asyncio
async def test_process_stop_command(live_price_watcher):
    """Test processing stop command"""
    # Mock the watcher thread
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    mock_thread.join.return_value = None
    live_price_watcher.watcher_thread = mock_thread
    
    # Call the process method
    result = await live_price_watcher.process({
        'command': 'stop'
    })
    
    # Verify the result
    assert result['status'] == 'success'
    assert 'Watcher stopped' in result['message']
    
    # Verify thread stopping
    mock_thread.join.assert_called_once()

@pytest.mark.asyncio
async def test_process_check_now_command(live_price_watcher):
    """Test processing check_now command"""
    # Mock the check method
    live_price_watcher._check_for_price_updates = MagicMock(return_value={
        'status': 'success',
        'message': 'Processed 1 emails, found 1 price updates',
        'updates': [
            {
                'property_id': 'test_property_id',
                'unit_no': 'UNO-611',
                'old_price': 1000000,
                'new_price': 1050000,
                'price_change_pct': 5.0,
                'significant_change': True
            }
        ]
    })
    
    # Call the process method
    result = await live_price_watcher.process({
        'command': 'check_now'
    })
    
    # Verify the result
    assert result['status'] == 'success'
    assert 'Processed 1 emails' in result['message']
    assert len(result['updates']) == 1
    
    # Verify check method call
    live_price_watcher._check_for_price_updates.assert_called_once()

@pytest.mark.asyncio
async def test_check_for_price_updates(live_price_watcher):
    """Test checking for price updates"""
    # Mock IMAP
    with patch('agents.live_price_watcher.live_price_watcher.imaplib.IMAP4_SSL') as mock_imap:
        # Configure mock
        mock_imap_instance = MagicMock()
        mock_imap_instance.search.return_value = ('OK', [b'1'])
        mock_imap_instance.fetch.return_value = ('OK', [(b'1', SAMPLE_EMAIL.encode())])
        mock_imap_instance.store.return_value = ('OK', [b'1'])
        mock_imap.return_value = mock_imap_instance
        
        # Mock tempfile
        with patch('agents.live_price_watcher.live_price_watcher.tempfile.NamedTemporaryFile', 
                  mock_open(read_data=b'test data')):
            # Mock os.unlink
            with patch('agents.live_price_watcher.live_price_watcher.os.unlink'):
                # Mock process_email_attachments
                live_price_watcher._process_email_attachments = MagicMock(return_value=[
                    {
                        'property_id': 'test_property_id',
                        'unit_no': 'UNO-611',
                        'old_price': 1000000,
                        'new_price': 1050000,
                        'price_change_pct': 5.0,
                        'significant_change': True
                    }
                ])
                
                # Call the method
                result = await live_price_watcher._check_for_price_updates()
                
                # Verify the result
                assert result['status'] == 'success'
                assert 'Processed 1 emails' in result['message']
                assert len(result['updates']) == 1
                
                # Verify IMAP calls
                mock_imap_instance.login.assert_called_once()
                mock_imap_instance.select.assert_called_once()
                mock_imap_instance.search.assert_called_once()
                mock_imap_instance.fetch.assert_called_once()
                mock_imap_instance.store.assert_called_once()
                mock_imap_instance.logout.assert_called_once()

@pytest.mark.asyncio
async def test_is_email_relevant(live_price_watcher):
    """Test checking if email is relevant"""
    # Create test emails
    relevant_email1 = EmailMessage()
    relevant_email1['From'] = 'sales@whiteoakwealthglobal.com'
    relevant_email1['Subject'] = 'Regular update'
    
    relevant_email2 = EmailMessage()
    relevant_email2['From'] = 'other@example.com'
    relevant_email2['Subject'] = 'Sales Offer for UNO'
    
    irrelevant_email = EmailMessage()
    irrelevant_email['From'] = 'other@example.com'
    irrelevant_email['Subject'] = 'Hello'
    
    # Test relevant emails
    assert live_price_watcher._is_email_relevant(relevant_email1) is True
    assert live_price_watcher._is_email_relevant(relevant_email2) is True
    
    # Test irrelevant email
    assert live_price_watcher._is_email_relevant(irrelevant_email) is False

@pytest.mark.asyncio
async def test_process_email_attachments(live_price_watcher):
    """Test processing email attachments"""
    # Create test email
    email_message = email.message_from_string(SAMPLE_EMAIL)
    
    # Mock tempfile
    with patch('agents.live_price_watcher.live_price_watcher.tempfile.NamedTemporaryFile', 
              mock_open(read_data=b'test data')):
        # Mock os.unlink
        with patch('agents.live_price_watcher.live_price_watcher.os.unlink'):
            # Mock update_property_prices
            live_price_watcher._update_property_prices = MagicMock(return_value=[
                {
                    'property_id': 'test_property_id',
                    'unit_no': 'UNO-611',
                    'old_price': 1000000,
                    'new_price': 1050000,
                    'price_change_pct': 5.0,
                    'significant_change': True
                }
            ])
            
            # Call the method
            result = await live_price_watcher._process_email_attachments(email_message, False)
            
            # Verify the result
            assert len(result) == 1
            assert result[0]['unit_no'] == 'UNO-611'
            assert result[0]['price_change_pct'] == 5.0
            
            # Verify data ingestor call
            live_price_watcher.data_ingestor.process.assert_called_once()
            
            # Verify update_property_prices call
            live_price_watcher._update_property_prices.assert_called_once()

@pytest.mark.asyncio
async def test_update_property_prices(live_price_watcher):
    """Test updating property prices"""
    # Test data
    extracted_data = [
        {
            'unit_no': 'UNO-611',
            'list_price_aed': '1050000'
        }
    ]
    
    # Call the method
    result = await live_price_watcher._update_property_prices(extracted_data, False)
    
    # Verify the result
    assert len(result) == 1
    assert result[0]['unit_no'] == 'UNO-611'
    assert result[0]['old_price'] == 1000000
    assert result[0]['new_price'] == 1050000
    assert result[0]['price_change_pct'] == 5.0
    assert result[0]['significant_change'] is True
    
    # Verify Zoho CRM calls
    live_price_watcher.zoho_crm.search_properties.assert_called_once()
    live_price_watcher.zoho_crm.update_property.assert_called_once()
    
    # Verify regenerate_proposals call
    live_price_watcher._regenerate_proposals.assert_called_once_with(
        'test_property_id', 'UNO-611', 1050000
    )

@pytest.mark.asyncio
async def test_regenerate_proposals(live_price_watcher):
    """Test regenerating proposals"""
    # Call the method
    await live_price_watcher._regenerate_proposals('test_property_id', 'UNO-611', 1050000)
    
    # Verify Zoho CRM calls
    live_price_watcher.zoho_crm.search_records.assert_called_once_with(
        'Proposals', {'criteria': 'Property_ID:equals:test_property_id'}
    )
    
    # Verify proposal writer call
    live_price_watcher.proposal_writer.process.assert_called_once_with({
        'property_id': 'test_property_id',
        'contact_id': 'test_contact_id',
        'language': 'en'
    })
    
    # Verify Zoho CRM update call
    live_price_watcher.zoho_crm.update_record.assert_called_once()
