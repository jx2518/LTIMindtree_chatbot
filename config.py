"""
Configuration settings for the Worldwide Express Shipment Tracking Chatbot
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shipment_tracking.db")
    
    # Email Configuration
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "chatbot@worldwideexpress.com")
    
    # Carrier API Configuration
    PROJECT44_API_KEY = os.getenv("PROJECT44_API_KEY")
    PROJECT44_BASE_URL = "https://api.project44.com"
    FEDEX_API_KEY = os.getenv("FEDEX_API_KEY")
    FEDEX_BASE_URL = "https://apis.fedex.com"
    
    # Application Settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Memory Configuration
    MEMORY_NAMESPACE_PREFIX = "wwsc_shipment_bot"
    MAX_CONVERSATION_HISTORY = 50
    
    # Carrier Timeout Settings
    API_TIMEOUT = 30  # seconds
    EMAIL_TIMEOUT = 10  # seconds

# Carrier configurations
CARRIER_CONFIGS = {
    "fedex": {
        "name": "FedEx",
        "api_endpoint": "/track/v1/trackingnumbers",
        "pro_number_format": r"^\d{12}$",
        "contact_email": "customer.service@fedex.com"
    },
    "ups": {
        "name": "UPS",
        "api_endpoint": "/track/v1/details",
        "pro_number_format": r"^1Z[A-Z0-9]{16}$",
        "contact_email": "customer.service@ups.com"
    },
    "project44": {
        "name": "Project44 Network",
        "api_endpoint": "/api/v4/shipments",
        "pro_number_format": r"^\d{7,10}$",
        "contact_email": "support@project44.com"
    }
}

# Standard responses for different scenarios
STANDARD_RESPONSES = {
    "greeting": "Hello! I'm here to help you track your shipments. You can provide me with a PRO number, or describe your shipment and I'll help you find it.",
    "pro_not_found": "I couldn't find a shipment with that PRO number. Let me help you by contacting the carrier directly.",
    "missing_details": "I need some additional information to help track your shipment. Could you provide details like origin, destination, weight, or any reference numbers?",
    "carrier_contact": "I'm reaching out to the carrier now to get an update on your shipment. You should receive an email with the response.",
    "technical_error": "I'm experiencing some technical difficulties. Let me escalate this to our support team."
}

# Conversation flow configurations
CONVERSATION_FLOWS = {
    "track_with_pro": ["extract_pro", "lookup_shipment", "return_status"],
    "track_without_pro": ["collect_details", "search_shipment", "contact_carrier"],
    "delayed_shipment": ["analyze_delay", "contact_carrier", "provide_update"],
    "missing_shipment": ["verify_details", "escalate_to_carrier", "schedule_follow_up"]
} 