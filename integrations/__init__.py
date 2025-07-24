"""
External integrations for carrier APIs and email services
"""

from .carrier_api import CarrierAPIManager, CarrierType
from .email_service import EmailService

__all__ = [
    "CarrierAPIManager",
    "CarrierType", 
    "EmailService"
] 