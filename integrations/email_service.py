"""
Email Service for Carrier Communication and Customer Notifications

This module handles:
1. Sending emails to carriers when PRO numbers are not found
2. Customer notifications about shipment status
3. Email templates and formatting
4. Email tracking and delivery confirmation
"""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import logging
import random
import json

from config import Config
from models.state import EmailTemplate, ShipmentDetails
from integrations.carrier_api import CarrierAPIManager

@dataclass
class EmailRequest:
    """Email request data structure"""
    to_email: str
    subject: str
    body: str
    carrier: str
    reference_id: str
    priority: str = "normal"  # normal, high, urgent
    template_used: str = ""
    attachments: List[Dict[str, Any]] = None

@dataclass
class EmailResponse:
    """Email response data structure"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EmailTemplateManager:
    """Manages email templates for different scenarios"""
    
    def __init__(self):
        self.templates = {
            "carrier_pro_request": EmailTemplate(
                template_name="carrier_pro_request",
                subject="Shipment Tracking Request - PRO Number Needed",
                body="""Dear {carrier_name} Customer Service,

We are assisting one of our customers with tracking a shipment, but we are unable to locate it using the available information. Could you please help us obtain the PRO number for this shipment?

Shipment Details:
- Origin: {origin}
- Destination: {destination}
- Pickup Date: {pickup_date}
- Weight: {weight}
- Reference Number: {reference_number}
- Customer Reference: {customer_reference}

Additional Information:
{additional_details}

This is for customer: {customer_name} ({customer_email})

Please reply with the PRO number and current status if available. We would appreciate a response within 24 hours to ensure excellent customer service.

Thank you for your assistance.

Best regards,
Worldwide Express Shipment Tracking Team
Email: {from_email}
Phone: 1-800-WWEXPRESS

Reference ID: {reference_id}
""",
                variables=["carrier_name", "origin", "destination", "pickup_date", "weight", "reference_number", "customer_reference", "additional_details", "customer_name", "customer_email", "from_email", "reference_id"]
            ),
            
            "carrier_status_update": EmailTemplate(
                template_name="carrier_status_update",
                subject="Shipment Status Update Request - PRO {pro_number}",
                body="""Dear {carrier_name} Customer Service,

We need an updated status for the following shipment:

PRO Number: {pro_number}
Customer: {customer_name} ({customer_email})

The customer is inquiring about the current status and estimated delivery time. Our last information shows:
- Status: {last_known_status}
- Last Update: {last_update_date}

Could you please provide:
1. Current shipment status
2. Current location
3. Estimated delivery date
4. Any delays or exceptions

We would appreciate a prompt response to ensure excellent customer service.

Thank you for your assistance.

Best regards,
Worldwide Express Shipment Tracking Team
Email: {from_email}

Reference ID: {reference_id}
""",
                variables=["carrier_name", "pro_number", "customer_name", "customer_email", "last_known_status", "last_update_date", "from_email", "reference_id"]
            ),
            
            "customer_notification": EmailTemplate(
                template_name="customer_notification", 
                subject="Shipment Update - {status}",
                body="""Dear {customer_name},

We have an update regarding your shipment inquiry.

{update_message}

If you have any questions or need further assistance, please don't hesitate to contact us.

Best regards,
Worldwide Express Customer Service Team

This is an automated message from the Worldwide Express Shipment Tracking System.
""",
                variables=["customer_name", "status", "update_message"]
            ),
            
            "carrier_escalation": EmailTemplate(
                template_name="carrier_escalation",
                subject="URGENT: Missing Shipment - Immediate Attention Required",
                body="""Dear {carrier_name} Customer Service Manager,

We are escalating a critical shipment inquiry that requires immediate attention.

Shipment Details:
- PRO Number (if available): {pro_number}
- Customer: {customer_name}
- Origin: {origin}
- Destination: {destination}
- Pickup Date: {pickup_date}
- Current Issue: {issue_description}

The customer has reported this shipment as missing/delayed beyond acceptable timeframes. We need:
1. Immediate status update
2. Current location (if in transit)
3. Investigation into any delays or exceptions
4. Expected resolution timeline
5. Direct contact information for follow-up

This matter requires urgent attention to maintain our service level agreements.

Please respond within 4 hours.

Best regards,
Worldwide Express Operations Team
Email: {from_email}
Phone: 1-800-WWEXPRESS (Emergency Line)

Reference ID: {reference_id}
Escalation Level: HIGH
""",
                variables=["carrier_name", "pro_number", "customer_name", "origin", "destination", "pickup_date", "issue_description", "from_email", "reference_id"]
            )
        }
    
    def get_template(self, template_name: str) -> Optional[EmailTemplate]:
        """Get email template by name"""
        return self.templates.get(template_name)
    
    def format_template(self, template_name: str, variables: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Format email template with provided variables"""
        template = self.get_template(template_name)
        if not template:
            return None
        
        try:
            # Provide default values for missing variables
            defaults = {
                "carrier_name": "Customer Service",
                "customer_name": "Valued Customer",
                "customer_email": "N/A",
                "origin": "N/A",
                "destination": "N/A",
                "pickup_date": "N/A",
                "weight": "N/A",
                "reference_number": "N/A",
                "customer_reference": "N/A",
                "additional_details": "N/A",
                "from_email": Config.FROM_EMAIL,
                "reference_id": f"WW{int(datetime.now().timestamp())}",
                "pro_number": "N/A",
                "last_known_status": "Unknown",
                "last_update_date": "N/A",
                "status": "Update",
                "update_message": "We are working on your request.",
                "issue_description": "Shipment status inquiry"
            }
            
            # Merge with provided variables
            merged_vars = {**defaults, **variables}
            
            return {
                "subject": template.subject.format(**merged_vars),
                "body": template.body.format(**merged_vars)
            }
        except KeyError as e:
            logging.error(f"Missing variable in template {template_name}: {e}")
            return None

class EmailService:
    """Main email service for sending and tracking emails"""
    
    def __init__(self, carrier_api_manager: CarrierAPIManager):
        self.template_manager = EmailTemplateManager()
        self.carrier_api_manager = carrier_api_manager
        self.sent_emails = []  # Track sent emails
        
        # SMTP configuration
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.username = Config.EMAIL_USERNAME
        self.password = Config.EMAIL_PASSWORD
        self.from_email = Config.FROM_EMAIL
    
    async def send_carrier_pro_request(self, carrier: str, shipment_details: Dict[str, Any], 
                                     customer_info: Dict[str, Any], reference_id: str) -> EmailResponse:
        """Send email to carrier requesting PRO number"""
        
        # Get carrier contact info
        carrier_contact = await self.carrier_api_manager.get_carrier_contact_info(carrier)
        
        # Prepare template variables
        variables = {
            "carrier_name": carrier_contact["name"],
            "origin": shipment_details.get("origin", "N/A"),
            "destination": shipment_details.get("destination", "N/A"),
            "pickup_date": shipment_details.get("pickup_date", "N/A"),
            "weight": shipment_details.get("weight", "N/A"),
            "reference_number": shipment_details.get("reference_number", "N/A"),
            "customer_reference": shipment_details.get("customer_reference", "N/A"),
            "additional_details": shipment_details.get("additional_details", "N/A"),
            "customer_name": customer_info.get("name", "N/A"),
            "customer_email": customer_info.get("email", "N/A"),
            "reference_id": reference_id
        }
        
        # Format email template
        formatted_email = self.template_manager.format_template("carrier_pro_request", variables)
        if not formatted_email:
            return EmailResponse(success=False, error="Failed to format email template")
        
        # Create email request
        email_request = EmailRequest(
            to_email=carrier_contact["email"],
            subject=formatted_email["subject"],
            body=formatted_email["body"],
            carrier=carrier,
            reference_id=reference_id,
            priority="normal",
            template_used="carrier_pro_request"
        )
        
        # Send email
        return await self._send_email(email_request)
    
    async def send_carrier_status_request(self, carrier: str, pro_number: str,
                                        customer_info: Dict[str, Any], 
                                        last_status: Dict[str, Any], reference_id: str) -> EmailResponse:
        """Send email to carrier requesting status update"""
        
        carrier_contact = await self.carrier_api_manager.get_carrier_contact_info(carrier)
        
        variables = {
            "carrier_name": carrier_contact["name"],
            "pro_number": pro_number,
            "customer_name": customer_info.get("name", "N/A"),
            "customer_email": customer_info.get("email", "N/A"),
            "last_known_status": last_status.get("status", "Unknown"),
            "last_update_date": last_status.get("date", "N/A"),
            "reference_id": reference_id
        }
        
        formatted_email = self.template_manager.format_template("carrier_status_update", variables)
        if not formatted_email:
            return EmailResponse(success=False, error="Failed to format email template")
        
        email_request = EmailRequest(
            to_email=carrier_contact["email"],
            subject=formatted_email["subject"],
            body=formatted_email["body"],
            carrier=carrier,
            reference_id=reference_id,
            priority="high",
            template_used="carrier_status_update"
        )
        
        return await self._send_email(email_request)
    
    async def send_carrier_escalation(self, carrier: str, shipment_details: Dict[str, Any],
                                    customer_info: Dict[str, Any], issue_description: str,
                                    reference_id: str) -> EmailResponse:
        """Send escalation email to carrier for urgent issues"""
        
        carrier_contact = await self.carrier_api_manager.get_carrier_contact_info(carrier)
        
        variables = {
            "carrier_name": carrier_contact["name"],
            "pro_number": shipment_details.get("pro_number", "N/A"),
            "customer_name": customer_info.get("name", "N/A"),
            "origin": shipment_details.get("origin", "N/A"),
            "destination": shipment_details.get("destination", "N/A"),
            "pickup_date": shipment_details.get("pickup_date", "N/A"),
            "issue_description": issue_description,
            "reference_id": reference_id
        }
        
        formatted_email = self.template_manager.format_template("carrier_escalation", variables)
        if not formatted_email:
            return EmailResponse(success=False, error="Failed to format email template")
        
        email_request = EmailRequest(
            to_email=carrier_contact["email"],
            subject=formatted_email["subject"],
            body=formatted_email["body"],
            carrier=carrier,
            reference_id=reference_id,
            priority="urgent",
            template_used="carrier_escalation"
        )
        
        return await self._send_email(email_request)
    
    async def send_customer_notification(self, customer_email: str, customer_name: str,
                                       status: str, update_message: str) -> EmailResponse:
        """Send notification to customer about shipment update"""
        
        variables = {
            "customer_name": customer_name,
            "status": status,
            "update_message": update_message
        }
        
        formatted_email = self.template_manager.format_template("customer_notification", variables)
        if not formatted_email:
            return EmailResponse(success=False, error="Failed to format email template")
        
        email_request = EmailRequest(
            to_email=customer_email,
            subject=formatted_email["subject"],
            body=formatted_email["body"],
            carrier="customer",
            reference_id=f"CUST{int(datetime.now().timestamp())}",
            priority="normal",
            template_used="customer_notification"
        )
        
        return await self._send_email(email_request)
    
    async def _send_email(self, email_request: EmailRequest) -> EmailResponse:
        """Send email using SMTP"""
        
        try:
            # For demonstration, we'll simulate email sending
            # In production, this would use actual SMTP
            await self._simulate_email_send(email_request)
            
            # Log the email
            self.sent_emails.append({
                "timestamp": datetime.now(),
                "to": email_request.to_email,
                "subject": email_request.subject,
                "carrier": email_request.carrier,
                "reference_id": email_request.reference_id,
                "priority": email_request.priority,
                "template": email_request.template_used
            })
            
            return EmailResponse(
                success=True,
                message_id=f"MSG_{email_request.reference_id}_{int(datetime.now().timestamp())}",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return EmailResponse(
                success=False,
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def _simulate_email_send(self, email_request: EmailRequest):
        """Simulate email sending with realistic delay"""
        # Simulate network delay
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # Print email details for demonstration
        print(f"\n📧 EMAIL SENT")
        print(f"To: {email_request.to_email}")
        print(f"Subject: {email_request.subject}")
        print(f"Priority: {email_request.priority}")
        print(f"Reference: {email_request.reference_id}")
        print(f"Template: {email_request.template_used}")
        print("=" * 50)
        print(email_request.body[:200] + "..." if len(email_request.body) > 200 else email_request.body)
        print("=" * 50)
    
    async def _send_smtp_email(self, email_request: EmailRequest) -> str:
        """Send email using actual SMTP (for production use)"""
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = email_request.to_email
        msg['Subject'] = email_request.subject
        
        # Add priority header if urgent
        if email_request.priority == "urgent":
            msg['X-Priority'] = '1'
            msg['X-MSMail-Priority'] = 'High'
        elif email_request.priority == "high":
            msg['X-Priority'] = '2'
        
        # Add body
        msg.attach(MIMEText(email_request.body, 'plain'))
        
        # Add attachments if any
        if email_request.attachments:
            for attachment in email_request.attachments:
                part = MIMEApplication(attachment['data'], Name=attachment['filename'])
                part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
                msg.attach(part)
        
        # Send email
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            text = msg.as_string()
            server.sendmail(self.from_email, email_request.to_email, text)
        
        return f"MSG_{email_request.reference_id}_{int(datetime.now().timestamp())}"
    
    def get_email_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent email history"""
        return self.sent_emails[-limit:] if self.sent_emails else []
    
    def get_emails_by_reference(self, reference_id: str) -> List[Dict[str, Any]]:
        """Get emails by reference ID"""
        return [email for email in self.sent_emails if email["reference_id"] == reference_id]
    
    async def create_pdf_attachment(self, shipment_details: Dict[str, Any], 
                                  reference_id: str) -> Dict[str, Any]:
        """Create PDF attachment with shipment details"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from io import BytesIO
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title = Paragraph("Shipment Details Report", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Reference information
            ref_info = Paragraph(f"Reference ID: {reference_id}", styles['Normal'])
            story.append(ref_info)
            date_info = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
            story.append(date_info)
            story.append(Spacer(1, 12))
            
            # Shipment details table
            if shipment_details:
                data = [['Field', 'Value']]
                for key, value in shipment_details.items():
                    if value:
                        data.append([key.replace('_', ' ').title(), str(value)])
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(table)
            
            # Build PDF
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            return {
                "filename": f"shipment_details_{reference_id}.pdf",
                "data": pdf_data,
                "content_type": "application/pdf"
            }
            
        except ImportError:
            # Fallback to text if reportlab not available
            pdf_content = f"Shipment Details Report\nReference: {reference_id}\n{json.dumps(shipment_details, indent=2)}"
            return {
                "filename": f"shipment_details_{reference_id}.txt",
                "data": pdf_content.encode('utf-8'),
                "content_type": "text/plain"
            } 