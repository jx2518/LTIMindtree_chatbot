"""
Sample data for testing and demonstration of the shipment tracking chatbot

This includes sample PRO numbers, shipment details, and carrier responses
that would typically come from real carrier APIs.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from models.state import ShipmentDetails, ShipmentStatus

# Sample PRO numbers and their corresponding shipment details
SAMPLE_SHIPMENTS = {
    "WE123456789": {
        "pro_number": "WE123456789",
        "shipper": "IKEA",
        "consignee": "IKEA Store Miami",
        "origin": "Atlanta, GA",
        "destination": "Miami, FL", 
        "pickup_date": "2024-01-15",
        "delivery_date": "2024-01-18",
        "status": ShipmentStatus.IN_TRANSIT,
        "carrier": "FedEx Freight",
        "weight": 500,
        "pieces": 5,
        "commodity": "Furniture - Sofas",
        "service_type": "LTL",
        "tracking_events": [
            {
                "timestamp": "2024-01-15T08:00:00Z",
                "location": "Atlanta, GA",
                "event": "Pickup completed",
                "status": "PICKED_UP"
            },
            {
                "timestamp": "2024-01-15T14:30:00Z", 
                "location": "Atlanta, GA Terminal",
                "event": "Arrived at terminal",
                "status": "IN_TRANSIT"
            },
            {
                "timestamp": "2024-01-16T06:00:00Z",
                "location": "Jacksonville, FL Terminal", 
                "event": "Departed origin terminal",
                "status": "IN_TRANSIT"
            },
            {
                "timestamp": "2024-01-17T10:15:00Z",
                "location": "Miami, FL Terminal",
                "event": "Arrived at destination terminal",
                "status": "OUT_FOR_DELIVERY"
            }
        ]
    },
    
    "WE987654321": {
        "pro_number": "WE987654321",
        "shipper": "Home Depot",
        "consignee": "Construction Site",
        "origin": "Dallas, TX",
        "destination": "Houston, TX",
        "pickup_date": "2024-01-10", 
        "delivery_date": "2024-01-12",
        "status": ShipmentStatus.DELAYED,
        "carrier": "YRC Freight",
        "weight": 1200,
        "pieces": 15,
        "commodity": "Building Materials",
        "service_type": "LTL",
        "delay_reason": "Weather conditions",
        "tracking_events": [
            {
                "timestamp": "2024-01-10T09:00:00Z",
                "location": "Dallas, TX",
                "event": "Pickup completed",
                "status": "PICKED_UP"
            },
            {
                "timestamp": "2024-01-11T16:45:00Z",
                "location": "Dallas, TX Terminal",
                "event": "Delayed due to weather",
                "status": "DELAYED"
            }
        ]
    },
    
    "WE555444333": {
        "pro_number": "WE555444333",
        "shipper": "Best Buy",
        "consignee": "Customer Residence",
        "origin": "Memphis, TN",
        "destination": "Nashville, TN",
        "pickup_date": "2024-01-14",
        "delivery_date": "2024-01-15",
        "status": ShipmentStatus.DELIVERED,
        "carrier": "UPS Freight",
        "weight": 85,
        "pieces": 3,
        "commodity": "Electronics",
        "service_type": "LTL",
        "tracking_events": [
            {
                "timestamp": "2024-01-14T11:00:00Z",
                "location": "Memphis, TN",
                "event": "Pickup completed",
                "status": "PICKED_UP"
            },
            {
                "timestamp": "2024-01-15T09:30:00Z",
                "location": "Nashville, TN",
                "event": "Delivered",
                "status": "DELIVERED"
            }
        ]
    }
}

# Sample customer conversation patterns for memory learning
SAMPLE_CONVERSATIONS = [
    {
        "customer_id": "IKEA_001",
        "conversation_history": [
            "I need to track PRO WE123456789",
            "When will it be delivered?",
            "Can you send me email updates?"
        ],
        "preferences": {
            "communication_method": "email",
            "notification_frequency": "daily",
            "preferred_language": "english"
        },
        "resolution": "successful_tracking"
    },
    {
        "customer_id": "HD_002", 
        "conversation_history": [
            "My shipment is late",
            "PRO number is WE987654321",
            "This is urgent for our construction project"
        ],
        "preferences": {
            "communication_method": "phone",
            "priority": "high",
            "business_hours": "6am-6pm"
        },
        "resolution": "escalated_to_carrier"
    }
]

# Sample carrier contact information
CARRIER_CONTACTS = {
    "FedEx Freight": {
        "api_endpoint": "https://api.fedex.com/freight/v1",
        "contact_email": "freight-support@fedex.com",
        "phone": "1-800-463-3339",
        "business_hours": "24/7"
    },
    "UPS Freight": {
        "api_endpoint": "https://api.ups.com/freight/v1", 
        "contact_email": "freight@ups.com",
        "phone": "1-800-333-7400",
        "business_hours": "24/7"
    },
    "YRC Freight": {
        "api_endpoint": "https://api.yrc.com/v1",
        "contact_email": "customerservice@yrc.com", 
        "phone": "1-800-610-6500",
        "business_hours": "Mon-Fri 7am-7pm EST"
    }
}

# Email templates for different scenarios
EMAIL_TEMPLATES = {
    "pro_not_found": {
        "subject": "PRO Number Request - {shipper} Shipment",
        "body": """
Dear Carrier Partner,

We are assisting {shipper} with tracking their shipment and need the PRO number for the following shipment:

Shipment Details:
- Origin: {origin}
- Destination: {destination}
- Pickup Date: {pickup_date}
- Weight: {weight} lbs
- Pieces: {pieces}
- Commodity: {commodity}

Please provide the PRO number for this shipment so we can provide tracking updates to our customer.

Thank you for your assistance.

Best regards,
Worldwide Express Customer Service
        """
    },
    
    "delay_notification": {
        "subject": "Shipment Delay Notification - PRO {pro_number}",
        "body": """
Dear {customer_name},

We want to inform you about a delay with your shipment:

PRO Number: {pro_number}
Current Status: {status}
Reason for Delay: {delay_reason}
Updated Delivery Estimate: {updated_delivery}

We are actively working with the carrier to resolve this issue and will keep you updated on the progress.

If you have any questions, please don't hesitate to contact us.

Best regards,
Worldwide Express Team
        """
    }
}

def get_sample_shipment(pro_number: str) -> Dict:
    """Get sample shipment data by PRO number"""
    return SAMPLE_SHIPMENTS.get(pro_number)

def get_all_sample_pros() -> List[str]:
    """Get all sample PRO numbers"""
    return list(SAMPLE_SHIPMENTS.keys())

def get_sample_conversations() -> List[Dict]:
    """Get sample conversation data for memory learning"""
    return SAMPLE_CONVERSATIONS

def get_carrier_contacts() -> Dict:
    """Get carrier contact information"""
    return CARRIER_CONTACTS

def get_email_templates() -> Dict:
    """Get email templates"""
    return EMAIL_TEMPLATES 