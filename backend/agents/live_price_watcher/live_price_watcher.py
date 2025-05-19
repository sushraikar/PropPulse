"""
LivePriceWatcher for PropPulse
Monitors email inbox for price sheet attachments and updates property prices
"""
import os
import re
import imaplib
import email
import tempfile
import logging
import asyncio
import time
from datetime import datetime
from email.header import decode_header
from typing import Dict, Any, List, Optional, Tuple, Union
import threading

# Import base agent and data ingestor
from agents.base_agent import BaseAgent
from agents.data_ingestor.data_ingestor import DataIngestor
from agents.proposal_writer.proposal_writer import ProposalWriter
from integrations.zoho.zoho_crm import ZohoCRM
from db.models.property import Property

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LivePriceWatcher(BaseAgent):
    """
    LivePriceWatcher monitors an email inbox for price sheet attachments
    and updates property prices in the database.
    
    Responsibilities:
    - Connect to IMAP server and monitor inbox
    - Filter emails by sender and subject
    - Download and process attachments
    - Pipe attachments to DataIngestor
    - Update property prices
    - Trigger proposal regeneration for significant price changes
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the LivePriceWatcher"""
        super().__init__(config)
        
        # Email configuration
        self.email_config = config.get('email_config', {})
        self.imap_server = self.email_config.get('imap_server', 'outlook.office365.com')
        self.email_address = self.email_config.get('email_address', os.getenv('EMAIL_ADDRESS'))
        self.email_password = self.email_config.get('email_password', os.getenv('EMAIL_PASSWORD'))
        self.mailbox = self.email_config.get('mailbox', 'PriceSheets')
        
        # Email filtering
        self.sender_patterns = [
            '*@whiteoakwealthglobal.com'
        ]
        self.subject_patterns = [
            'Sales Offer',
            'Price Sheet'
        ]
        self.attachment_regex = r'^(SO_|RateSheet_).*\.(pdf|xls|xlsx)$'
        
        # Price change threshold (percentage)
        self.price_change_threshold = 2.0
        
        # Initialize DataIngestor
        self.data_ingestor = DataIngestor(config.get('data_ingestor_config'))
        
        # Initialize ProposalWriter
        self.proposal_writer = ProposalWriter(config.get('proposal_writer_config'))
        
        # Initialize Zoho CRM client
        self.zoho_crm = ZohoCRM(config.get('zoho_config'))
        
        # Polling interval (seconds)
        self.polling_interval = config.get('polling_interval', 300)  # 5 minutes
        
        # Watcher thread
        self.watcher_thread = None
        self.stop_event = threading.Event()
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process command to start/stop watcher or manually check for price updates
        
        Args:
            input_data: Dictionary containing:
                - command: 'start', 'stop', or 'check_now'
                - force_process: (optional) Force processing even if no price change
                
        Returns:
            Dict containing:
                - status: Processing status
                - message: Status message
                - updates: List of updated properties (if any)
        """
        command = input_data.get('command')
        
        if not command:
            return {
                'status': 'error',
                'message': 'Missing required input: command'
            }
        
        if command == 'start':
            return await self._start_watcher()
        elif command == 'stop':
            return await self._stop_watcher()
        elif command == 'check_now':
            force_process = input_data.get('force_process', False)
            return await self._check_for_price_updates(force_process)
        else:
            return {
                'status': 'error',
                'message': f"Invalid command: {command}. Valid commands are 'start', 'stop', 'check_now'"
            }
    
    async def _start_watcher(self) -> Dict[str, Any]:
        """
        Start the email watcher thread
        
        Returns:
            Status dictionary
        """
        if self.watcher_thread and self.watcher_thread.is_alive():
            return {
                'status': 'warning',
                'message': 'Watcher is already running'
            }
        
        # Reset stop event
        self.stop_event.clear()
        
        # Start watcher thread
        self.watcher_thread = threading.Thread(
            target=self._watcher_loop,
            daemon=True
        )
        self.watcher_thread.start()
        
        return {
            'status': 'success',
            'message': f"Watcher started. Polling every {self.polling_interval} seconds"
        }
    
    async def _stop_watcher(self) -> Dict[str, Any]:
        """
        Stop the email watcher thread
        
        Returns:
            Status dictionary
        """
        if not self.watcher_thread or not self.watcher_thread.is_alive():
            return {
                'status': 'warning',
                'message': 'Watcher is not running'
            }
        
        # Set stop event
        self.stop_event.set()
        
        # Wait for thread to terminate
        self.watcher_thread.join(timeout=10)
        
        if self.watcher_thread.is_alive():
            return {
                'status': 'error',
                'message': 'Failed to stop watcher thread'
            }
        
        return {
            'status': 'success',
            'message': 'Watcher stopped'
        }
    
    def _watcher_loop(self):
        """
        Main watcher loop - runs in a separate thread
        """
        logger.info("Starting LivePriceWatcher loop")
        
        while not self.stop_event.is_set():
            try:
                # Run the check in the event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Check for price updates
                result = loop.run_until_complete(self._check_for_price_updates())
                
                if result['status'] == 'success' and result.get('updates'):
                    logger.info(f"Processed {len(result['updates'])} price updates")
                
                # Close the event loop
                loop.close()
                
            except Exception as e:
                logger.error(f"Error in watcher loop: {str(e)}")
            
            # Sleep until next check
            for _ in range(self.polling_interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        
        logger.info("LivePriceWatcher loop stopped")
    
    async def _check_for_price_updates(self, force_process: bool = False) -> Dict[str, Any]:
        """
        Check for price updates in email inbox
        
        Args:
            force_process: Force processing even if no price change
            
        Returns:
            Status dictionary with updates
        """
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_address, self.email_password)
            mail.select(self.mailbox)
            
            # Search for unread emails
            search_criteria = '(UNSEEN)'
            result, data = mail.search(None, search_criteria)
            
            if result != 'OK':
                return {
                    'status': 'error',
                    'message': f"Failed to search mailbox: {result}"
                }
            
            # Get email IDs
            email_ids = data[0].split()
            
            if not email_ids:
                return {
                    'status': 'success',
                    'message': 'No new emails found',
                    'updates': []
                }
            
            # Process emails
            updates = []
            
            for email_id in email_ids:
                # Fetch email
                result, data = mail.fetch(email_id, '(RFC822)')
                
                if result != 'OK':
                    logger.warning(f"Failed to fetch email {email_id}: {result}")
                    continue
                
                # Parse email
                raw_email = data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Check sender and subject
                if not self._is_email_relevant(email_message):
                    # Mark as read and continue
                    mail.store(email_id, '+FLAGS', '\\Seen')
                    continue
                
                # Process attachments
                attachment_updates = await self._process_email_attachments(email_message, force_process)
                updates.extend(attachment_updates)
                
                # Mark as read
                mail.store(email_id, '+FLAGS', '\\Seen')
            
            # Logout
            mail.logout()
            
            return {
                'status': 'success',
                'message': f"Processed {len(email_ids)} emails, found {len(updates)} price updates",
                'updates': updates
            }
            
        except Exception as e:
            logger.error(f"Error checking for price updates: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error checking for price updates: {str(e)}"
            }
    
    def _is_email_relevant(self, email_message) -> bool:
        """
        Check if email is relevant based on sender and subject
        
        Args:
            email_message: Email message object
            
        Returns:
            True if email is relevant, False otherwise
        """
        # Get sender
        sender = self._decode_header(email_message.get('From', ''))
        
        # Get subject
        subject = self._decode_header(email_message.get('Subject', ''))
        
        # Check sender patterns
        sender_match = False
        for pattern in self.sender_patterns:
            if self._match_pattern(sender, pattern):
                sender_match = True
                break
        
        # Check subject patterns
        subject_match = False
        for pattern in self.subject_patterns:
            if pattern.lower() in subject.lower():
                subject_match = True
                break
        
        # Email is relevant if sender OR subject matches
        return sender_match or subject_match
    
    def _match_pattern(self, value: str, pattern: str) -> bool:
        """
        Match string against pattern with wildcard support
        
        Args:
            value: String to match
            pattern: Pattern with * as wildcard
            
        Returns:
            True if matches, False otherwise
        """
        # Convert pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        return bool(re.match(regex_pattern, value, re.IGNORECASE))
    
    def _decode_header(self, header: str) -> str:
        """
        Decode email header
        
        Args:
            header: Email header string
            
        Returns:
            Decoded header string
        """
        decoded_header = decode_header(header)
        result = ""
        
        for part, encoding in decoded_header:
            if isinstance(part, bytes):
                if encoding:
                    result += part.decode(encoding)
                else:
                    result += part.decode('utf-8', errors='replace')
            else:
                result += part
        
        return result
    
    async def _process_email_attachments(self, email_message, force_process: bool) -> List[Dict[str, Any]]:
        """
        Process email attachments
        
        Args:
            email_message: Email message object
            force_process: Force processing even if no price change
            
        Returns:
            List of property updates
        """
        updates = []
        
        # Check if email has attachments
        if not email_message.is_multipart():
            return updates
        
        # Process each part
        for part in email_message.walk():
            # Check if part is an attachment
            if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                continue
            
            # Get filename
            filename = part.get_filename()
            if not filename:
                continue
            
            # Decode filename if needed
            filename = self._decode_header(filename)
            
            # Check if filename matches pattern
            if not re.match(self.attachment_regex, filename, re.IGNORECASE):
                logger.info(f"Skipping attachment: {filename} (doesn't match pattern)")
                continue
            
            logger.info(f"Processing attachment: {filename}")
            
            # Save attachment to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_file.write(part.get_payload(decode=True))
                temp_path = temp_file.name
            
            try:
                # Process attachment with DataIngestor
                ingest_result = await self.data_ingestor.process({
                    'file_path': temp_path,
                    'file_type': os.path.splitext(filename)[1][1:],  # Remove dot from extension
                    'project_code': self._extract_project_code(filename)
                })
                
                if ingest_result['status'] != 'success':
                    logger.error(f"Failed to ingest attachment: {ingest_result['message']}")
                    continue
                
                # Update property prices and check for significant changes
                price_updates = await self._update_property_prices(ingest_result['extracted_data'], force_process)
                updates.extend(price_updates)
                
            finally:
                # Remove temp file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {temp_path}: {str(e)}")
        
        return updates
    
    def _extract_project_code(self, filename: str) -> Optional[str]:
        """
        Extract project code from filename
        
        Args:
            filename: Attachment filename
            
        Returns:
            Project code or None
        """
        # Common patterns:
        # SO_UNO_20250519.pdf -> UNO
        # RateSheet_UNO_LUXE_Q2_2025.xlsx -> UNO_LUXE
        
        # Remove prefix and extension
        name_only = re.sub(r'^(SO_|RateSheet_)', '', filename)
        name_only = os.path.splitext(name_only)[0]
        
        # Split by underscore
        parts = name_only.split('_')
        
        if len(parts) >= 1:
            # For Uno Luxe, return UNO
            if parts[0].upper() == 'UNO':
                return 'UNO'
        
        # Default to first part
        return parts[0] if parts else None
    
    async def _update_property_prices(self, extracted_data: List[Dict[str, Any]], force_process: bool) -> List[Dict[str, Any]]:
        """
        Update property prices and check for significant changes
        
        Args:
            extracted_data: List of extracted property data
            force_process: Force processing even if no price change
            
        Returns:
            List of property updates
        """
        updates = []
        
        for property_data in extracted_data:
            # Skip if no unit number or price
            if not property_data.get('unit_no') or not property_data.get('list_price_aed'):
                continue
            
            unit_no = property_data['unit_no']
            new_price = float(property_data['list_price_aed'])
            
            # Find property in Zoho CRM
            try:
                zoho_property = await self.zoho_crm.search_properties({
                    'criteria': f"Unit_No:equals:{unit_no}"
                })
                
                if not zoho_property or len(zoho_property) == 0:
                    logger.warning(f"Property not found in Zoho CRM: {unit_no}")
                    continue
                
                property_id = zoho_property[0]['id']
                old_price = float(zoho_property[0].get('List_Price_AED', 0))
                
                # Calculate price change percentage
                price_change_pct = 0
                if old_price > 0:
                    price_change_pct = ((new_price - old_price) / old_price) * 100
                
                # Check if price change is significant
                significant_change = abs(price_change_pct) >= self.price_change_threshold
                
                # Update property in Zoho CRM
                update_data = {
                    'List_Price_AED': new_price,
                    'Last_Price_Update': datetime.now().isoformat(),
                    'Price_Change_Percentage': round(price_change_pct, 2)
                }
                
                await self.zoho_crm.update_property(property_id, update_data)
                
                # Add to updates
                update_info = {
                    'property_id': property_id,
                    'unit_no': unit_no,
                    'old_price': old_price,
                    'new_price': new_price,
                    'price_change_pct': round(price_change_pct, 2),
                    'significant_change': significant_change
                }
                
                updates.append(update_info)
                
                # Regenerate proposals if significant change or forced
                if significant_change or force_process:
                    await self._regenerate_proposals(property_id, unit_no, new_price)
                
            except Exception as e:
                logger.error(f"Error updating property {unit_no}: {str(e)}")
        
        return updates
    
    async def _regenerate_proposals(self, property_id: str, unit_no: str, new_price: float) -> None:
        """
        Regenerate proposals for property
        
        Args:
            property_id: Zoho CRM Property ID
            unit_no: Unit number
            new_price: New price
        """
        try:
            # Find proposals for this property
            proposals = await self.zoho_crm.search_records('Proposals', {
                'criteria': f"Property_ID:equals:{property_id}"
            })
            
            if not proposals:
                logger.info(f"No proposals found for property {unit_no}")
                return
            
            logger.info(f"Regenerating {len(proposals)} proposals for property {unit_no}")
            
            # Regenerate each proposal
            for proposal in proposals:
                proposal_id = proposal['id']
                contact_id = proposal.get('Contact_Name', {}).get('id')
                language = proposal.get('Language', 'en')
                
                if not contact_id:
                    logger.warning(f"No contact found for proposal {proposal_id}")
                    continue
                
                # Regenerate proposal
                result = await self.proposal_writer.process({
                    'property_id': property_id,
                    'contact_id': contact_id,
                    'language': language
                })
                
                if result['status'] != 'success':
                    logger.error(f"Failed to regenerate proposal {proposal_id}: {result['message']}")
                    continue
                
                # Update proposal in Zoho CRM
                update_data = {
                    'PDF_Link': result['pdf_url'],
                    'ROI_JSON': result['roi_json'],
                    'Created_On': datetime.now().isoformat()
                }
                
                await self.zoho_crm.update_record('Proposals', proposal_id, update_data)
                
                logger.info(f"Regenerated proposal {proposal_id} for property {unit_no}")
                
        except Exception as e:
            logger.error(f"Error regenerating proposals for property {unit_no}: {str(e)}")
