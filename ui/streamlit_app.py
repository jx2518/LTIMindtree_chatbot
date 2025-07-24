"""
Streamlit UI for the Worldwide Express Shipment Tracking Chatbot

This interface demonstrates the capabilities of the intelligent chatbot including:
- Natural language understanding
- Memory management
- API integration
- Email communication
"""

import streamlit as st
import asyncio
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any

# Import our agent
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.shipment_agent import ShipmentTrackingAgent
from models.state import ConversationIntent

# Configure Streamlit page
st.set_page_config(
    page_title="Worldwide Express Shipment Tracking",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    
    .user-message {
        background-color: #e3f2fd;
        border-left-color: #2196f3;
    }
    
    .assistant-message {
        background-color: #f1f8e9;
        border-left-color: #4caf50;
    }
    
    .memory-box {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .sidebar-section {
        background-color: #fafafa;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def initialize_agent():
    """Initialize the shipment tracking agent"""
    return ShipmentTrackingAgent(use_mock_apis=True)

def display_chat_message(message: str, is_user: bool = True):
    """Display a chat message with proper styling"""
    if is_user:
        st.markdown(f"""
        <div class="chat-message user-message">
            <strong>You:</strong> {message}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message assistant-message">
            <strong>🤖 Agent:</strong> {message}
        </div>
        """, unsafe_allow_html=True)

def display_memory_stats(agent: ShipmentTrackingAgent):
    """Display memory statistics in the sidebar"""
    try:
        stats = agent.memory_manager.get_memory_statistics()
        
        st.sidebar.markdown("### 🧠 Memory Statistics")
        
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            st.metric("Semantic Facts", stats.get("semantic_facts", 0))
        with col2:
            st.metric("Episodes", stats.get("episodic_memories", 0))
        with col3:
            st.metric("Procedures", stats.get("procedural_prompts", 0))
            
    except Exception as e:
        st.sidebar.error(f"Error loading memory stats: {e}")

def display_recent_emails(agent: ShipmentTrackingAgent):
    """Display recent email activity"""
    try:
        recent_emails = agent.email_service.get_email_history(limit=5)
        
        if recent_emails:
            st.sidebar.markdown("### 📧 Recent Email Activity")
            for email in recent_emails[-3:]:  # Show last 3
                timestamp = email["timestamp"].strftime("%H:%M:%S")
                carrier = email["carrier"]
                success = "✅" if email["success"] else "❌"
                st.sidebar.markdown(f"**{timestamp}** - {carrier} {success}")
        
    except Exception as e:
        st.sidebar.error(f"Error loading email history: {e}")

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🚚 Worldwide Express Shipment Tracking</h1>
        <p>Intelligent AI Agent for Customer Service</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "agent" not in st.session_state:
        st.session_state.agent = initialize_agent()
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    
    # Sidebar
    st.sidebar.title("🔧 System Dashboard")
    
    # Agent configuration
    st.sidebar.markdown("### ⚙️ Configuration")
    
    # Session management
    if st.sidebar.button("🔄 New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.rerun()
    
    # Display current session info
    st.sidebar.markdown(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
    
    # Memory and email stats
    display_memory_stats(st.session_state.agent)
    display_recent_emails(st.session_state.agent)
    
    # Sample queries
    st.sidebar.markdown("### 💡 Try These Queries")
    sample_queries = [
        "Track shipment PRO WE123456789",
        "My shipment from Atlanta to Miami is delayed",
        "I can't find my package, it was supposed to arrive yesterday",
        "Where is my IKEA furniture shipment?",
        "Check status of shipment WE987654321"
    ]
    
    for query in sample_queries:
        if st.sidebar.button(f"📝 {query[:30]}...", key=f"sample_{query[:10]}"):
            st.session_state.messages.append({"role": "user", "content": query})
            st.rerun()
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### 💬 Chat with the Agent")
        
        # Display conversation history
        for message in st.session_state.messages:
            if message["role"] == "user":
                display_chat_message(message["content"], is_user=True)
            else:
                display_chat_message(message["content"], is_user=False)
        
        # Chat input
        if user_input := st.chat_input("Type your shipment inquiry here..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # Show user message immediately
            display_chat_message(user_input, is_user=True)
            
            # Process with agent
            with st.spinner("🤖 Agent is thinking..."):
                try:
                    # Run async function in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    response = loop.run_until_complete(
                        st.session_state.agent.process_message(
                            user_input,
                            st.session_state.session_id,
                            user_id="demo_user"
                        )
                    )
                    
                    # Add agent response
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # Display agent response
                    display_chat_message(response, is_user=False)
                    
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}"
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    display_chat_message(error_msg, is_user=False)
                
                finally:
                    loop.close()
    
    with col2:
        st.markdown("### 🔍 Debug Information")
        
        if st.session_state.messages:
            last_user_message = None
            for msg in reversed(st.session_state.messages):
                if msg["role"] == "user":
                    last_user_message = msg["content"]
                    break
            
            if last_user_message:
                # Analyze the last user message for debug info
                try:
                    nlu_agent = st.session_state.agent.nlu_agent
                    
                    # Extract entities
                    entities = nlu_agent.extract_entities(last_user_message)
                    
                    st.markdown("**🎯 Extracted Entities:**")
                    if entities.pro_numbers:
                        st.write(f"📋 PRO Numbers: {entities.pro_numbers}")
                    if entities.locations:
                        st.write(f"📍 Locations: {entities.locations}")
                    if entities.carriers:
                        st.write(f"🚛 Carriers: {entities.carriers}")
                    if entities.urgency_indicators:
                        st.write(f"⚠️ Urgency: {entities.urgency_indicators}")
                    if entities.dates:
                        st.write(f"📅 Dates: {entities.dates}")
                    
                    # Show recent semantic facts
                    recent_facts = st.session_state.agent.memory_manager.retrieve_semantic_facts(
                        query=last_user_message,
                        limit=3
                    )
                    
                    if recent_facts:
                        st.markdown("**🧠 Relevant Facts:**")
                        for fact in recent_facts:
                            st.write(f"• {fact.predicate}: {fact.object}")
                    
                except Exception as e:
                    st.write(f"Debug error: {e}")
        
        # Show mock shipment data
        st.markdown("### 📦 Mock Shipment Database")
        try:
            from data.sample_data import get_all_sample_pros, get_sample_shipment
            
            for pro in get_all_sample_pros():
                shipment = get_sample_shipment(pro)
                if shipment:
                    status_text = f"{shipment['status'].value.title()} ({shipment['origin']} → {shipment['destination']})"
                    st.write(f"**{pro}**: {status_text}")
        except Exception:
            # Fallback to hardcoded data
            mock_data = {
                "WE123456789": "In Transit (Atlanta → Miami)",
                "WE987654321": "Delayed (Dallas → Houston)",
                "WE555444333": "Delivered (Memphis → Nashville)"
            }
            
            for pro, status in mock_data.items():
                st.write(f"**{pro}**: {status}")
    
    # Footer with instructions
    st.markdown("---")
    st.markdown("""
    ### 🚀 How to Test the Chatbot
    
    **1. Track by PRO Number:**
    - Try: "Track PRO WE123456789" or "Where is my shipment WE987654321?"
    
    **2. Track without PRO Number:**
    - Try: "My shipment from Atlanta to Miami hasn't arrived"
    
    **3. Report Missing Shipment:**
    - Try: "My package is missing, it was supposed to be delivered yesterday"
    
    **4. Ask about Delays:**
    - Try: "Why is my FedEx shipment delayed?"
    
    The agent will demonstrate:
    - 🧠 **Memory**: Remembering previous conversations and facts
    - 🔍 **NLU**: Understanding natural language queries
    - 🌐 **API Integration**: Mock carrier API calls
    - 📧 **Email**: Automatic carrier communication
    - 🤖 **Intelligence**: Context-aware responses
    """)

if __name__ == "__main__":
    main() 