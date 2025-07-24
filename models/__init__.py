"""
Data models for the shipment tracking chatbot
"""

from .state import (
    ConversationState,
    ShipmentDetails,
    ShipmentStatus,
    ConversationIntent,
    APIResponse,
    EmailTemplate
)

__all__ = [
    "ConversationState",
    "ShipmentDetails", 
    "ShipmentStatus",
    "ConversationIntent",
    "APIResponse",
    "EmailTemplate"
] 