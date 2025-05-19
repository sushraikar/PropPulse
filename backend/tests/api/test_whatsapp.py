"""
Tests for the WhatsApp Quick-Quote integration
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import json
from fastapi import Request
from fastapi.responses import JSONResponse

from api.routes.whatsapp import (
    whatsapp_router, 
    process_whatsapp_message,
    handle_quote_command,
    handle_roi_command,
    handle_list_command,
    handle_schedule_command,
    handle_help_command
)

# Sample property data
SAMPLE_PROPERTY = {
    'id': 'test_property_id',
    'Unit_No': 'UNO-611',
    'List_Price_AED': '1117105',
    'Size_ft2': '850'
}

# Sample ROI data
SAMPLE_ROI = {
    'status': 'success',
    'roi_data': {
        'net_yield_percentage': 9.8,
        'irr_10yr': 14.6,
        'adr': 1200,
        'occupancy_percentage': 85,
        'gross_rental_income': 372300,
        'projected_capital_appreciation': 7
    }
}

# Sample proposal data
SAMPLE_PROPOSAL = {
    'status': 'success',
    'pdf_url': 'https://app.proppulse.ai/p/UNO-611',
    'roi_json': json.dumps(SAMPLE_ROI['roi_data'])
}

@pytest.fixture
def mock_dependencies():
    """Mock dependencies for WhatsApp integration"""
    with patch('api.routes.whatsapp.ZohoCRM') as mock_zoho:
        with patch('api.routes.whatsapp.ROIcalcAgent') as mock_roi:
            with patch('api.routes.whatsapp.ProposalWriter') as mock_proposal:
                # Configure mocks
                mock_zoho_instance = MagicMock()
                mock_zoho_instance.search_properties.return_value = [SAMPLE_PROPERTY]
                mock_zoho.return_value = mock_zoho_instance
                
                mock_roi_instance = MagicMock()
                mock_roi_instance.process.return_value = SAMPLE_ROI
                mock_roi.return_value = mock_roi_instance
                
                mock_proposal_instance = MagicMock()
                mock_proposal_instance.process.return_value = SAMPLE_PROPOSAL
                mock_proposal.return_value = mock_proposal_instance
                
                # Set global variables
                global zoho_crm, roi_calc_agent, proposal_writer
                zoho_crm = mock_zoho_instance
                roi_calc_agent = mock_roi_instance
                proposal_writer = mock_proposal_instance
                
                yield

@pytest.mark.asyncio
async def test_process_whatsapp_message_quote(mock_dependencies):
    """Test processing QUOTE command"""
    # Mock handle_quote_command
    with patch('api.routes.whatsapp.handle_quote_command') as mock_handle:
        mock_handle.return_value = "Test quote response"
        
        # Call the function
        response = await process_whatsapp_message("QUOTE UNO-611")
        
        # Verify the result
        assert response == "Test quote response"
        
        # Verify handle_quote_command call
        mock_handle.assert_called_once_with("UNO-611")

@pytest.mark.asyncio
async def test_process_whatsapp_message_roi(mock_dependencies):
    """Test processing ROI command"""
    # Mock handle_roi_command
    with patch('api.routes.whatsapp.handle_roi_command') as mock_handle:
        mock_handle.return_value = "Test ROI response"
        
        # Call the function
        response = await process_whatsapp_message("ROI UNO-611")
        
        # Verify the result
        assert response == "Test ROI response"
        
        # Verify handle_roi_command call
        mock_handle.assert_called_once_with("UNO-611")

@pytest.mark.asyncio
async def test_process_whatsapp_message_list(mock_dependencies):
    """Test processing LIST command"""
    # Mock handle_list_command
    with patch('api.routes.whatsapp.handle_list_command') as mock_handle:
        mock_handle.return_value = "Test list response"
        
        # Call the function
        response = await process_whatsapp_message("LIST")
        
        # Verify the result
        assert response == "Test list response"
        
        # Verify handle_list_command call
        mock_handle.assert_called_once()

@pytest.mark.asyncio
async def test_process_whatsapp_message_schedule(mock_dependencies):
    """Test processing SCHEDULE command"""
    # Mock handle_schedule_command
    with patch('api.routes.whatsapp.handle_schedule_command') as mock_handle:
        mock_handle.return_value = "Test schedule response"
        
        # Call the function
        response = await process_whatsapp_message("SCHEDULE UNO-611")
        
        # Verify the result
        assert response == "Test schedule response"
        
        # Verify handle_schedule_command call
        mock_handle.assert_called_once_with("UNO-611")

@pytest.mark.asyncio
async def test_process_whatsapp_message_help(mock_dependencies):
    """Test processing HELP command"""
    # Mock handle_help_command
    with patch('api.routes.whatsapp.handle_help_command') as mock_handle:
        mock_handle.return_value = "Test help response"
        
        # Call the function
        response = await process_whatsapp_message("HELP")
        
        # Verify the result
        assert response == "Test help response"
        
        # Verify handle_help_command call
        mock_handle.assert_called_once()

@pytest.mark.asyncio
async def test_process_whatsapp_message_unknown(mock_dependencies):
    """Test processing unknown command"""
    # Call the function
    response = await process_whatsapp_message("UNKNOWN COMMAND")
    
    # Verify the result
    assert "I don't understand that command" in response
    assert "HELP" in response

@pytest.mark.asyncio
async def test_handle_quote_command(mock_dependencies):
    """Test handling QUOTE command"""
    # Call the function
    response = await handle_quote_command("UNO-611")
    
    # Verify the result
    assert "UNO-611" in response
    assert "AED 1,117,105" in response
    assert "9.8 %" in response
    assert "14.6 %" in response
    assert "https://app.proppulse.ai/p/UNO-611" in response
    
    # Verify dependencies calls
    zoho_crm.search_properties.assert_called_once()
    roi_calc_agent.process.assert_called_once()
    proposal_writer.process.assert_called_once()

@pytest.mark.asyncio
async def test_handle_roi_command(mock_dependencies):
    """Test handling ROI command"""
    # Call the function
    response = await handle_roi_command("UNO-611")
    
    # Verify the result
    assert "ROI Stats for UNO-611" in response
    assert "AED 1,117,105" in response
    assert "850 ft²" in response
    assert "AED 1200" in response
    assert "85 %" in response
    assert "9.8 %" in response
    assert "14.6 %" in response
    assert "7 %" in response
    assert "QUOTE UNO-611" in response
    
    # Verify dependencies calls
    zoho_crm.search_properties.assert_called_once()
    roi_calc_agent.process.assert_called_once()

@pytest.mark.asyncio
async def test_handle_list_command(mock_dependencies):
    """Test handling LIST command"""
    # Mock zoho_crm.search_properties to return multiple properties
    zoho_crm.search_properties.return_value = [
        {'id': 'id1', 'Unit_No': 'UNO-611', 'List_Price_AED': '1000000'},
        {'id': 'id2', 'Unit_No': 'UNO-612', 'List_Price_AED': '1100000'},
        {'id': 'id3', 'Unit_No': 'UNO-613', 'List_Price_AED': '1200000'},
        {'id': 'id4', 'Unit_No': 'UNO-614', 'List_Price_AED': '1300000'},
        {'id': 'id5', 'Unit_No': 'UNO-615', 'List_Price_AED': '1400000'}
    ]
    
    # Call the function
    response = await handle_list_command()
    
    # Verify the result
    assert "Top 5 Units by Yield" in response
    assert "UNO-611" in response
    assert "UNO-612" in response
    assert "UNO-613" in response
    assert "UNO-614" in response
    assert "UNO-615" in response
    assert "QUOTE" in response
    
    # Verify dependencies calls
    zoho_crm.search_properties.assert_called_once()
    assert roi_calc_agent.process.call_count == 5

@pytest.mark.asyncio
async def test_handle_schedule_command(mock_dependencies):
    """Test handling SCHEDULE command"""
    # Call the function
    response = await handle_schedule_command("UNO-611")
    
    # Verify the result
    assert "Payment Schedule for UNO-611" in response
    assert "Next Milestone" in response
    assert "Amount Due" in response
    assert "AED" in response
    assert "QUOTE UNO-611" in response
    
    # Verify dependencies calls
    zoho_crm.search_properties.assert_called_once()

def test_handle_help_command():
    """Test handling HELP command"""
    # Call the function
    response = handle_help_command()
    
    # Verify the result
    assert "PropPulse WhatsApp Commands" in response
    assert "QUOTE" in response
    assert "ROI" in response
    assert "LIST" in response
    assert "SCHEDULE" in response
    assert "HELP" in response
