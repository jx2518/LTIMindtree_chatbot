"""
Natural Language Understanding Agent for Shipment Tracking

This agent handles:
1. Intent classification (what does the user want?)
2. Entity extraction (PRO numbers, locations, dates, etc.)
3. Context understanding (follow-up questions, corrections)
4. Confidence scoring for decisions
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models.state import ConversationIntent, ConversationContext, ShipmentDetails
from memory.memory_manager import MemoryManager

@dataclass
class ExtractedEntity:
    """Represents an extracted entity from user input"""
    entity_type: str
    value: str
    confidence: float
    start_pos: int
    end_pos: int

class IntentClassificationOutput(BaseModel):
    """Structured output for intent classification"""
    intent: str = Field(description="The classified intent")
    confidence: float = Field(description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Explanation for the classification")
    entities_mentioned: List[str] = Field(description="List of entity types mentioned")

class EntityExtractionOutput(BaseModel):
    """Structured output for entity extraction"""
    pro_numbers: List[str] = Field(default=[], description="Extracted PRO tracking numbers")
    locations: List[str] = Field(default=[], description="Mentioned locations (cities, states, zips)")
    dates: List[str] = Field(default=[], description="Mentioned dates or time references")
    reference_numbers: List[str] = Field(default=[], description="Other reference numbers")
    carriers: List[str] = Field(default=[], description="Mentioned carrier names")
    weights: List[str] = Field(default=[], description="Weight references")
    urgency_indicators: List[str] = Field(default=[], description="Words indicating urgency")

class NLUAgent:
    """Natural Language Understanding Agent for shipment tracking"""
    
    def __init__(self, memory_manager: MemoryManager, model: str = "gpt-4"):
        self.memory_manager = memory_manager
        self.llm = ChatOpenAI(model=model, temperature=0.1)
        
        # Initialize parsers
        self.intent_parser = PydanticOutputParser(pydantic_object=IntentClassificationOutput)
        self.entity_parser = PydanticOutputParser(pydantic_object=EntityExtractionOutput)
        
        # Regex patterns for entity extraction
        self.patterns = {
            'pro_number': [
                r'\b(?:PRO|pro|tracking|track)[\s#:]*([0-9]{7,10})\b',
                r'\b([0-9]{7,10})\b',  # Standalone numbers
                r'\b([A-Z]{2,4}[0-9]{7,10})\b'  # Carrier prefix + numbers
            ],
            'phone_number': r'\b(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            'zip_code': r'\b[0-9]{5}(?:-[0-9]{4})?\b',
            'weight': r'\b([0-9]+(?:\.[0-9]+)?)\s*(?:lbs?|pounds?|kg|kilograms?|tons?)\b',
            'date': r'\b(?:today|tomorrow|yesterday|[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{2,4}|[0-9]{1,2}-[0-9]{1,2}-[0-9]{2,4})\b'
        }
        
        # Urgency keywords
        self.urgency_keywords = [
            'urgent', 'emergency', 'asap', 'immediately', 'critical', 'rush',
            'delayed', 'late', 'missing', 'lost', 'where is', 'still waiting'
        ]
        
        # Location indicators
        self.location_indicators = [
            'from', 'to', 'shipped to', 'going to', 'destination', 'origin',
            'pickup', 'delivery', 'deliver to'
        ]
    
    def classify_intent(self, message: str, conversation_history: List[BaseMessage]) -> IntentClassificationOutput:
        """Classify the user's intent based on their message and conversation history"""
        
        # Get procedural memory for intent classification
        intent_prompt = self.memory_manager.get_procedural_prompt("intent_classification")
        base_prompt = intent_prompt.prompt_text if intent_prompt else "Classify the user's intent."
        
        # Look for similar past episodes to inform classification
        similar_episodes = self.memory_manager.retrieve_similar_episodes(
            message, ConversationIntent.UNKNOWN, limit=3
        )
        
        # Build context from similar episodes
        episode_context = ""
        if similar_episodes:
            episode_context = "\nSimilar past conversations:\n"
            for episode in similar_episodes:
                episode_context += f"- Query: '{episode.user_query}' → Intent: {episode.intent.value}\n"
        
        # Format conversation history
        history_text = ""
        if conversation_history:
            recent_messages = conversation_history[-6:]  # Last 3 exchanges
            for msg in recent_messages:
                role = "User" if msg.type == "human" else "Assistant"
                history_text += f"{role}: {msg.content}\n"
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""
{base_prompt}

Available intents:
- TRACK_SHIPMENT: User wants to track a specific shipment
- SHIPMENT_DELAY: User is asking about a delayed shipment  
- MISSING_SHIPMENT: User believes a shipment is lost or missing
- GENERAL_INQUIRY: General questions about shipping
- PROVIDE_FEEDBACK: User is providing feedback
- UNKNOWN: Intent is unclear

Consider the conversation context and any patterns from similar past interactions.

{episode_context}

{self.intent_parser.get_format_instructions()}
"""),
            HumanMessage(content=f"""
Conversation History:
{history_text}

Current Message: {message}

Classify this intent considering the full context.
""")
        ])
        
        response = self.llm.invoke(prompt.format_messages())
        return self.intent_parser.parse(response.content)
    
    def extract_entities(self, message: str) -> EntityExtractionOutput:
        """Extract entities from the user message"""
        
        # Get procedural memory for entity extraction
        extraction_prompt = self.memory_manager.get_procedural_prompt("pro_extraction")
        base_prompt = extraction_prompt.prompt_text if extraction_prompt else "Extract entities from the message."
        
        # Use both regex and LLM for entity extraction
        regex_entities = self._extract_with_regex(message)
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""
{base_prompt}

Extract specific entities from the user's message. Be precise and only extract entities that are clearly mentioned.

Common patterns:
- PRO numbers: 7-10 digits, may have carrier prefix (FedEx: 1234567890, UPS: 1Z...)
- Locations: Cities, states, ZIP codes
- Dates: Specific dates or relative references (today, yesterday, last week)
- Carriers: FedEx, UPS, YRC, Estes, etc.
- Reference numbers: Any other tracking or reference numbers

{self.entity_parser.get_format_instructions()}
"""),
            HumanMessage(content=f"Message: {message}")
        ])
        
        response = self.llm.invoke(prompt.format_messages())
        llm_entities = self.entity_parser.parse(response.content)
        
        # Combine regex and LLM results
        combined_entities = self._combine_entity_results(regex_entities, llm_entities)
        
        return combined_entities
    
    def _extract_with_regex(self, text: str) -> Dict[str, List[str]]:
        """Extract entities using regex patterns"""
        entities = {
            'pro_numbers': [],
            'phone_numbers': [],
            'zip_codes': [],
            'weights': [],
            'dates': [],
            'urgency_indicators': []
        }
        
        # Extract PRO numbers (but filter out phone numbers)
        phone_matches = re.findall(self.patterns['phone_number'], text, re.IGNORECASE)
        phone_numbers = [match for match in phone_matches]
        
        for pattern in self.patterns['pro_number']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Skip if it's a phone number
                if not any(phone in match for phone in phone_numbers):
                    # Validate PRO number length
                    number_only = re.sub(r'[^0-9]', '', match)
                    if 7 <= len(number_only) <= 12:
                        entities['pro_numbers'].append(match)
        
        # Extract other entities
        entities['phone_numbers'] = phone_numbers
        entities['zip_codes'] = re.findall(self.patterns['zip_code'], text)
        entities['weights'] = re.findall(self.patterns['weight'], text, re.IGNORECASE)
        entities['dates'] = re.findall(self.patterns['date'], text, re.IGNORECASE)
        
        # Check for urgency indicators
        text_lower = text.lower()
        for keyword in self.urgency_keywords:
            if keyword in text_lower:
                entities['urgency_indicators'].append(keyword)
        
        return entities
    
    def _combine_entity_results(self, regex_entities: Dict[str, List[str]], 
                               llm_entities: EntityExtractionOutput) -> EntityExtractionOutput:
        """Combine and deduplicate results from regex and LLM extraction"""
        
        # Start with LLM entities
        combined = EntityExtractionOutput(
            pro_numbers=list(set(llm_entities.pro_numbers + regex_entities.get('pro_numbers', []))),
            locations=llm_entities.locations,
            dates=list(set(llm_entities.dates + regex_entities.get('dates', []))),
            reference_numbers=llm_entities.reference_numbers,
            carriers=llm_entities.carriers,
            weights=list(set(llm_entities.weights + regex_entities.get('weights', []))),
            urgency_indicators=list(set(llm_entities.urgency_indicators + regex_entities.get('urgency_indicators', [])))
        )
        
        return combined
    
    def analyze_context(self, current_message: str, conversation_history: List[BaseMessage], 
                       context: ConversationContext) -> ConversationContext:
        """Analyze and update conversation context"""
        
        # Classify intent
        intent_result = self.classify_intent(current_message, conversation_history)
        
        # Extract entities from current message
        current_entities = self.extract_entities(current_message)
        
        # Accumulate entities from conversation history
        accumulated_entities = self._accumulate_entities_from_history(conversation_history, current_entities)
        
        # Update context
        updated_context = ConversationContext(
            session_id=context.session_id,
            user_id=context.user_id,
            intent=ConversationIntent(intent_result.intent.lower()),
            confidence=intent_result.confidence,
            extracted_entities=accumulated_entities,
            current_shipment=context.current_shipment,
            previous_queries=context.previous_queries + [current_message],
            carrier_contacted=context.carrier_contacted,
            email_sent=context.email_sent,
            escalated=context.escalated,
            conversation_start_time=context.conversation_start_time
        )
        
        # Store relevant facts in semantic memory
        self._store_extracted_facts(current_entities, updated_context)
        
        return updated_context
    
    def _accumulate_entities_from_history(self, conversation_history: List[BaseMessage], 
                                        current_entities: 'EntityExtractionOutput') -> Dict[str, List[str]]:
        """Accumulate entities from conversation history and current message"""
        
        accumulated = {
            'pro_numbers': list(current_entities.pro_numbers),
            'locations': list(current_entities.locations),
            'dates': list(current_entities.dates),
            'carriers': list(current_entities.carriers),
            'weights': list(current_entities.weights),
            'urgency_indicators': list(current_entities.urgency_indicators),
            'reference_numbers': list(current_entities.reference_numbers)
        }
        
        # Extract entities from recent conversation history (last 4 messages to avoid too much noise)
        recent_messages = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
        
        for message in recent_messages:
            if hasattr(message, 'content') and message.type == "human":
                try:
                    historical_entities = self.extract_entities(message.content)
                    
                    # Add non-duplicate entities from history
                    for entity_type, values in {
                        'pro_numbers': historical_entities.pro_numbers,
                        'locations': historical_entities.locations,
                        'dates': historical_entities.dates,
                        'carriers': historical_entities.carriers,
                        'weights': historical_entities.weights,
                        'urgency_indicators': historical_entities.urgency_indicators,
                        'reference_numbers': historical_entities.reference_numbers
                    }.items():
                        for value in values:
                            if value not in accumulated[entity_type]:
                                accumulated[entity_type].append(value)
                
                except Exception:
                    # Skip this message if entity extraction fails
                    continue
        
        return accumulated
    
    def _store_extracted_facts(self, entities: EntityExtractionOutput, context: ConversationContext):
        """Store extracted entities as semantic facts"""
        session_id = context.session_id
        
        # Store PRO numbers
        for pro in entities.pro_numbers:
            self.memory_manager.store_semantic_fact(
                subject=session_id,
                predicate="mentioned_pro_number",
                object_value=pro,
                confidence=0.9,
                source="nlu_extraction"
            )
        
        # Store carrier mentions
        for carrier in entities.carriers:
            self.memory_manager.store_semantic_fact(
                subject=session_id,
                predicate="mentioned_carrier",
                object_value=carrier,
                confidence=0.8,
                source="nlu_extraction"
            )
        
        # Store urgency indicators
        if entities.urgency_indicators:
            urgency_level = "high" if len(entities.urgency_indicators) > 1 else "medium"
            self.memory_manager.store_semantic_fact(
                subject=session_id,
                predicate="urgency_level",
                object_value=urgency_level,
                confidence=0.7,
                source="nlu_extraction"
            )
    
    def should_request_clarification(self, context: ConversationContext) -> Tuple[bool, str]:
        """Determine if we need to ask for clarification"""
        
        # Check if we have enough information for the intent
        if context.intent == ConversationIntent.TRACK_SHIPMENT:
            pro_numbers = context.extracted_entities.get('pro_numbers', [])
            locations = context.extracted_entities.get('locations', [])
            carriers = context.extracted_entities.get('carriers', [])
            
            # We have enough info if we have PRO number OR sufficient alternative details
            if pro_numbers:
                return False, ""  # Have PRO number, no clarification needed
            
            # Check what specific information is missing for alternative search
            missing_info = []
            if len(locations) < 2:  # Need origin and destination
                missing_info.append("origin and destination cities")
            if not carriers:
                missing_info.append("carrier name (FedEx Freight, UPS Freight, YRC Freight)")
            
            if missing_info:
                missing_text = " and ".join(missing_info)
                return True, f"I'd be happy to help you track your shipment. Since you don't have the PRO number, I'll need the {missing_text} to locate your shipment."
        
        elif context.intent == ConversationIntent.SHIPMENT_DELAY:
            pro_numbers = context.extracted_entities.get('pro_numbers', [])
            locations = context.extracted_entities.get('locations', [])
            carriers = context.extracted_entities.get('carriers', [])
            
            if pro_numbers:
                return False, ""  # Have PRO number, no clarification needed
                
            # Check what's missing for delay investigation
            missing_info = []
            if len(locations) < 2:
                missing_info.append("origin and destination cities")
            if not carriers:
                missing_info.append("carrier name")
                
            if missing_info:
                missing_text = " and ".join(missing_info)
                return True, f"I understand you're concerned about a delayed shipment. To investigate this, I'll need the {missing_text} since you don't have the PRO number."
        
        elif context.intent == ConversationIntent.MISSING_SHIPMENT:
            pro_numbers = context.extracted_entities.get('pro_numbers', [])
            locations = context.extracted_entities.get('locations', [])
            carriers = context.extracted_entities.get('carriers', [])
            
            if pro_numbers:
                return False, ""  # Have PRO number, can escalate directly
                
            # For missing shipments, we need more details to escalate properly
            missing_info = []
            if len(locations) < 2:
                missing_info.append("origin and destination cities")
            if not carriers:
                missing_info.append("carrier name")
                
            if missing_info:
                missing_text = " and ".join(missing_info)
                return True, f"I'm sorry to hear about your missing shipment. To escalate this properly with the carrier, I'll need the {missing_text}."
        
        elif context.confidence < 0.7:
            return True, "I want to make sure I understand correctly. Could you please rephrase what you're looking for?"
        
        return False, ""
    
    def get_suggested_actions(self, context: ConversationContext) -> List[str]:
        """Get suggested next actions based on the context"""
        actions = []
        
        # Get success patterns for this intent
        patterns = self.memory_manager.get_success_patterns(context.intent)
        
        if patterns.get("common_actions"):
            # Use the most successful actions for this intent
            actions.extend([action[0] for action in patterns["common_actions"][:3]])
        else:
            # Default actions based on intent
            if context.intent == ConversationIntent.TRACK_SHIPMENT:
                if context.extracted_entities.get('pro_numbers'):
                    actions.append("search_by_pro")
                else:
                    actions.append("request_more_info")
            
            elif context.intent == ConversationIntent.SHIPMENT_DELAY:
                actions.extend(["search_by_pro", "contact_carrier"])
            
            elif context.intent == ConversationIntent.MISSING_SHIPMENT:
                actions.extend(["search_by_details", "escalate"])
        
        return actions 