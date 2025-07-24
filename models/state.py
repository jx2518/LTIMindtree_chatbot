"""
State management models for the shipment tracking chatbot
"""
from typing import Dict, List, Optional, Any, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class ShipmentStatus(str, Enum):
    """Shipment status options"""
    PICKUP_SCHEDULED = "pickup_scheduled"
    IN_TRANSIT = "in_transit" 
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"

class ConversationIntent(str, Enum):
    """Types of conversation intents"""
    TRACK_SHIPMENT = "track_shipment"
    SHIPMENT_DELAY = "shipment_delay"
    MISSING_SHIPMENT = "missing_shipment"
    GENERAL_INQUIRY = "general_inquiry"
    PROVIDE_FEEDBACK = "provide_feedback"
    UNKNOWN = "unknown"

class ActionType(str, Enum):
    """Types of actions the agent can take"""
    SEARCH_BY_PRO = "search_by_pro"
    SEARCH_BY_DETAILS = "search_by_details"
    CONTACT_CARRIER = "contact_carrier"
    SEND_EMAIL = "send_email"
    REQUEST_MORE_INFO = "request_more_info"
    PROVIDE_STATUS = "provide_status"
    ESCALATE = "escalate"

class ShipmentDetails(BaseModel):
    """Detailed shipment information"""
    pro_number: Optional[str] = None
    carrier: Optional[str] = None
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    origin_zip: Optional[str] = None
    destination_city: Optional[str] = None
    destination_state: Optional[str] = None
    destination_zip: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None
    service_type: Optional[str] = None
    reference_number: Optional[str] = None
    pickup_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None
    status: ShipmentStatus = ShipmentStatus.UNKNOWN
    last_update: Optional[datetime] = None
    tracking_events: List[Dict[str, Any]] = Field(default_factory=list)
    
class CustomerInfo(BaseModel):
    """Customer information"""
    customer_id: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)

class ConversationContext(BaseModel):
    """Context information for the current conversation"""
    session_id: str
    user_id: Optional[str] = None
    intent: ConversationIntent = ConversationIntent.UNKNOWN
    confidence: float = 0.0
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    current_shipment: Optional[ShipmentDetails] = None
    previous_queries: List[str] = Field(default_factory=list)
    carrier_contacted: bool = False
    email_sent: bool = False
    escalated: bool = False
    next_action: Optional[ActionType] = None
    conversation_start_time: datetime = Field(default_factory=datetime.now)

class AgentMemory(BaseModel):
    """Agent memory structure"""
    semantic_memory: Dict[str, Any] = Field(default_factory=dict)  # Facts and knowledge
    episodic_memory: List[Dict[str, Any]] = Field(default_factory=list)  # Past interactions
    procedural_memory: Dict[str, str] = Field(default_factory=dict)  # System prompts and procedures

# Main state for LangGraph
class ConversationState(TypedDict):
    """Main state type for the LangGraph conversation flow"""
    messages: Annotated[List[BaseMessage], add_messages]
    context: ConversationContext
    customer: CustomerInfo
    shipment: Optional[ShipmentDetails]
    memory: AgentMemory
    next_action: Optional[ActionType]
    api_responses: Dict[str, Any]
    email_history: List[Dict[str, Any]]
    error_messages: List[str]
    metadata: Dict[str, Any]

class APIResponse(BaseModel):
    """Standardized API response format"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    carrier: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class EmailTemplate(BaseModel):
    """Email template for carrier communication"""
    template_name: str
    subject: str
    body: str
    variables: List[str] = Field(default_factory=list)

class CarrierAPIConfig(BaseModel):
    """Configuration for carrier API integration"""
    name: str
    base_url: str
    api_key: str
    endpoints: Dict[str, str]
    timeout: int = 30
    retry_attempts: int = 3
    
class UserPreferences(BaseModel):
    """User preferences for personalization"""
    preferred_communication: str = "email"  # email, sms, both
    notification_frequency: str = "updates_only"  # all, updates_only, delivered_only
    preferred_carriers: List[str] = Field(default_factory=list)
    language: str = "en"
    timezone: str = "UTC" 