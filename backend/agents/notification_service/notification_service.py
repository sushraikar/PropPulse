"""
Notification service for PropPulse platform

Handles email, SMS, and WhatsApp notifications for various events:
- Funding milestones (25%, 50%, 100%)
- Token minting confirmations
- Rent distribution executions
"""
import os
import logging
from typing import Dict, Any, List, Optional, Union
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from twilio.rest import Client
from datetime import datetime

from db.models.co_investment import CoInvestmentGroup, CapTable, PayoutSchedule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    """
    Notification service for PropPulse
    
    Handles sending notifications via email, SMS, and WhatsApp
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the NotificationService"""
        self.config = config or {}
        
        # Email configuration
        self.smtp_server = self.config.get('smtp_server', os.getenv('SMTP_SERVER', 'smtp.office365.com'))
        self.smtp_port = self.config.get('smtp_port', int(os.getenv('SMTP_PORT', '587')))
        self.smtp_username = self.config.get('smtp_username', os.getenv('SMTP_USERNAME'))
        self.smtp_password = self.config.get('smtp_password', os.getenv('SMTP_PASSWORD'))
        self.email_from = self.config.get('email_from', os.getenv('EMAIL_FROM', 'notifications@proppulse.ai'))
        
        # Twilio configuration for SMS and WhatsApp
        self.twilio_account_sid = self.config.get('twilio_account_sid', os.getenv('TWILIO_ACCOUNT_SID'))
        self.twilio_auth_token = self.config.get('twilio_auth_token', os.getenv('TWILIO_AUTH_TOKEN'))
        self.twilio_phone_number = self.config.get('twilio_phone_number', os.getenv('TWILIO_PHONE_NUMBER'))
        self.twilio_whatsapp_number = self.config.get('twilio_whatsapp_number', os.getenv('TWILIO_WHATSAPP_NUMBER'))
        
        # Initialize Twilio client if credentials are available
        self.twilio_client = None
        if self.twilio_account_sid and self.twilio_auth_token:
            self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send email notification
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            
        Returns:
            Email sending result
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = to_email
            
            # Add CC if provided
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add BCC if provided
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Add text body if provided
            if body_text:
                msg.attach(MIMEText(body_text, 'plain'))
            
            # Add HTML body
            msg.attach(MIMEText(body_html, 'html'))
            
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                
                # Get all recipients
                all_recipients = [to_email]
                if cc:
                    all_recipients.extend(cc)
                if bcc:
                    all_recipients.extend(bcc)
                
                # Send email
                server.sendmail(self.email_from, all_recipients, msg.as_string())
            
            return {
                'status': 'success',
                'message': f"Email sent to {to_email}",
                'to_email': to_email,
                'subject': subject
            }
        
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send email: {str(e)}",
                'to_email': to_email
            }
    
    async def send_sms(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send SMS notification
        
        Args:
            to_phone: Recipient phone number (E.164 format)
            message: SMS message
            
        Returns:
            SMS sending result
        """
        try:
            # Check if Twilio client is initialized
            if not self.twilio_client:
                return {
                    'status': 'error',
                    'message': 'Twilio client not initialized',
                    'to_phone': to_phone
                }
            
            # Send SMS
            sms = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=to_phone
            )
            
            return {
                'status': 'success',
                'message': f"SMS sent to {to_phone}",
                'to_phone': to_phone,
                'twilio_sid': sms.sid
            }
        
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send SMS: {str(e)}",
                'to_phone': to_phone
            }
    
    async def send_whatsapp(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send WhatsApp notification
        
        Args:
            to_phone: Recipient phone number (E.164 format)
            message: WhatsApp message
            
        Returns:
            WhatsApp sending result
        """
        try:
            # Check if Twilio client is initialized
            if not self.twilio_client:
                return {
                    'status': 'error',
                    'message': 'Twilio client not initialized',
                    'to_phone': to_phone
                }
            
            # Format WhatsApp number
            whatsapp_to = f"whatsapp:{to_phone}"
            whatsapp_from = f"whatsapp:{self.twilio_whatsapp_number}"
            
            # Send WhatsApp message
            whatsapp = self.twilio_client.messages.create(
                body=message,
                from_=whatsapp_from,
                to=whatsapp_to
            )
            
            return {
                'status': 'success',
                'message': f"WhatsApp message sent to {to_phone}",
                'to_phone': to_phone,
                'twilio_sid': whatsapp.sid
            }
        
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send WhatsApp message: {str(e)}",
                'to_phone': to_phone
            }
    
    async def notify_funding_milestone(
        self,
        co_investment_group: CoInvestmentGroup,
        milestone_percentage: int,
        db_session
    ) -> Dict[str, Any]:
        """
        Send funding milestone notifications
        
        Args:
            co_investment_group: Co-investment group
            milestone_percentage: Milestone percentage (25, 50, 100)
            db_session: Database session
            
        Returns:
            Notification result
        """
        try:
            # Get all investors in this group
            investors = db_session.query(CapTable).filter(
                CapTable.co_investment_group_id == co_investment_group.id
            ).all()
            
            # Get property details
            property_id = co_investment_group.property_id
            
            # Prepare notification content
            subject = f"PropPulse: {property_id} Funding Milestone - {milestone_percentage}% Reached"
            
            # HTML email body
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4A90E2; color: white; padding: 10px 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #999; }}
                    .button {{ display: inline-block; background-color: #4A90E2; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>PropPulse Funding Update</h2>
                    </div>
                    <div class="content">
                        <h3>Exciting News! {milestone_percentage}% Funding Milestone Reached</h3>
                        <p>Dear Investor,</p>
                        <p>We're pleased to inform you that the {property_id} syndicate has reached {milestone_percentage}% of its funding target.</p>
                        
                        <p><strong>Property:</strong> {property_id}<br>
                        <strong>Current Funding:</strong> {milestone_percentage}%<br>
                        <strong>Target Amount:</strong> AED {co_investment_group.target_raise:,.2f}</p>
                        
                        <p>This is an important milestone in our journey to complete this investment opportunity.</p>
                        
                        <p>You can track the progress and view more details on your investor dashboard.</p>
                        
                        <a href="https://app.proppulse.ai/dashboard" class="button">View Dashboard</a>
                    </div>
                    <div class="footer">
                        <p>© 2025 PropPulse. All rights reserved.</p>
                        <p>This email was sent to you because you are an investor in the {property_id} syndicate.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text email body
            text_body = f"""
            PropPulse Funding Update
            
            Exciting News! {milestone_percentage}% Funding Milestone Reached
            
            Dear Investor,
            
            We're pleased to inform you that the {property_id} syndicate has reached {milestone_percentage}% of its funding target.
            
            Property: {property_id}
            Current Funding: {milestone_percentage}%
            Target Amount: AED {co_investment_group.target_raise:,.2f}
            
            This is an important milestone in our journey to complete this investment opportunity.
            
            You can track the progress and view more details on your investor dashboard:
            https://app.proppulse.ai/dashboard
            
            © 2025 PropPulse. All rights reserved.
            This email was sent to you because you are an investor in the {property_id} syndicate.
            """
            
            # WhatsApp/SMS message
            short_message = f"""
            PropPulse: {property_id} has reached {milestone_percentage}% funding! 🎉
            
            Track progress: https://app.proppulse.ai/dashboard
            """
            
            # Send notifications to all investors
            email_results = []
            sms_results = []
            whatsapp_results = []
            
            for investor in investors:
                # Send email
                if investor.investor_email:
                    email_result = await self.send_email(
                        to_email=investor.investor_email,
                        subject=subject,
                        body_html=html_body,
                        body_text=text_body
                    )
                    email_results.append(email_result)
                
                # Send SMS if phone number is available
                if investor.investor_phone:
                    sms_result = await self.send_sms(
                        to_phone=investor.investor_phone,
                        message=short_message
                    )
                    sms_results.append(sms_result)
                    
                    # Send WhatsApp
                    whatsapp_result = await self.send_whatsapp(
                        to_phone=investor.investor_phone,
                        message=short_message
                    )
                    whatsapp_results.append(whatsapp_result)
            
            return {
                'status': 'success',
                'message': f"Funding milestone notifications sent for {property_id} - {milestone_percentage}%",
                'property_id': property_id,
                'milestone_percentage': milestone_percentage,
                'email_results': email_results,
                'sms_results': sms_results,
                'whatsapp_results': whatsapp_results
            }
        
        except Exception as e:
            logger.error(f"Failed to send funding milestone notifications: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send funding milestone notifications: {str(e)}",
                'property_id': co_investment_group.property_id,
                'milestone_percentage': milestone_percentage
            }
    
    async def notify_token_minting(
        self,
        investor: CapTable,
        token_address: str,
        token_amount: float,
        transaction_hash: str,
        db_session
    ) -> Dict[str, Any]:
        """
        Send token minting notification
        
        Args:
            investor: Investor from cap table
            token_address: Token contract address
            token_amount: Token amount minted
            transaction_hash: Transaction hash
            db_session: Database session
            
        Returns:
            Notification result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.id == investor.co_investment_group_id
            ).first()
            
            if not co_investment_group:
                return {
                    'status': 'error',
                    'message': f"Co-investment group not found: {investor.co_investment_group_id}",
                    'investor_id': investor.id
                }
            
            # Get property details
            property_id = co_investment_group.property_id
            
            # Prepare notification content
            subject = f"PropPulse: Your {property_id} Tokens Have Been Minted"
            
            # HTML email body
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4A90E2; color: white; padding: 10px 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #999; }}
                    .button {{ display: inline-block; background-color: #4A90E2; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                    .token-details {{ background-color: #e9f7fe; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>PropPulse Token Confirmation</h2>
                    </div>
                    <div class="content">
                        <h3>Your Property Tokens Have Been Minted!</h3>
                        <p>Dear {investor.investor_name},</p>
                        <p>We're pleased to confirm that your tokens for the {property_id} property have been successfully minted to your wallet.</p>
                        
                        <div class="token-details">
                            <p><strong>Property:</strong> {property_id}<br>
                            <strong>Token Amount:</strong> {token_amount:,.6f}<br>
                            <strong>Token Contract:</strong> {token_address}<br>
                            <strong>Transaction Hash:</strong> {transaction_hash}<br>
                            <strong>Ownership Percentage:</strong> {investor.share_percentage:.2f}%</p>
                        </div>
                        
                        <p>You can view your tokens on the blockchain explorer or check your investor dashboard for more details.</p>
                        
                        <a href="https://polygonscan.com/tx/{transaction_hash}" class="button" style="margin-right: 10px;">View Transaction</a>
                        <a href="https://app.proppulse.ai/dashboard" class="button">View Dashboard</a>
                    </div>
                    <div class="footer">
                        <p>© 2025 PropPulse. All rights reserved.</p>
                        <p>This email was sent to you because you are an investor in the {property_id} syndicate.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text email body
            text_body = f"""
            PropPulse Token Confirmation
            
            Your Property Tokens Have Been Minted!
            
            Dear {investor.investor_name},
            
            We're pleased to confirm that your tokens for the {property_id} property have been successfully minted to your wallet.
            
            Property: {property_id}
            Token Amount: {token_amount:,.6f}
            Token Contract: {token_address}
            Transaction Hash: {transaction_hash}
            Ownership Percentage: {investor.share_percentage:.2f}%
            
            You can view your tokens on the blockchain explorer or check your investor dashboard for more details.
            
            View Transaction: https://polygonscan.com/tx/{transaction_hash}
            View Dashboard: https://app.proppulse.ai/dashboard
            
            © 2025 PropPulse. All rights reserved.
            This email was sent to you because you are an investor in the {property_id} syndicate.
            """
            
            # WhatsApp/SMS message
            short_message = f"""
            PropPulse: Your {property_id} tokens have been minted! 🎉
            
            Amount: {token_amount:,.6f}
            Ownership: {investor.share_percentage:.2f}%
            
            View details: https://app.proppulse.ai/dashboard
            """
            
            # Send notifications
            results = {}
            
            # Send email
            if investor.investor_email:
                email_result = await self.send_email(
                    to_email=investor.investor_email,
                    subject=subject,
                    body_html=html_body,
                    body_text=text_body
                )
                results['email'] = email_result
            
            # Send SMS if phone number is available
            if investor.investor_phone:
                sms_result = await self.send_sms(
                    to_phone=investor.investor_phone,
                    message=short_message
                )
                results['sms'] = sms_result
                
                # Send WhatsApp
                whatsapp_result = await self.send_whatsapp(
                    to_phone=investor.investor_phone,
                    message=short_message
                )
                results['whatsapp'] = whatsapp_result
            
            return {
                'status': 'success',
                'message': f"Token minting notification sent to {investor.investor_name}",
                'property_id': property_id,
                'investor_id': investor.id,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to send token minting notification: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send token minting notification: {str(e)}",
                'investor_id': investor.id
            }
    
    async def notify_rent_distribution(
        self,
        payout_schedule: PayoutSchedule,
        investor: CapTable,
        amount: float,
        transaction_hash: str,
        db_session
    ) -> Dict[str, Any]:
        """
        Send rent distribution notification
        
        Args:
            payout_schedule: Payout schedule
            investor: Investor from cap table
            amount: Distribution amount
            transaction_hash: Transaction hash
            db_session: Database session
            
        Returns:
            Notification result
        """
        try:
            # Get co-investment group
            co_investment_group = db_session.query(CoInvestmentGroup).filter(
                CoInvestmentGroup.id == payout_schedule.co_investment_group_id
            ).first()
            
            if not co_investment_group:
                return {
                    'status': 'error',
                    'message': f"Co-investment group not found: {payout_schedule.co_investment_group_id}",
                    'payout_id': payout_schedule.id
                }
            
            # Get property details
            property_id = co_investment_group.property_id
            
            # Prepare notification content
            subject = f"PropPulse: Rent Distribution for {property_id}"
            
            # HTML email body
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4A90E2; color: white; padding: 10px 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #999; }}
                    .button {{ display: inline-block; background-color: #4A90E2; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                    .distribution-details {{ background-color: #e9f7fe; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>PropPulse Rent Distribution</h2>
                    </div>
                    <div class="content">
                        <h3>Your Rental Income Has Been Distributed!</h3>
                        <p>Dear {investor.investor_name},</p>
                        <p>We're pleased to inform you that your share of the rental income for {property_id} has been distributed to your wallet.</p>
                        
                        <div class="distribution-details">
                            <p><strong>Property:</strong> {property_id}<br>
                            <strong>Distribution Amount:</strong> AED {amount:,.2f}<br>
                            <strong>Distribution Date:</strong> {datetime.now().strftime('%B %d, %Y')}<br>
                            <strong>Transaction Hash:</strong> {transaction_hash}<br>
                            <strong>Your Ownership:</strong> {investor.share_percentage:.2f}%</p>
                        </div>
                        
                        <p>This distribution represents your pro-rata share of the rental income for the property, based on your ownership percentage.</p>
                        
                        <p>You can view the transaction details on the blockchain explorer or check your investor dashboard for more information.</p>
                        
                        <a href="https://polygonscan.com/tx/{transaction_hash}" class="button" style="margin-right: 10px;">View Transaction</a>
                        <a href="https://app.proppulse.ai/dashboard" class="button">View Dashboard</a>
                    </div>
                    <div class="footer">
                        <p>© 2025 PropPulse. All rights reserved.</p>
                        <p>This email was sent to you because you are an investor in the {property_id} syndicate.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text email body
            text_body = f"""
            PropPulse Rent Distribution
            
            Your Rental Income Has Been Distributed!
            
            Dear {investor.investor_name},
            
            We're pleased to inform you that your share of the rental income for {property_id} has been distributed to your wallet.
            
            Property: {property_id}
            Distribution Amount: AED {amount:,.2f}
            Distribution Date: {datetime.now().strftime('%B %d, %Y')}
            Transaction Hash: {transaction_hash}
            Your Ownership: {investor.share_percentage:.2f}%
            
            This distribution represents your pro-rata share of the rental income for the property, based on your ownership percentage.
            
            You can view the transaction details on the blockchain explorer or check your investor dashboard for more information.
            
            View Transaction: https://polygonscan.com/tx/{transaction_hash}
            View Dashboard: https://app.proppulse.ai/dashboard
            
            © 2025 PropPulse. All rights reserved.
            This email was sent to you because you are an investor in the {property_id} syndicate.
            """
            
            # WhatsApp/SMS message
            short_message = f"""
            PropPulse: Your {property_id} rent distribution of AED {amount:,.2f} has been sent! 💰
            
            View details: https://app.proppulse.ai/dashboard
            """
            
            # Send notifications
            results = {}
            
            # Send email
            if investor.investor_email:
                email_result = await self.send_email(
                    to_email=investor.investor_email,
                    subject=subject,
                    body_html=html_body,
                    body_text=text_body
                )
                results['email'] = email_result
            
            # Send SMS if phone number is available
            if investor.investor_phone:
                sms_result = await self.send_sms(
                    to_phone=investor.investor_phone,
                    message=short_message
                )
                results['sms'] = sms_result
                
                # Send WhatsApp
                whatsapp_result = await self.send_whatsapp(
                    to_phone=investor.investor_phone,
                    message=short_message
                )
                results['whatsapp'] = whatsapp_result
            
            return {
                'status': 'success',
                'message': f"Rent distribution notification sent to {investor.investor_name}",
                'property_id': property_id,
                'investor_id': investor.id,
                'amount': amount,
                'results': results
            }
        
        except Exception as e:
            logger.error(f"Failed to send rent distribution notification: {str(e)}")
            return {
                'status': 'error',
                'message': f"Failed to send rent distribution notification: {str(e)}",
                'investor_id': investor.id
            }
