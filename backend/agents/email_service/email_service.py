"""
Email scheduling and reporting service for PropPulse developer portal.

This module provides:
1. Weekly/bi-weekly/monthly email report scheduling
2. Customizable KPI selection for reports
3. PDF report generation and delivery
4. GDPR compliance features including data purge requests
"""

import os
import json
import uuid
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Get email credentials from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
email_username = secret_client.get_secret("EMAIL-USERNAME").value
email_password = secret_client.get_secret("EMAIL-PASSWORD").value
email_server = secret_client.get_secret("EMAIL-SERVER").value
email_port = int(secret_client.get_secret("EMAIL-PORT").value)

class EmailReportService:
    """Service for scheduling and sending email reports."""
    
    def __init__(self, db: Session = None):
        """Initialize the service."""
        self.db = db
    
    async def schedule_email_reports(
        self, 
        developer_id: str, 
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Schedule email reports for a developer.
        
        Returns a dictionary with scheduling status.
        """
        try:
            # Get developer
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Validate preferences
            if not self._validate_email_preferences(preferences):
                return {"success": False, "error": "Invalid email preferences"}
            
            # Save preferences to database
            from ...db.models.email_preferences import EmailPreferences
            
            # Check if preferences already exist
            existing_preferences = self.db.query(EmailPreferences).filter_by(
                developer_id=developer_id
            ).first()
            
            if existing_preferences:
                # Update existing preferences
                existing_preferences.enabled = preferences.get("enabled", False)
                existing_preferences.frequency = preferences.get("frequency", "weekly")
                existing_preferences.day = preferences.get("day", "monday")
                existing_preferences.time = preferences.get("time", "08:00")
                existing_preferences.timezone = preferences.get("timezone", "GST")
                existing_preferences.kpis = json.dumps(preferences.get("kpis", {}))
                existing_preferences.updated_at = datetime.utcnow()
            else:
                # Create new preferences
                new_preferences = EmailPreferences(
                    id=str(uuid.uuid4()),
                    developer_id=developer_id,
                    enabled=preferences.get("enabled", False),
                    frequency=preferences.get("frequency", "weekly"),
                    day=preferences.get("day", "monday"),
                    time=preferences.get("time", "08:00"),
                    timezone=preferences.get("timezone", "GST"),
                    kpis=json.dumps(preferences.get("kpis", {})),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(new_preferences)
            
            # Commit changes
            self.db.commit()
            
            return {
                "success": True,
                "message": "Email reports scheduled successfully",
                "preferences": preferences
            }
        except Exception as e:
            print(f"Error scheduling email reports: {e}")
            return {"success": False, "error": str(e)}
    
    def _validate_email_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        Validate email preferences.
        
        Returns True if preferences are valid, False otherwise.
        """
        # Check required fields
        required_fields = ["enabled", "frequency", "day", "time", "timezone", "kpis"]
        for field in required_fields:
            if field not in preferences:
                print(f"Missing required field: {field}")
                return False
        
        # Validate frequency
        valid_frequencies = ["weekly", "bi-weekly", "monthly"]
        if preferences["frequency"] not in valid_frequencies:
            print(f"Invalid frequency: {preferences['frequency']}")
            return False
        
        # Validate day
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if preferences["day"] not in valid_days:
            print(f"Invalid day: {preferences['day']}")
            return False
        
        # Validate time format (HH:MM)
        time_str = preferences["time"]
        try:
            hours, minutes = time_str.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                print(f"Invalid time format: {time_str}")
                return False
        except:
            print(f"Invalid time format: {time_str}")
            return False
        
        # Validate timezone
        valid_timezones = ["GST", "UTC", "EST", "PST"]
        if preferences["timezone"] not in valid_timezones:
            print(f"Invalid timezone: {preferences['timezone']}")
            return False
        
        # Validate KPIs
        kpis = preferences["kpis"]
        required_kpis = ["views", "saves", "tokenized", "riskGrade", "timeOnListing", "conversion", "tokensTraded"]
        for kpi in required_kpis:
            if kpi not in kpis:
                print(f"Missing KPI: {kpi}")
                return False
            if not isinstance(kpis[kpi], bool):
                print(f"Invalid KPI value for {kpi}: {kpis[kpi]}")
                return False
        
        return True
    
    async def get_email_preferences(self, developer_id: str) -> Dict[str, Any]:
        """
        Get email preferences for a developer.
        
        Returns a dictionary with email preferences.
        """
        try:
            # Get preferences from database
            from ...db.models.email_preferences import EmailPreferences
            preferences = self.db.query(EmailPreferences).filter_by(
                developer_id=developer_id
            ).first()
            
            if not preferences:
                # Return default preferences
                return {
                    "success": True,
                    "preferences": {
                        "enabled": False,
                        "frequency": "weekly",
                        "day": "monday",
                        "time": "08:00",
                        "timezone": "GST",
                        "kpis": {
                            "views": True,
                            "saves": True,
                            "tokenized": True,
                            "riskGrade": True,
                            "timeOnListing": True,
                            "conversion": True,
                            "tokensTraded": True
                        }
                    }
                }
            
            # Parse KPIs from JSON
            kpis = json.loads(preferences.kpis)
            
            return {
                "success": True,
                "preferences": {
                    "enabled": preferences.enabled,
                    "frequency": preferences.frequency,
                    "day": preferences.day,
                    "time": preferences.time,
                    "timezone": preferences.timezone,
                    "kpis": kpis
                }
            }
        except Exception as e:
            print(f"Error getting email preferences: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_test_email(
        self, 
        developer_id: str, 
        email: str
    ) -> Dict[str, Any]:
        """
        Send a test email to verify email configuration.
        
        Returns a dictionary with sending status.
        """
        try:
            # Get developer
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Create test email
            subject = "PropPulse Analytics - Test Email"
            body = f"""
            <html>
            <body>
                <h1>PropPulse Analytics Test Email</h1>
                <p>Hello {developer.legal_name},</p>
                <p>This is a test email to verify your email configuration for PropPulse Analytics reports.</p>
                <p>If you received this email, your email configuration is working correctly.</p>
                <p>Thank you for using PropPulse!</p>
            </body>
            </html>
            """
            
            # Send email
            self._send_email(email, subject, body)
            
            return {
                "success": True,
                "message": "Test email sent successfully"
            }
        except Exception as e:
            print(f"Error sending test email: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_and_send_report(
        self, 
        developer_id: str, 
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Generate and send an analytics report for a developer.
        
        Returns a dictionary with sending status.
        """
        try:
            # Get developer
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Get email preferences
            preferences_result = await self.get_email_preferences(developer_id)
            
            if not preferences_result["success"]:
                return preferences_result
            
            preferences = preferences_result["preferences"]
            
            # Check if email reports are enabled
            if not preferences["enabled"]:
                return {"success": False, "error": "Email reports are not enabled"}
            
            # Get developer email
            developer_email = developer.primary_contact_email
            
            if not developer_email:
                return {"success": False, "error": "Developer email not found"}
            
            # Generate report in background if background_tasks is provided
            if background_tasks:
                background_tasks.add_task(
                    self._generate_and_send_report,
                    developer,
                    developer_email,
                    preferences
                )
                
                return {
                    "success": True,
                    "status": "processing",
                    "message": "Report generation started in background"
                }
            else:
                # Generate report synchronously
                return await self._generate_and_send_report(
                    developer,
                    developer_email,
                    preferences
                )
        except Exception as e:
            print(f"Error generating and sending report: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_and_send_report(
        self,
        developer: Any,
        email: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate and send an analytics report for a developer.
        
        Returns a dictionary with sending status.
        """
        try:
            # Generate PDF report
            from ...agents.analytics.analytics_agent import AnalyticsAgent
            analytics_agent = AnalyticsAgent(self.db)
            
            report_result = await analytics_agent.generate_pdf_report(
                developer.id,
                preferences["kpis"]
            )
            
            if not report_result["success"]:
                return report_result
            
            # Get report file path
            report_path = report_result["report_path"]
            
            # Create email subject
            subject = f"PropPulse Analytics Report - {datetime.now().strftime('%B %d, %Y')}"
            
            # Create email body
            body = f"""
            <html>
            <body>
                <h1>PropPulse Analytics Report</h1>
                <p>Hello {developer.legal_name},</p>
                <p>Please find attached your {preferences['frequency']} analytics report.</p>
                <p>This report includes the following KPIs:</p>
                <ul>
                    {self._format_kpi_list(preferences['kpis'])}
                </ul>
                <p>Thank you for using PropPulse!</p>
            </body>
            </html>
            """
            
            # Send email with attachment
            self._send_email_with_attachment(email, subject, body, report_path)
            
            return {
                "success": True,
                "message": "Report sent successfully",
                "report_path": report_path
            }
        except Exception as e:
            print(f"Error in _generate_and_send_report: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_kpi_list(self, kpis: Dict[str, bool]) -> str:
        """
        Format KPI list for email body.
        
        Returns HTML list items for enabled KPIs.
        """
        kpi_names = {
            "views": "Views",
            "saves": "Saves",
            "tokenized": "Tokenized Units",
            "riskGrade": "Risk Grade Mix",
            "timeOnListing": "Average Time on Listing",
            "conversion": "Inquiry-to-Lead Conversion",
            "tokensTraded": "Tokens Traded (Secondary Liquidity)"
        }
        
        list_items = ""
        for kpi, enabled in kpis.items():
            if enabled and kpi in kpi_names:
                list_items += f"<li>{kpi_names[kpi]}</li>"
        
        return list_items
    
    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """
        Send an email.
        
        Raises an exception if sending fails.
        """
        # Create message
        msg = MIMEMultipart()
        msg["From"] = email_username
        msg["To"] = to_email
        msg["Subject"] = subject
        
        # Attach body
        msg.attach(MIMEText(body, "html"))
        
        # Send email
        with smtplib.SMTP(email_server, email_port) as server:
            server.starttls()
            server.login(email_username, email_password)
            server.send_message(msg)
    
    def _send_email_with_attachment(
        self, 
        to_email: str, 
        subject: str, 
        body: str, 
        attachment_path: str
    ) -> None:
        """
        Send an email with an attachment.
        
        Raises an exception if sending fails.
        """
        # Create message
        msg = MIMEMultipart()
        msg["From"] = email_username
        msg["To"] = to_email
        msg["Subject"] = subject
        
        # Attach body
        msg.attach(MIMEText(body, "html"))
        
        # Attach file
        with open(attachment_path, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="pdf")
            attachment.add_header(
                "Content-Disposition", 
                f"attachment; filename={os.path.basename(attachment_path)}"
            )
            msg.attach(attachment)
        
        # Send email
        with smtplib.SMTP(email_server, email_port) as server:
            server.starttls()
            server.login(email_username, email_password)
            server.send_message(msg)

class GDPRService:
    """Service for GDPR compliance features."""
    
    def __init__(self, db: Session = None):
        """Initialize the service."""
        self.db = db
    
    async def request_data_purge(
        self, 
        developer_id: str, 
        verification_code: str,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Request a GDPR data purge for a developer.
        
        Returns a dictionary with request status.
        """
        try:
            # Get developer
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Verify code (in a real implementation, this would be a secure verification process)
            # For this example, we'll use a simple check
            if verification_code != f"PURGE-{developer_id[:8]}":
                return {"success": False, "error": "Invalid verification code"}
            
            # Create purge request
            from ...db.models.gdpr import DataPurgeRequest
            
            purge_request = DataPurgeRequest(
                id=str(uuid.uuid4()),
                developer_id=developer_id,
                status="pending",
                requested_at=datetime.utcnow(),
                scheduled_completion=datetime.utcnow() + timedelta(hours=24)
            )
            
            self.db.add(purge_request)
            self.db.commit()
            
            # Process purge in background if background_tasks is provided
            if background_tasks:
                background_tasks.add_task(
                    self._process_data_purge,
                    purge_request.id
                )
                
                return {
                    "success": True,
                    "status": "processing",
                    "message": "Data purge request submitted and will be processed within 24 hours",
                    "request_id": purge_request.id,
                    "scheduled_completion": purge_request.scheduled_completion.isoformat()
                }
            else:
                # For this example, we'll just return success
                # In a real implementation, this would be a background job
                return {
                    "success": True,
                    "status": "scheduled",
                    "message": "Data purge request submitted and will be processed within 24 hours",
                    "request_id": purge_request.id,
                    "scheduled_completion": purge_request.scheduled_completion.isoformat()
                }
        except Exception as e:
            print(f"Error requesting data purge: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_data_purge(self, request_id: str) -> None:
        """
        Process a data purge request.
        
        This is a background job that purges developer data.
        """
        try:
            # Get purge request
            from ...db.models.gdpr import DataPurgeRequest
            purge_request = self.db.query(DataPurgeRequest).filter_by(id=request_id).first()
            
            if not purge_request:
                print(f"Purge request not found: {request_id}")
                return
            
            # Update status
            purge_request.status = "processing"
            self.db.commit()
            
            # Get developer
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=purge_request.developer_id).first()
            
            if not developer:
                print(f"Developer not found: {purge_request.developer_id}")
                purge_request.status = "failed"
                purge_request.completion_notes = "Developer not found"
                self.db.commit()
                return
            
            # Purge developer data
            # This would be a complex process in a real implementation
            # For this example, we'll just simulate the process
            
            # 1. Anonymize developer profile
            developer.legal_name = f"REDACTED-{developer.id[:8]}"
            developer.primary_contact_email = f"redacted-{developer.id[:8]}@example.com"
            developer.primary_contact_whatsapp = "REDACTED"
            developer.support_phone = "REDACTED"
            developer.vat_reg_number = "REDACTED"
            developer.trade_license = "REDACTED"
            
            # 2. Delete marketing assets
            from ...db.models.marketing import MarketingAsset
            marketing_assets = self.db.query(MarketingAsset).filter_by(
                developer_id=developer.id
            ).all()
            
            for asset in marketing_assets:
                self.db.delete(asset)
            
            # 3. Delete email preferences
            from ...db.models.email_preferences import EmailPreferences
            email_preferences = self.db.query(EmailPreferences).filter_by(
                developer_id=developer.id
            ).first()
            
            if email_preferences:
                self.db.delete(email_preferences)
            
            # 4. Mark properties as anonymized
            from ...db.models.property import Property
            properties = self.db.query(Property).filter_by(
                developer_id=developer.id
            ).all()
            
            for prop in properties:
                prop.developer_id = "REDACTED"
            
            # 5. Update purge request status
            purge_request.status = "completed"
            purge_request.completed_at = datetime.utcnow()
            purge_request.completion_notes = "Data purge completed successfully"
            
            # Commit changes
            self.db.commit()
            
            print(f"Data purge completed for developer {developer.id}")
        except Exception as e:
            print(f"Error processing data purge: {e}")
            
            # Update purge request status
            try:
                from ...db.models.gdpr import DataPurgeRequest
                purge_request = self.db.query(DataPurgeRequest).filter_by(id=request_id).first()
                
                if purge_request:
                    purge_request.status = "failed"
                    purge_request.completion_notes = f"Error: {str(e)}"
                    self.db.commit()
            except Exception as update_error:
                print(f"Error updating purge request status: {update_error}")
    
    async def get_purge_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get the status of a data purge request.
        
        Returns a dictionary with request status.
        """
        try:
            # Get purge request
            from ...db.models.gdpr import DataPurgeRequest
            purge_request = self.db.query(DataPurgeRequest).filter_by(id=request_id).first()
            
            if not purge_request:
                return {"success": False, "error": "Purge request not found"}
            
            return {
                "success": True,
                "request": {
                    "id": purge_request.id,
                    "developer_id": purge_request.developer_id,
                    "status": purge_request.status,
                    "requested_at": purge_request.requested_at.isoformat(),
                    "scheduled_completion": purge_request.scheduled_completion.isoformat(),
                    "completed_at": purge_request.completed_at.isoformat() if purge_request.completed_at else None,
                    "completion_notes": purge_request.completion_notes
                }
            }
        except Exception as e:
            print(f"Error getting purge request status: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_developer_purge_requests(self, developer_id: str) -> Dict[str, Any]:
        """
        Get all data purge requests for a developer.
        
        Returns a dictionary with request list.
        """
        try:
            # Get purge requests
            from ...db.models.gdpr import DataPurgeRequest
            purge_requests = self.db.query(DataPurgeRequest).filter_by(
                developer_id=developer_id
            ).order_by(DataPurgeRequest.requested_at.desc()).all()
            
            # Format requests
            formatted_requests = []
            for request in purge_requests:
                formatted_requests.append({
                    "id": request.id,
                    "developer_id": request.developer_id,
                    "status": request.status,
                    "requested_at": request.requested_at.isoformat(),
                    "scheduled_completion": request.scheduled_completion.isoformat(),
                    "completed_at": request.completed_at.isoformat() if request.completed_at else None,
                    "completion_notes": request.completion_notes
                })
            
            return {
                "success": True,
                "requests": formatted_requests
            }
        except Exception as e:
            print(f"Error getting developer purge requests: {e}")
            return {"success": False, "error": str(e)}
