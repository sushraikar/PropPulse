"""
WhatsApp Quick-Quote for PropPulse
Handles WhatsApp messages via Twilio webhook and provides quick property quotes
"""
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from twilio.rest import Client
from twilio.request_validator import RequestValidator

# Import agents and integrations
from agents.roi_calc_agent.roi_calc_agent import ROIcalcAgent
from agents.proposal_writer.proposal_writer import ProposalWriter
from integrations.zoho.zoho_crm import ZohoCRM

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router
whatsapp_router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

# Twilio client
twilio_client = None

# Agents and integrations
zoho_crm = None
roi_calc_agent = None
proposal_writer = None

def initialize(config: Dict[str, Any]):
    """Initialize WhatsApp Quick-Quote with configuration"""
    global twilio_client, zoho_crm, roi_calc_agent, proposal_writer
    
    # Initialize Twilio client
    twilio_account_sid = config.get('twilio_account_sid', os.getenv('TWILIO_ACCOUNT_SID'))
    twilio_auth_token = config.get('twilio_auth_token', os.getenv('TWILIO_AUTH_TOKEN'))
    
    if twilio_account_sid and twilio_auth_token:
        twilio_client = Client(twilio_account_sid, twilio_auth_token)
    
    # Initialize Zoho CRM
    zoho_crm = ZohoCRM(config.get('zoho_config'))
    
    # Initialize ROI calculator
    roi_calc_agent = ROIcalcAgent(config.get('roi_calc_config'))
    
    # Initialize Proposal writer
    proposal_writer = ProposalWriter(config.get('proposal_writer_config'))

def validate_twilio_request(request: Request) -> bool:
    """Validate that the request is from Twilio"""
    # Get Twilio auth token
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set, skipping validation")
        return True
    
    # Create validator
    validator = RequestValidator(auth_token)
    
    # Get request data
    form_data = await request.form()
    
    # Get request URL and headers
    url = str(request.url)
    signature = request.headers.get('X-Twilio-Signature', '')
    
    # Validate request
    return validator.validate(url, form_data, signature)

@whatsapp_router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """
    Webhook for WhatsApp messages via Twilio
    
    Handles the following commands:
    - QUOTE <unit_no> - Return full quote with PDF link
    - ROI <unit_no> - Return short ROI stats (no PDF)
    - LIST - Return top-5 available units sorted by yield
    - SCHEDULE <unit_no> - Return next milestone date & amount
    - HELP - Return command list
    """
    # Validate request
    if not validate_twilio_request(request):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    
    # Parse request
    form_data = await request.form()
    
    # Get message data
    message_body = form_data.get('Body', '').strip()
    from_number = form_data.get('From', '')
    
    # Process message
    response_message = await process_whatsapp_message(message_body)
    
    # Return response in Twilio format
    return {
        "response": "success",
        "message": response_message
    }

async def process_whatsapp_message(message: str) -> str:
    """
    Process WhatsApp message and return response
    
    Args:
        message: Message text
        
    Returns:
        Response message
    """
    # Convert to uppercase for case-insensitive matching
    message_upper = message.upper()
    
    # Check command type
    if message_upper.startswith('QUOTE '):
        return await handle_quote_command(message[6:].strip())
    
    elif message_upper.startswith('ROI '):
        return await handle_roi_command(message[4:].strip())
    
    elif message_upper == 'LIST':
        return await handle_list_command()
    
    elif message_upper.startswith('SCHEDULE '):
        return await handle_schedule_command(message[9:].strip())
    
    elif message_upper == 'HELP':
        return handle_help_command()
    
    else:
        return "I don't understand that command. Type HELP for options."

async def handle_quote_command(unit_no: str) -> str:
    """
    Handle QUOTE command
    
    Args:
        unit_no: Unit number
        
    Returns:
        Formatted quote response
    """
    try:
        # Find property in Zoho CRM
        properties = await zoho_crm.search_properties({
            'criteria': f"Unit_No:equals:{unit_no}"
        })
        
        if not properties or len(properties) == 0:
            return f"Sorry, I couldn't find unit {unit_no}. Please check the unit number and try again."
        
        property_data = properties[0]
        property_id = property_data['id']
        
        # Calculate ROI
        roi_result = await roi_calc_agent.process({
            'property_id': property_id
        })
        
        if roi_result['status'] != 'success':
            return f"Sorry, I couldn't calculate ROI for unit {unit_no}. Please try again later."
        
        # Generate or get existing proposal
        proposal_result = await proposal_writer.process({
            'property_id': property_id,
            'language': 'en'
        })
        
        if proposal_result['status'] != 'success':
            return f"Sorry, I couldn't generate a proposal for unit {unit_no}. Please try again later."
        
        # Format response according to specified format
        price = property_data.get('List_Price_AED', 'N/A')
        if price != 'N/A':
            price = f"AED {int(float(price)):,}"
        
        net_yield = roi_result.get('roi_data', {}).get('net_yield_percentage', 'N/A')
        if net_yield != 'N/A':
            net_yield = f"{net_yield:.1f} %"
        
        irr = roi_result.get('roi_data', {}).get('irr_10yr', 'N/A')
        if irr != 'N/A':
            irr = f"{irr:.1f} %"
        
        pdf_url = proposal_result.get('pdf_url', 'N/A')
        
        response = f"""*{unit_no}*
Price: {price}
Net Yield: {net_yield}
10-yr IRR: {irr}
PDF 👉 {pdf_url}"""
        
        return response
        
    except Exception as e:
        logger.error(f"Error handling QUOTE command: {str(e)}")
        return f"Sorry, I encountered an error while processing your request. Please try again later."

async def handle_roi_command(unit_no: str) -> str:
    """
    Handle ROI command
    
    Args:
        unit_no: Unit number
        
    Returns:
        Formatted ROI response
    """
    try:
        # Find property in Zoho CRM
        properties = await zoho_crm.search_properties({
            'criteria': f"Unit_No:equals:{unit_no}"
        })
        
        if not properties or len(properties) == 0:
            return f"Sorry, I couldn't find unit {unit_no}. Please check the unit number and try again."
        
        property_data = properties[0]
        property_id = property_data['id']
        
        # Calculate ROI
        roi_result = await roi_calc_agent.process({
            'property_id': property_id
        })
        
        if roi_result['status'] != 'success':
            return f"Sorry, I couldn't calculate ROI for unit {unit_no}. Please try again later."
        
        # Format response
        roi_data = roi_result.get('roi_data', {})
        
        price = property_data.get('List_Price_AED', 'N/A')
        if price != 'N/A':
            price = f"AED {int(float(price)):,}"
        
        size = property_data.get('Size_ft2', 'N/A')
        if size != 'N/A':
            size = f"{int(float(size))} ft²"
        
        adr = roi_data.get('adr', 'N/A')
        if adr != 'N/A':
            adr = f"AED {int(adr)}"
        
        occupancy = roi_data.get('occupancy_percentage', 'N/A')
        if occupancy != 'N/A':
            occupancy = f"{occupancy} %"
        
        gross_income = roi_data.get('gross_rental_income', 'N/A')
        if gross_income != 'N/A':
            gross_income = f"AED {int(gross_income):,}/yr"
        
        net_yield = roi_data.get('net_yield_percentage', 'N/A')
        if net_yield != 'N/A':
            net_yield = f"{net_yield:.1f} %"
        
        irr = roi_data.get('irr_10yr', 'N/A')
        if irr != 'N/A':
            irr = f"{irr:.1f} %"
        
        cagr = roi_data.get('projected_capital_appreciation', 'N/A')
        if cagr != 'N/A':
            cagr = f"{cagr} %"
        
        response = f"""*ROI Stats for {unit_no}*

Price: {price}
Size: {size}

ADR: {adr}
Occupancy: {occupancy}
Gross Income: {gross_income}
Net Yield: {net_yield}
10-yr IRR: {irr}
Proj. CAGR: {cagr}

Type QUOTE {unit_no} for full proposal with PDF."""
        
        return response
        
    except Exception as e:
        logger.error(f"Error handling ROI command: {str(e)}")
        return f"Sorry, I encountered an error while processing your request. Please try again later."

async def handle_list_command() -> str:
    """
    Handle LIST command
    
    Returns:
        Formatted list of top 5 units by yield
    """
    try:
        # Get available properties
        properties = await zoho_crm.search_properties({
            'criteria': "Status:equals:Available"
        })
        
        if not properties or len(properties) == 0:
            return "Sorry, there are no available units at the moment."
        
        # Calculate ROI for each property
        property_yields = []
        
        for property_data in properties[:20]:  # Limit to first 20 to avoid too many API calls
            property_id = property_data['id']
            unit_no = property_data.get('Unit_No', 'Unknown')
            
            # Calculate ROI
            roi_result = await roi_calc_agent.process({
                'property_id': property_id
            })
            
            if roi_result['status'] != 'success':
                continue
            
            net_yield = roi_result.get('roi_data', {}).get('net_yield_percentage', 0)
            
            property_yields.append({
                'property_id': property_id,
                'unit_no': unit_no,
                'net_yield': net_yield,
                'price': property_data.get('List_Price_AED', 0)
            })
        
        # Sort by yield (descending)
        property_yields.sort(key=lambda x: x['net_yield'], reverse=True)
        
        # Take top 5
        top_properties = property_yields[:5]
        
        if not top_properties:
            return "Sorry, I couldn't calculate yields for any available units."
        
        # Format response
        response = "*Top 5 Units by Yield*\n\n"
        
        for i, prop in enumerate(top_properties, 1):
            price = f"AED {int(float(prop['price'])):,}" if prop['price'] else 'N/A'
            yield_pct = f"{prop['net_yield']:.1f} %" if prop['net_yield'] else 'N/A'
            
            response += f"{i}. *{prop['unit_no']}*\n"
            response += f"   Price: {price}\n"
            response += f"   Yield: {yield_pct}\n\n"
        
        response += "Type QUOTE <unit_no> for full details."
        
        return response
        
    except Exception as e:
        logger.error(f"Error handling LIST command: {str(e)}")
        return f"Sorry, I encountered an error while processing your request. Please try again later."

async def handle_schedule_command(unit_no: str) -> str:
    """
    Handle SCHEDULE command
    
    Args:
        unit_no: Unit number
        
    Returns:
        Formatted schedule response
    """
    try:
        # Find property in Zoho CRM
        properties = await zoho_crm.search_properties({
            'criteria': f"Unit_No:equals:{unit_no}"
        })
        
        if not properties or len(properties) == 0:
            return f"Sorry, I couldn't find unit {unit_no}. Please check the unit number and try again."
        
        property_data = properties[0]
        
        # Get payment schedule
        # This would typically come from a payment schedule field in Zoho CRM
        # For now, we'll use placeholder data
        
        # Placeholder: Next milestone is 10% payment in 30 days
        price = float(property_data.get('List_Price_AED', 0))
        next_amount = price * 0.1
        next_date = "June 19, 2025"  # 30 days from now
        
        response = f"""*Payment Schedule for {unit_no}*

Next Milestone: {next_date}
Amount Due: AED {int(next_amount):,} (10%)

Type QUOTE {unit_no} for full proposal with payment plan."""
        
        return response
        
    except Exception as e:
        logger.error(f"Error handling SCHEDULE command: {str(e)}")
        return f"Sorry, I encountered an error while processing your request. Please try again later."

def handle_help_command() -> str:
    """
    Handle HELP command
    
    Returns:
        Help message with available commands
    """
    return """*PropPulse WhatsApp Commands*

QUOTE <unit_no>
Get full investment proposal with PDF link

ROI <unit_no>
View ROI statistics for a unit

LIST
See top 5 available units by yield

SCHEDULE <unit_no>
Check next payment milestone

HELP
Show this command list"""

def send_whatsapp_message(to: str, body: str) -> bool:
    """
    Send WhatsApp message via Twilio
    
    Args:
        to: Recipient phone number (with WhatsApp format)
        body: Message body
        
    Returns:
        True if successful, False otherwise
    """
    if not twilio_client:
        logger.error("Twilio client not initialized")
        return False
    
    try:
        # Ensure 'to' has WhatsApp format
        if not to.startswith('whatsapp:'):
            to = f"whatsapp:{to}"
        
        # Get WhatsApp from number from environment
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        if not from_number:
            logger.error("TWILIO_WHATSAPP_NUMBER not set")
            return False
        
        if not from_number.startswith('whatsapp:'):
            from_number = f"whatsapp:{from_number}"
        
        # Send message
        message = twilio_client.messages.create(
            body=body,
            from_=from_number,
            to=to
        )
        
        logger.info(f"Sent WhatsApp message: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False
