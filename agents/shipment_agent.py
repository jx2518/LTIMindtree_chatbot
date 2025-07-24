"""
Main Shipment Tracking Agent using LangGraph

This agent orchestrates:
1. Natural language understanding 
2. Memory management (semantic, episodic, procedural)
3. Carrier API integration
4. Email communication
5. Intelligent conversation flow

The agent uses LangGraph to manage complex conversation states and decision-making.
"""

import uuid
import asyncio
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from models.state import (
    ConversationState, ConversationContext, ConversationIntent, 
    ActionType, CustomerInfo, ShipmentDetails, AgentMemory
)
from memory.memory_manager import MemoryManager, EpisodicMemory
from agents.nlu_agent import NLUAgent  
from integrations.carrier_api import CarrierAPIManager
from integrations.email_service import EmailService
from config import Config

class ShipmentTrackingAgent:
    """Main agent for handling shipment tracking conversations"""
    
    def __init__(self, use_mock_apis: bool = True):
        # Initialize core components
        self.memory_manager = MemoryManager()
        self.nlu_agent = NLUAgent(self.memory_manager)
        self.carrier_api_manager = CarrierAPIManager(use_mock=use_mock_apis)
        self.email_service = EmailService(self.carrier_api_manager)
        
        # LLM for conversation generation
        self.llm = ChatOpenAI(
            model=Config.OPENAI_MODEL,
            temperature=0.3
        )
        
        # Initialize LangGraph components
        self.checkpointer = MemorySaver()
        self.store = InMemoryStore()
        
        # Build the conversation graph
        self.graph = self._build_conversation_graph()
    
    def _build_conversation_graph(self) -> StateGraph:
        """Build the LangGraph workflow for conversation handling"""
        
        # Create the graph
        graph = StateGraph(ConversationState)
        
        # Add nodes
        graph.add_node("analyze_input", self._analyze_input_node)
        graph.add_node("search_shipment", self._search_shipment_node)
        graph.add_node("contact_carrier", self._contact_carrier_node)
        graph.add_node("generate_response", self._generate_response_node)
        graph.add_node("update_memory", self._update_memory_node)
        
        # Define the conversation flow
        graph.add_edge(START, "analyze_input")
        
        # Conditional routing from analyze_input
        graph.add_conditional_edges(
            "analyze_input",
            self._route_after_analysis,
            {
                "search": "search_shipment",
                "contact": "contact_carrier", 
                "respond": "generate_response"
            }
        )
        
        # Conditional routing from search_shipment
        graph.add_conditional_edges(
            "search_shipment",
            self._route_after_search,
            {
                "found": "generate_response",
                "multiple_found": "generate_response",
                "not_found": "contact_carrier",
                "need_info": "generate_response"
            }
        )
        
        # From contact_carrier, always go to generate_response
        graph.add_edge("contact_carrier", "generate_response")
        
        # From generate_response, update memory then end
        graph.add_edge("generate_response", "update_memory")
        graph.add_edge("update_memory", END)
        
        # Compile the graph
        return graph.compile(
            checkpointer=self.checkpointer,
            store=self.store
        )
    
    async def _analyze_input_node(self, state: ConversationState) -> ConversationState:
        """Analyze user input and update context"""
        
        current_message = state["messages"][-1].content
        
        # Use NLU agent to analyze the message
        updated_context = self.nlu_agent.analyze_context(
            current_message,
            state["messages"][:-1],  # Previous messages
            state["context"]
        )
        
        # Store extracted facts in semantic memory
        for pro in updated_context.extracted_entities.get('pro_numbers', []):
            self.memory_manager.store_semantic_fact(
                subject=updated_context.session_id,
                predicate="has_pro_number",
                object_value=pro,
                confidence=0.9
            )
        
        # Check if we need clarification
        needs_clarification, clarification_msg = self.nlu_agent.should_request_clarification(updated_context)
        
        if needs_clarification:
            updated_context.next_action = ActionType.REQUEST_MORE_INFO
            state["metadata"]["clarification_message"] = clarification_msg
        else:
            # Get suggested actions from NLU agent
            suggested_actions = self.nlu_agent.get_suggested_actions(updated_context)
            if suggested_actions:
                updated_context.next_action = ActionType(suggested_actions[0])
        
        # Update state
        state["context"] = updated_context
        
        return state
    
    async def _search_shipment_node(self, state: ConversationState) -> ConversationState:
        """Search for shipment using available information"""
        
        context = state["context"]
        pro_numbers = context.extracted_entities.get('pro_numbers', [])
        
        if pro_numbers:
            # Search by PRO number
            pro_number = pro_numbers[0]  # Use first PRO number found
            carriers = context.extracted_entities.get('carriers', [])
            carrier = carriers[0] if carriers else None
            
            # Call carrier API
            api_response = await self.carrier_api_manager.track_shipment(pro_number, carrier)
            state["api_responses"]["tracking"] = api_response.dict()
            
            if api_response.success:
                # Create shipment details from API response
                shipment_data = api_response.data
                state["shipment"] = ShipmentDetails(
                    pro_number=pro_number,
                    carrier=api_response.carrier,
                    origin_city=shipment_data.get("origin", ""),
                    destination_city=shipment_data.get("destination", ""),
                    status=shipment_data.get("status", "unknown"),
                    pickup_date=self._parse_date(shipment_data.get("pickup_date")),
                    estimated_delivery=self._parse_date(shipment_data.get("estimated_delivery")),
                    weight=shipment_data.get("weight"),
                    tracking_events=shipment_data.get("events", [])
                )
                
                state["metadata"]["search_result"] = "found"
            else:
                state["metadata"]["search_result"] = "not_found"
                state["error_messages"].append(api_response.error)
        
        else:
            # Try to search by details if available
            locations = context.extracted_entities.get('locations', [])
            carriers = context.extracted_entities.get('carriers', [])
            
            if locations or carriers:
                # Extract origin/destination from locations
                origin = locations[0] if len(locations) > 0 else None
                destination = locations[1] if len(locations) > 1 else None
                carrier = carriers[0] if carriers else None
                
                api_response = await self.carrier_api_manager.search_by_details(
                    origin=origin,
                    destination=destination,
                    carrier=carrier
                )
                
                state["api_responses"]["search"] = api_response.dict()
                
                if api_response.success and api_response.data.get("shipments"):
                    found_shipments = api_response.data["shipments"]
                    
                    if len(found_shipments) == 1:
                        # Single shipment found - treat as direct match
                        shipment_data = found_shipments[0]
                        state["shipment"] = ShipmentDetails(
                            pro_number=shipment_data.get("pro_number"),
                            carrier=shipment_data.get("carrier"),
                            origin_city=shipment_data.get("origin", ""),
                            destination_city=shipment_data.get("destination", ""),
                            status=shipment_data.get("status", "unknown"),
                            pickup_date=self._parse_date(shipment_data.get("pickup_date")),
                            estimated_delivery=self._parse_date(shipment_data.get("estimated_delivery")),
                            weight=shipment_data.get("weight"),
                            tracking_events=shipment_data.get("events", [])
                        )
                        state["metadata"]["search_result"] = "found"
                    else:
                        # Multiple shipments found
                        state["metadata"]["search_result"] = "multiple_found"
                        state["metadata"]["found_shipments"] = found_shipments
                else:
                    state["metadata"]["search_result"] = "not_found"
            else:
                state["metadata"]["search_result"] = "need_info"
        
        return state
    
    async def _contact_carrier_node(self, state: ConversationState) -> ConversationState:
        """Contact carrier via email when shipment not found"""
        
        context = state["context"]
        
        # Generate unique reference ID
        reference_id = f"WW{int(datetime.now().timestamp())}{uuid.uuid4().hex[:6]}"
        
        # Prepare shipment details for email
        shipment_details = {
            "origin": ", ".join(context.extracted_entities.get('locations', [])[:1]),
            "destination": ", ".join(context.extracted_entities.get('locations', [])[1:2]) if len(context.extracted_entities.get('locations', [])) > 1 else "Unknown",
            "pickup_date": ", ".join(context.extracted_entities.get('dates', [])),
            "weight": ", ".join(context.extracted_entities.get('weights', [])),
            "reference_number": ", ".join(context.extracted_entities.get('reference_numbers', [])),
            "additional_details": f"Customer query: {state['messages'][-1].content}"
        }
        
        # Customer info
        customer_info = {
            "name": state["customer"].contact_name or "Customer",
            "email": state["customer"].email or "customer@example.com"
        }
        
        # Determine carrier to contact
        carriers = context.extracted_entities.get('carriers', [])
        if carriers:
            carrier = carriers[0]
        else:
            # Default to a general carrier if none specified
            carrier = "FedEx"  # Or could be determined by other logic
        
        # Send email to carrier
        if context.intent == ConversationIntent.MISSING_SHIPMENT:
            # Escalation email for missing shipments
            email_response = await self.email_service.send_carrier_escalation(
                carrier=carrier,
                shipment_details=shipment_details,
                customer_info=customer_info,
                issue_description="Customer reports shipment as missing or delayed",
                reference_id=reference_id
            )
        else:
            # Regular PRO request email
            email_response = await self.email_service.send_carrier_pro_request(
                carrier=carrier,
                shipment_details=shipment_details,
                customer_info=customer_info,
                reference_id=reference_id
            )
        
        # Store email response
        state["email_history"].append({
            "timestamp": datetime.now(),
            "type": "carrier_contact",
            "carrier": carrier,
            "reference_id": reference_id,
            "success": email_response.success,
            "message_id": email_response.message_id
        })
        
        # Update context
        context.carrier_contacted = True
        state["context"] = context
        state["metadata"]["email_reference"] = reference_id
        
        return state
    
    async def _generate_response_node(self, state: ConversationState) -> ConversationState:
        """Generate intelligent response based on current state"""
        
        context = state["context"]
        
        # Get procedural memory for response generation
        response_prompt = self.memory_manager.get_procedural_prompt("customer_communication")
        base_instructions = response_prompt.prompt_text if response_prompt else "Be helpful and professional."
        
        # Retrieve relevant semantic facts
        relevant_facts = self.memory_manager.retrieve_semantic_facts(
            query=state["messages"][-1].content,
            limit=3
        )
        facts_context = "\n".join([f"- {fact.subject} {fact.predicate} {fact.object}" for fact in relevant_facts])
        
        # Get similar successful episodes
        similar_episodes = self.memory_manager.retrieve_similar_episodes(
            current_query=state["messages"][-1].content,
            intent=context.intent,
            limit=2
        )
        
        episodes_context = ""
        if similar_episodes:
            episodes_context = "Similar successful resolutions:\n"
            for episode in similar_episodes:
                episodes_context += f"- Query: {episode.user_query} → Actions: {[a.value for a in episode.actions_taken]}\n"
        
        # Build response based on current state
        response_context = self._build_response_context(state)
        
        # Create system prompt
        system_prompt = f"""
{base_instructions}

You are assisting a customer with shipment tracking. Based on the analysis and available information, provide a helpful response.

IMPORTANT: Our system can track shipments using these data fields ONLY:
- PRO numbers (preferred): WE123456789, WE987654321, WE555444333
- Shipper names: IKEA, Home Depot, Best Buy
- Origin/destination cities: Atlanta→Miami, Dallas→Houston, Memphis→Nashville  
- Pickup dates: January 2024 dates
- Carriers: FedEx Freight, YRC Freight, UPS Freight
- Commodity types: Furniture-Sofas, Building Materials, Electronics

DO NOT ask for email addresses, order numbers, or other data not listed above.

Current situation:
- Customer intent: {context.intent.value}
- Confidence: {context.confidence:.2f}
- Urgency indicators: {context.extracted_entities.get('urgency_indicators', [])}

Relevant facts from memory:
{facts_context}

{episodes_context}

{response_context}

Be professional, empathetic, and provide clear next steps using only available data fields.
"""
        
        # Generate response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Customer message: {state['messages'][-1].content}")
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # Add response to conversation
        ai_message = AIMessage(content=response.content)
        state["messages"].append(ai_message)
        
        return state
    
    async def _update_memory_node(self, state: ConversationState) -> ConversationState:
        """Update episodic memory with conversation outcome"""
        
        context = state["context"]
        
        # Determine if this was a successful resolution
        success = self._evaluate_conversation_success(state)
        
        # Calculate actual resolution time
        start_time = context.conversation_start_time
        current_time = datetime.now()
        resolution_time = int((current_time - start_time).total_seconds() / 60)  # Convert to minutes
        
        # Create episodic memory
        episode = EpisodicMemory(
            id=str(uuid.uuid4()),
            session_id=context.session_id,
            user_query=state["messages"][0].content if state["messages"] else "",
            intent=context.intent,
            actions_taken=self._extract_actions_taken(state),
            resolution_successful=success,
            resolution_time_minutes=resolution_time,
            shipment_details=state["shipment"].__dict__ if state["shipment"] else None,
            customer_satisfaction=self._estimate_satisfaction(state),
            lessons_learned=self._extract_lessons_learned(state),
            created_at=datetime.now()
        )
        
        # Store the episode
        self.memory_manager.store_episodic_memory(episode)
        
        return state
    
    def _route_after_analysis(self, state: ConversationState) -> Literal["search", "contact", "respond"]:
        """Route conversation based on analysis results"""
        
        if state["metadata"].get("clarification_message"):
            return "respond"
        
        context = state["context"]
        
        if context.intent in [ConversationIntent.TRACK_SHIPMENT, ConversationIntent.SHIPMENT_DELAY]:
            if context.extracted_entities.get('pro_numbers') or context.extracted_entities.get('locations'):
                return "search"
            else:
                return "respond"  # Need more info
        
        elif context.intent == ConversationIntent.MISSING_SHIPMENT:
            # For missing shipments, try to search first if we have enough details
            pro_numbers = context.extracted_entities.get('pro_numbers', [])
            locations = context.extracted_entities.get('locations', [])
            carriers = context.extracted_entities.get('carriers', [])
            
            if pro_numbers or (locations and carriers):
                return "search"  # Try to find the shipment first
            else:
                return "contact"  # Escalate if insufficient details
        
        else:
            return "respond"
    
    def _route_after_search(self, state: ConversationState) -> Literal["found", "multiple_found", "not_found", "need_info"]:
        """Route conversation based on search results"""
        
        search_result = state["metadata"].get("search_result", "need_info")
        return search_result
    
    def _build_response_context(self, state: ConversationState) -> str:
        """Build context for response generation based on current state"""
        
        context_parts = []
        
        # Search results
        if state["shipment"]:
            shipment = state["shipment"]
            search_method = "PRO number" if state["api_responses"].get("tracking") else "shipment details"
            
            # Special handling for missing shipments that were found
            context = state["context"]
            if context.intent == ConversationIntent.MISSING_SHIPMENT:
                context_parts.append(f"""
GOOD NEWS: Missing shipment found via {search_method}!
- PRO Number: {shipment.pro_number}
- Carrier: {shipment.carrier}
- Current Status: {shipment.status.title() if shipment.status else 'Unknown'}
- Origin: {shipment.origin_city}
- Destination: {shipment.destination_city}
- Pickup Date: {shipment.pickup_date.strftime('%B %d, %Y') if shipment.pickup_date else 'N/A'}
- Estimated Delivery: {shipment.estimated_delivery.strftime('%B %d, %Y') if shipment.estimated_delivery else 'N/A'}
- Weight: {shipment.weight} lbs

IMPORTANT: Reassure the customer that their shipment was located and provide complete tracking details. Do not escalate since shipment was found.
""")
            else:
                context_parts.append(f"""
Shipment found (via {search_method}):
- PRO Number: {shipment.pro_number}
- Carrier: {shipment.carrier}
- Status: {shipment.status.title() if shipment.status else 'Unknown'}
- Origin: {shipment.origin_city}
- Destination: {shipment.destination_city}
- Pickup Date: {shipment.pickup_date.strftime('%B %d, %Y') if shipment.pickup_date else 'N/A'}
- Estimated Delivery: {shipment.estimated_delivery.strftime('%B %d, %Y') if shipment.estimated_delivery else 'N/A'}
- Weight: {shipment.weight} lbs

IMPORTANT: Provide the complete tracking information immediately to the customer. Do not ask them to wait.
""")
        
        # API errors
        if state["error_messages"]:
            context_parts.append(f"API Issues: {'; '.join(state['error_messages'])}")
        
        # Email sent
        if state["email_history"]:
            last_email = state["email_history"][-1]
            if last_email["success"]:
                context_parts.append(f"Email sent to {last_email['carrier']} - Reference: {last_email.get('reference_id', 'N/A')}")
            else:
                context_parts.append("Email sending failed")
        
        # Multiple shipments found
        if state["metadata"].get("found_shipments"):
            found_shipments = state["metadata"]["found_shipments"]
            count = len(found_shipments)
            context_parts.append(f"""
Found {count} matching shipments:
""")
            for i, ship in enumerate(found_shipments[:3], 1):  # Show first 3
                context_parts.append(f"""
{i}. PRO: {ship.get('pro_number', 'N/A')} - {ship.get('carrier', 'N/A')} - {ship.get('status', 'unknown').title()}
   Route: {ship.get('origin', 'N/A')} → {ship.get('destination', 'N/A')}
   Pickup: {ship.get('pickup_date', 'N/A')}
""")
            context_parts.append("IMPORTANT: Present all matching shipments to the customer and ask them to identify which one is theirs.")
        
        # Clarification needed
        if state["metadata"].get("clarification_message"):
            context_parts.append(f"Need clarification: {state['metadata']['clarification_message']}")
        
        return "\n".join(context_parts)
    
    def _evaluate_conversation_success(self, state: ConversationState) -> bool:
        """Evaluate if the conversation was successful"""
        
        # Consider successful if:
        # 1. Shipment was found
        # 2. Carrier was contacted successfully
        # 3. Customer inquiry was addressed
        
        if state["shipment"]:
            return True
        
        if state["email_history"] and state["email_history"][-1]["success"]:
            return True
        
        # Check if customer's question was adequately addressed
        context = state["context"]
        if context.intent == ConversationIntent.GENERAL_INQUIRY:
            return True
        
        return False
    
    def _extract_actions_taken(self, state: ConversationState) -> List[ActionType]:
        """Extract actions that were taken during the conversation"""
        
        actions = []
        
        if state["api_responses"].get("tracking") or state["api_responses"].get("search"):
            actions.append(ActionType.SEARCH_BY_PRO if state["api_responses"].get("tracking") else ActionType.SEARCH_BY_DETAILS)
        
        if state["email_history"]:
            actions.append(ActionType.CONTACT_CARRIER)
        
        if state["shipment"]:
            actions.append(ActionType.PROVIDE_STATUS)
        
        if state["metadata"].get("clarification_message"):
            actions.append(ActionType.REQUEST_MORE_INFO)
        
        return actions
    
    def _estimate_satisfaction(self, state: ConversationState) -> Optional[int]:
        """Estimate customer satisfaction (1-5 scale)"""
        
        # Simple heuristic - in a real system this might use sentiment analysis
        if state["shipment"]:
            return 5  # Found shipment
        elif state["email_history"] and state["email_history"][-1]["success"]:
            return 4  # Contacted carrier
        elif state["metadata"].get("clarification_message"):
            return 3  # Asked for clarification
        else:
            return 2  # Couldn't help much
    
    def _extract_lessons_learned(self, state: ConversationState) -> str:
        """Extract lessons learned from this conversation"""
        
        lessons = []
        
        context = state["context"]
        
        if context.confidence < 0.7:
            lessons.append("Low confidence in intent classification - may need better NLU training")
        
        if not context.extracted_entities.get('pro_numbers') and context.intent == ConversationIntent.TRACK_SHIPMENT:
            lessons.append("Customer wanted to track but didn't provide PRO number - need to ask more clearly")
        
        if state["error_messages"]:
            lessons.append(f"API errors encountered: {'; '.join(state['error_messages'])}")
        
        if state["email_history"] and not state["email_history"][-1]["success"]:
            lessons.append("Email sending failed - check SMTP configuration")
        
        return "; ".join(lessons) if lessons else "Standard successful interaction"
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None
        
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except:
            pass
        
        return None
    
    async def process_message(self, message: str, session_id: str, user_id: str = None) -> str:
        """Process a user message and return the agent's response"""
        
        config = {"configurable": {"thread_id": session_id}}
        
        # Try to get existing conversation state
        try:
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint and hasattr(checkpoint, 'values') and checkpoint.values:
                # Continue existing conversation
                existing_state = dict(checkpoint.values)  # Create a copy
                # Add new message to existing conversation
                if "messages" not in existing_state:
                    existing_state["messages"] = []
                existing_state["messages"].append(HumanMessage(content=message))
                # Reset metadata for new processing
                existing_state["metadata"] = {}
                initial_state = existing_state
            else:
                # Start new conversation
                initial_state = self._create_new_conversation_state(message, session_id, user_id)
        except Exception:
            # Fallback to new conversation if checkpoint retrieval fails
            initial_state = self._create_new_conversation_state(message, session_id, user_id)
        
        # Run the conversation graph
        final_state = await self.graph.ainvoke(initial_state, config)
        
        # Return the last AI message
        ai_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
        return ai_messages[-1].content if ai_messages else "I apologize, but I'm having trouble processing your request right now."
    
    def _create_new_conversation_state(self, message: str, session_id: str, user_id: str = None) -> ConversationState:
        """Create a new conversation state for the first message"""
        return ConversationState(
            messages=[HumanMessage(content=message)],
            context=ConversationContext(
                session_id=session_id,
                user_id=user_id
            ),
            customer=CustomerInfo(
                customer_id=user_id,
                contact_name="Customer"
            ),
            shipment=None,
            memory=AgentMemory(),
            next_action=None,
            api_responses={},
            email_history=[],
            error_messages=[],
            metadata={}
        )
    
    async def get_conversation_history(self, session_id: str) -> List[BaseMessage]:
        """Get conversation history for a session"""
        
        config = {"configurable": {"thread_id": session_id}}
        
        try:
            # Get state from checkpointer
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint and hasattr(checkpoint, 'values') and checkpoint.values:
                # checkpoint.values should be the ConversationState dict
                state_dict = checkpoint.values
                return state_dict.get("messages", [])
        except Exception:
            pass
        
        return []
    
    async def close(self):
        """Close all connections and clean up resources"""
        await self.carrier_api_manager.close() 