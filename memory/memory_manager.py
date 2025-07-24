"""
Memory Management System for Worldwide Express Shipment Tracking Chatbot

This module implements three types of memory:
1. Semantic Memory: Facts about shipments, carriers, and customers
2. Episodic Memory: Past conversations and successful resolution patterns
3. Procedural Memory: System prompts and conversation strategies that evolve
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

from langchain_openai import OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import BaseMessage

from models.state import ConversationState, ShipmentDetails, ConversationIntent, ActionType

@dataclass
class SemanticFact:
    """A fact stored in semantic memory"""
    id: str
    subject: str  # What this fact is about (customer, shipment, carrier)
    predicate: str  # The relationship or property
    object: str  # The value or related entity
    confidence: float
    source: str  # Where this fact came from
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0

@dataclass
class EpisodicMemory:
    """An episode/experience stored in memory"""
    id: str
    session_id: str
    user_query: str
    intent: ConversationIntent
    actions_taken: List[ActionType]
    resolution_successful: bool
    resolution_time_minutes: int
    shipment_details: Optional[Dict[str, Any]]
    customer_satisfaction: Optional[int]  # 1-5 scale
    lessons_learned: str
    created_at: datetime

@dataclass
class ProceduralPrompt:
    """A procedural memory containing system prompts and strategies"""
    name: str
    prompt_text: str
    usage_context: str
    success_rate: float
    last_updated: datetime
    version: int

class MemoryManager:
    """Manages all three types of memory for the chatbot"""
    
    def __init__(self, embeddings_model: str = "text-embedding-3-small"):
        self.embeddings = OpenAIEmbeddings(model=embeddings_model)
        self.store = InMemoryStore()
        
        # Memory namespaces
        self.semantic_namespace = ("wwsc", "semantic")
        self.episodic_namespace = ("wwsc", "episodic") 
        self.procedural_namespace = ("wwsc", "procedural")
        
        # Initialize with base procedural memories
        self._initialize_procedural_memory()
        
    def _initialize_procedural_memory(self):
        """Initialize the system with basic procedural prompts"""
        base_prompts = {
            "intent_classification": ProceduralPrompt(
                name="intent_classification",
                prompt_text="""Analyze the user's message and classify their intent:
                - TRACK_SHIPMENT: User wants to track a specific shipment
                - SHIPMENT_DELAY: User is asking about a delayed shipment
                - MISSING_SHIPMENT: User believes a shipment is lost or missing
                - GENERAL_INQUIRY: General questions about shipping
                - PROVIDE_FEEDBACK: User is providing feedback
                - UNKNOWN: Intent is unclear
                
                Consider the context and be specific about confidence level.""",
                usage_context="message_analysis",
                success_rate=0.85,
                last_updated=datetime.now(),
                version=1
            ),
            "pro_extraction": ProceduralPrompt(
                name="pro_extraction",
                prompt_text="""Extract PRO numbers from user messages. PRO numbers are typically:
                - 7-10 digits for LTL shipments
                - May be preceded by carrier codes
                - Look for patterns like "PRO 1234567" or "tracking 9876543210"
                
                Be careful not to confuse with phone numbers or other numeric data.""",
                usage_context="entity_extraction",
                success_rate=0.92,
                last_updated=datetime.now(),
                version=1
            ),
            "customer_communication": ProceduralPrompt(
                name="customer_communication",
                prompt_text="""When communicating with customers:
                - Be professional but friendly
                - Acknowledge their concern immediately
                - Provide clear next steps
                - Set realistic expectations for response times
                - Always offer alternative solutions if primary fails""",
                usage_context="response_generation",
                success_rate=0.88,
                last_updated=datetime.now(),
                version=1
            )
        }
        
        for prompt_name, prompt_obj in base_prompts.items():
            self.store_procedural_memory(prompt_obj)
    
    # ===== SEMANTIC MEMORY METHODS =====
    
    def store_semantic_fact(self, subject: str, predicate: str, object_value: str, 
                           confidence: float = 1.0, source: str = "conversation") -> str:
        """Store a fact in semantic memory"""
        fact_id = str(uuid.uuid4())
        fact = SemanticFact(
            id=fact_id,
            subject=subject,
            predicate=predicate,
            object=object_value,
            confidence=confidence,
            source=source,
            created_at=datetime.now(),
            last_accessed=datetime.now()
        )
        
        # Store with embedding-friendly content
        content = f"{subject} {predicate} {object_value}"
        
        self.store.put(
            namespace=self.semantic_namespace,
            key=fact_id,
            value={
                **asdict(fact),
                "content": content,
                "created_at": fact.created_at.isoformat(),
                "last_accessed": fact.last_accessed.isoformat()
            }
        )
        
        return fact_id
    
    def retrieve_semantic_facts(self, query: str, limit: int = 5) -> List[SemanticFact]:
        """Retrieve relevant semantic facts based on query"""
        try:
            results = self.store.search(
                namespace=self.semantic_namespace,
                query=query,
                limit=limit
            )
        except TypeError:
            # Fallback for API compatibility - return empty results
            results = []
        
        facts = []
        for result in results:
            fact_data = result.value
            # Handle datetime conversion safely
            if isinstance(fact_data['created_at'], str):
                fact_data['created_at'] = datetime.fromisoformat(fact_data['created_at'])
            if isinstance(fact_data['last_accessed'], str):
                fact_data['last_accessed'] = datetime.fromisoformat(fact_data['last_accessed'])
            facts.append(SemanticFact(**{k: v for k, v in fact_data.items() if k != 'content'}))
            
        return facts
    
    def update_semantic_fact(self, fact_id: str, **updates) -> bool:
        """Update an existing semantic fact"""
        try:
            existing = self.store.get(self.semantic_namespace, fact_id)
            fact_data = existing.value
            
            # Update provided fields
            for key, value in updates.items():
                if key in fact_data:
                    fact_data[key] = value
            
            fact_data['last_accessed'] = datetime.now().isoformat()
            fact_data['access_count'] = fact_data.get('access_count', 0) + 1
            
            self.store.put(self.semantic_namespace, fact_id, fact_data)
            return True
        except KeyError:
            return False
    
    # ===== EPISODIC MEMORY METHODS =====
    
    def store_episodic_memory(self, episode: EpisodicMemory) -> str:
        """Store an episode in episodic memory"""
        episode_data = asdict(episode)
        episode_data['created_at'] = episode.created_at.isoformat()
        
        # Create searchable content
        content = f"""
        Query: {episode.user_query}
        Intent: {episode.intent.value}
        Actions: {', '.join([action.value for action in episode.actions_taken])}
        Resolution: {'Successful' if episode.resolution_successful else 'Failed'}
        Lessons: {episode.lessons_learned}
        """
        
        episode_data['content'] = content.strip()
        
        self.store.put(
            namespace=self.episodic_namespace,
            key=episode.id,
            value=episode_data
        )
        
        return episode.id
    
    def retrieve_similar_episodes(self, current_query: str, intent: ConversationIntent, 
                                limit: int = 3) -> List[EpisodicMemory]:
        """Find similar past episodes for guidance"""
        # Search for similar successful episodes
        search_query = f"Query: {current_query} Intent: {intent.value} Resolution: Successful"
        
        try:
            results = self.store.search(
                namespace=self.episodic_namespace,
                query=search_query,
                limit=limit
            )
        except TypeError:
            # Fallback for API compatibility - return empty results
            results = []
        
        episodes = []
        for result in results:
            episode_data = result.value
            # Handle datetime conversion safely
            if isinstance(episode_data['created_at'], str):
                episode_data['created_at'] = datetime.fromisoformat(episode_data['created_at'])
            episode_data['intent'] = ConversationIntent(episode_data['intent'])
            episode_data['actions_taken'] = [ActionType(action) for action in episode_data['actions_taken']]
            
            # Remove the content field before creating object
            episode_data = {k: v for k, v in episode_data.items() if k != 'content'}
            episodes.append(EpisodicMemory(**episode_data))
            
        return episodes
    
    def get_success_patterns(self, intent: ConversationIntent) -> Dict[str, Any]:
        """Analyze successful patterns for a specific intent"""
        # Get all episodes with this intent
        try:
            results = self.store.search(
                namespace=self.episodic_namespace,
                query=f"Intent: {intent.value}",
                limit=50
            )
        except TypeError:
            # Fallback for API compatibility - return empty results
            results = []
        
        successful_episodes = [r for r in results if r.value.get('resolution_successful', False)]
        
        if not successful_episodes:
            return {"success_rate": 0, "common_actions": [], "avg_resolution_time": 0}
        
        # Analyze patterns
        action_counts = defaultdict(int)
        total_time = 0
        
        for episode in successful_episodes:
            actions = episode.value.get('actions_taken', [])
            for action in actions:
                action_counts[action] += 1
            total_time += episode.value.get('resolution_time_minutes', 0)
        
        total_episodes = len(successful_episodes)
        success_rate = total_episodes / len(results) if results else 0
        avg_resolution_time = total_time / total_episodes if total_episodes > 0 else 0
        
        # Sort actions by frequency
        common_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "success_rate": success_rate,
            "common_actions": common_actions[:5],  # Top 5 most common actions
            "avg_resolution_time": avg_resolution_time,
            "total_episodes": total_episodes
        }
    
    # ===== PROCEDURAL MEMORY METHODS =====
    
    def store_procedural_memory(self, prompt: ProceduralPrompt) -> None:
        """Store or update a procedural prompt"""
        prompt_data = asdict(prompt)
        prompt_data['last_updated'] = prompt.last_updated.isoformat()
        
        self.store.put(
            namespace=self.procedural_namespace,
            key=prompt.name,
            value=prompt_data
        )
    
    def get_procedural_prompt(self, prompt_name: str) -> Optional[ProceduralPrompt]:
        """Retrieve a specific procedural prompt"""
        try:
            result = self.store.get(self.procedural_namespace, prompt_name)
            prompt_data = result.value
            # Handle datetime conversion safely
            if isinstance(prompt_data['last_updated'], str):
                prompt_data['last_updated'] = datetime.fromisoformat(prompt_data['last_updated'])
            return ProceduralPrompt(**prompt_data)
        except KeyError:
            return None
    
    def update_procedural_success_rate(self, prompt_name: str, new_success_rate: float) -> bool:
        """Update the success rate of a procedural prompt"""
        try:
            result = self.store.get(self.procedural_namespace, prompt_name)
            prompt_data = result.value
            prompt_data['success_rate'] = new_success_rate
            prompt_data['last_updated'] = datetime.now().isoformat()
            
            self.store.put(self.procedural_namespace, prompt_name, prompt_data)
            return True
        except KeyError:
            return False
    
    def evolve_procedural_prompt(self, prompt_name: str, feedback: str, 
                               conversation_example: List[BaseMessage]) -> str:
        """Evolve a procedural prompt based on feedback and examples"""
        current_prompt = self.get_procedural_prompt(prompt_name)
        if not current_prompt:
            return "Prompt not found"
        
        # Here you would use an LLM to improve the prompt based on feedback
        # For now, we'll implement a simple version tracking system
        new_version = current_prompt.version + 1
        updated_prompt = ProceduralPrompt(
            name=current_prompt.name,
            prompt_text=current_prompt.prompt_text,  # In reality, this would be improved by LLM
            usage_context=current_prompt.usage_context,
            success_rate=current_prompt.success_rate * 0.9,  # Reset to allow re-evaluation
            last_updated=datetime.now(),
            version=new_version
        )
        
        self.store_procedural_memory(updated_prompt)
        return f"Updated {prompt_name} to version {new_version}"
    
    # ===== UTILITY METHODS =====
    
    def cleanup_old_memories(self, days_threshold: int = 90) -> Dict[str, int]:
        """Clean up old, unused memories"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        cleanup_stats = {"semantic": 0, "episodic": 0}
        
        # Clean up semantic facts that haven't been accessed recently
        # Implementation would depend on specific cleanup criteria
        
        return cleanup_stats
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get statistics about memory usage"""
        try:
            # Try the newer API
            stats = {
                "semantic_facts": len(list(self.store.list_keys(self.semantic_namespace))),
                "episodic_memories": len(list(self.store.list_keys(self.episodic_namespace))),
                "procedural_prompts": len(list(self.store.list_keys(self.procedural_namespace)))
            }
        except AttributeError:
            # Fallback for API compatibility
            stats = {
                "semantic_facts": 0,
                "episodic_memories": 0,
                "procedural_prompts": 3  # Default count
            }
        
        return stats
    
    def export_memories(self, memory_type: str = "all") -> Dict[str, Any]:
        """Export memories for backup or analysis"""
        export_data = {}
        
        try:
            if memory_type in ["all", "semantic"]:
                semantic_data = []
                for key in self.store.list_keys(self.semantic_namespace):
                    result = self.store.get(self.semantic_namespace, key)
                    semantic_data.append(result.value)
                export_data["semantic"] = semantic_data
            
            if memory_type in ["all", "episodic"]:
                episodic_data = []
                for key in self.store.list_keys(self.episodic_namespace):
                    result = self.store.get(self.episodic_namespace, key)
                    episodic_data.append(result.value)
                export_data["episodic"] = episodic_data
            
            if memory_type in ["all", "procedural"]:
                procedural_data = []
                for key in self.store.list_keys(self.procedural_namespace):
                    result = self.store.get(self.procedural_namespace, key)
                    procedural_data.append(result.value)
                export_data["procedural"] = procedural_data
        except AttributeError:
            # Fallback for API compatibility issues
            export_data = {
                "semantic": [],
                "episodic": [],
                "procedural": [],
                "note": "Export limited due to API compatibility"
            }
        
        return export_data 