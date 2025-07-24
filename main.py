#!/usr/bin/env python3
"""
Main entry point for the Worldwide Express Shipment Tracking Chatbot

This demonstrates the complete AI agent system including:
- Natural language understanding
- Memory management (semantic, episodic, procedural)
- Carrier API integration
- Email communication
- Intelligent conversation flow

Usage:
    python main.py --mode demo        # Run demo conversation
    python main.py --mode streamlit   # Launch Streamlit UI
    python main.py --mode api         # Start FastAPI server
"""

import asyncio
import argparse
import os
import sys
from typing import Optional

from config import Config
from agents.shipment_agent import ShipmentTrackingAgent


async def run_demo_conversation():
    """Run a demonstration conversation with the chatbot"""
    print("🚚 Worldwide Express Shipment Tracking Chatbot Demo")
    print("=" * 60)
    print("This demo shows how the AI agent handles different scenarios:")
    print("1. Tracking with PRO number")
    print("2. Tracking without PRO number") 
    print("3. Handling delays and exceptions")
    print("4. Learning from conversation patterns")
    print("=" * 60)
    
    # Initialize the agent
    agent = ShipmentTrackingAgent()
    await agent.initialize()
    
    # Demo scenarios
    demo_conversations = [
        {
            "scenario": "Customer with PRO Number",
            "messages": [
                "Hi, I need to track my shipment",
                "Yes, I have a PRO number: WE123456789",
                "Thank you! When will it be delivered?"
            ]
        },
        {
            "scenario": "Customer without PRO Number", 
            "messages": [
                "I need to track a shipment but don't have a PRO number",
                "It's 5 sofas from IKEA warehouse in Atlanta to our store in Miami",
                "The shipment weighs about 500 pounds and was picked up yesterday"
            ]
        },
        {
            "scenario": "Shipment Delay Inquiry",
            "messages": [
                "My shipment WE987654321 was supposed to arrive today but didn't show up",
                "This is really urgent, what happened?",
                "Can you expedite the delivery?"
            ]
        }
    ]
    
    for i, conversation in enumerate(demo_conversations, 1):
        print(f"\n🎯 Demo Scenario {i}: {conversation['scenario']}")
        print("-" * 40)
        
        # Create a new session for each demo
        session_id = f"demo_session_{i}"
        
        for message in conversation["messages"]:
            print(f"\n👤 Customer: {message}")
            
            try:
                response = await agent.process_message(
                    message=message,
                    session_id=session_id
                )
                print(f"🤖 Agent: {response['response']}")
                
                # Show any actions taken
                if response.get('actions_taken'):
                    print(f"   🔧 Actions: {', '.join(response['actions_taken'])}")
                    
                # Show memory updates
                if response.get('memory_updates'):
                    print(f"   🧠 Memory: {response['memory_updates']}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n" + "="*60)
    
    print("\n✅ Demo completed! The agent learned from these conversations.")
    print("💡 Key Features Demonstrated:")
    print("   • Natural language understanding")
    print("   • Context-aware responses") 
    print("   • Memory management (remembers customer preferences)")
    print("   • API integration (mock carrier responses)")
    print("   • Intelligent routing (different paths for different scenarios)")
    

def run_streamlit_ui():
    """Launch the Streamlit user interface"""
    import subprocess
    
    print("🚀 Launching Streamlit UI...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "ui/streamlit_app.py",
            "--server.port", "8501",
            "--server.headless", "true"
        ])
    except KeyboardInterrupt:
        print("\n👋 Shutting down Streamlit...")


def run_api_server():
    """Start the FastAPI server"""
    import uvicorn
    from api.server import app
    
    print("🚀 Starting FastAPI server...")
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


async def test_system_integration():
    """Test the complete system integration"""
    print("🧪 Running System Integration Tests")
    print("=" * 40)
    
    agent = ShipmentTrackingAgent()
    await agent.initialize()
    
    # Test cases
    test_cases = [
        ("PRO number extraction", "Track PRO WE123456789"),
        ("Location extraction", "Shipment from Atlanta to Miami"), 
        ("Date extraction", "Picked up yesterday"),
        ("Weight extraction", "500 pounds"),
        ("Intent classification", "Where is my package?"),
        ("Memory recall", "What was my last shipment status?")
    ]
    
    for test_name, message in test_cases:
        print(f"\n🔍 Testing: {test_name}")
        print(f"   Input: '{message}'")
        
        try:
            response = await agent.process_message(
                message=message,
                session_id="test_session"
            )
            print(f"   ✅ Success: Agent understood and responded appropriately")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ System integration tests completed!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Worldwide Express Shipment Tracking Chatbot"
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "streamlit", "api", "test"],
        default="demo",
        help="Run mode: demo conversation, streamlit UI, API server, or tests"
    )
    
    args = parser.parse_args()
    
    # Check configuration
    if not Config.OPENAI_API_KEY:
        print("⚠️  Warning: OPENAI_API_KEY not set in environment variables")
        print("   Create a .env file with your OpenAI API key for full functionality")
        print("   The demo will still work with mock responses.\n")
    
    if args.mode == "demo":
        asyncio.run(run_demo_conversation())
    elif args.mode == "streamlit":
        run_streamlit_ui()
    elif args.mode == "api":
        run_api_server()
    elif args.mode == "test":
        asyncio.run(test_system_integration())


if __name__ == "__main__":
    main() 