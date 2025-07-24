# Worldwide Express Shipment Tracking Chatbot

A sophisticated AI agent system built with LangGraph for intelligent shipment tracking and carrier communication.

## 🎯 Project Overview

This chatbot serves as an intelligent intermediary between shippers (like IKEA) and carriers (like FedEx) through Worldwide Express (3PL provider). It goes far beyond simple hardcoded logic by implementing:

- **Natural Language Understanding**: Extracts PRO numbers, locations, dates, and intent from conversational text
- **Multi-layered Memory System**: Semantic, episodic, and procedural memory for learning and context
- **Intelligent Routing**: Different conversation flows based on context and user needs
- **API Integration**: Real-time communication with carrier APIs
- **Email Automation**: Automated carrier communication when PRO numbers aren't available

## 🏗️ Architecture

### Core Components

1. **State Management** (`models/state.py`)
   - Pydantic models for conversation state
   - Shipment details and status tracking
   - Type-safe data structures

2. **Memory Management** (`memory/memory_manager.py`)
   - **Semantic Memory**: Facts about shipments, carriers, customers
   - **Episodic Memory**: Past conversations and successful patterns
   - **Procedural Memory**: Evolving system prompts and strategies

3. **Natural Language Understanding** (`agents/nlu_agent.py`)
   - Intent classification (track shipment, report delay, etc.)
   - Entity extraction (PRO numbers, locations, dates)
   - Confidence scoring for decision making

4. **Carrier Integration** (`integrations/carrier_api.py`)
   - Multi-carrier API support (FedEx, UPS, Project44)
   - Mock implementations for development
   - Error handling and retry logic

5. **Email Service** (`integrations/email_service.py`)
   - Automated carrier communication
   - Customer notifications
   - Template-based email generation

6. **Main Agent** (`agents/shipment_agent.py`)
   - LangGraph orchestration
   - Complex conversation flow management
   - Decision-making logic

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key (for full AI functionality)
- Email credentials (for carrier communication)

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd LTIMindtree_chatbot
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   # Copy the example environment file
   cp env_example.txt .env
   
   # Edit .env with your actual values
   # At minimum, add your OPENAI_API_KEY
   ```

3. **Run Demo**
   ```bash
   # Run interactive demo
   python main.py --mode demo
   
   # Launch Streamlit UI
   python main.py --mode streamlit
   
   # Run system tests
   python main.py --mode test
   ```

## 💡 Why This Needs AI (Not Simple Hardcoded Logic)

Your manager was right - this problem requires more than simple if/else logic:

### 1. **Natural Language Complexity**
- Users say "track my package" not "please execute shipment tracking function"
- PRO numbers come in various formats: "WE123456789", "PRO: WE-123-456-789", "tracking number WE123456789"
- Context matters: "the urgent shipment from yesterday" vs "PRO WE123456789"

### 2. **Context and Memory**
- Customer: "What about my other shipment?" (requires remembering previous conversations)
- Follow-up questions: "When will it be delivered?" (needs to know what "it" refers to)
- Preference learning: Some customers prefer email, others want immediate phone calls

### 3. **Intelligent Decision Making**
```python
# Simple logic would be:
if has_pro_number:
    lookup_shipment()
else:
    ask_for_details()

# But reality is:
# - What if PRO number format is invalid?
# - What if customer gives partial details?
# - What if shipment is delayed and customer is frustrated?
# - What if this is the 3rd inquiry about the same shipment?
# - What if customer mentions urgency or special requirements?
```

### 4. **Learning and Adaptation**
- **Episodic Memory**: "Last time IKEA called about a delay, they needed immediate carrier escalation"
- **Semantic Memory**: "FedEx shipments from Atlanta typically take 2 days to Miami"
- **Procedural Memory**: "When customers use urgent language, prioritize carrier contact over email"

### 5. **Error Recovery and Edge Cases**
- API failures require graceful degradation
- Invalid PRO numbers need intelligent handling
- Conflicting information needs resolution
- Multiple shipments require disambiguation

## 🧠 Memory System in Action

### Example: Learning Customer Preferences

**First Interaction:**
```
Customer: "Track PRO WE123456789"
Agent: "Your shipment is in transit, arriving tomorrow. Would you like email updates?"
Customer: "Yes, but please call me if there are any delays"
```

**Memory Stored:**
- Semantic: Customer prefers email for routine updates, phone for exceptions
- Episodic: Successful resolution with proactive communication offer

**Later Interaction:**
```
Customer: "Any updates on my shipment WE987654321?" 
Agent: "There's a weather delay. Based on your preferences, I'm calling you now at 555-1234"
```

## 📊 System Components

### State Flow (LangGraph)
```
Start → Intent Classification → Entity Extraction → Memory Lookup → Action Decision → Response Generation → Memory Update
```

### Decision Tree Examples

**PRO Number Provided:**
1. Validate format
2. Check carrier APIs
3. If found: Return tracking info
4. If not found: Email carrier with details
5. Update memory with customer preference

**No PRO Number:**
1. Extract location/date/weight details
2. Search carrier APIs by details
3. If multiple matches: Disambiguate with customer
4. If no matches: Request additional details
5. Escalate to carrier if still unresolved

## 🔧 Configuration

### Environment Variables

See `env_example.txt` for all configuration options.

**Required:**
- `OPENAI_API_KEY`: For AI functionality
- `EMAIL_USERNAME` / `EMAIL_PASSWORD`: For carrier communication

**Optional:**
- Carrier API keys (falls back to mock data)
- Database configuration (defaults to SQLite)

### Memory Settings

```python
# Memory retention and limits
MEMORY_RETENTION_DAYS=90
MAX_CONVERSATION_HISTORY=50
ENABLE_MEMORY_PERSISTENCE=true
```

## 🧪 Testing

```bash
# Run integration tests
python main.py --mode test

# Test specific components
python -m pytest tests/

# Test NLU extraction
python -c "
from agents.nlu_agent import NLUAgent
agent = NLUAgent()
result = agent.extract_entities('Track PRO WE123456789 please')
print(result)
"
```

## 📁 Project Structure

```
LTIMindtree_chatbot/
├── agents/                 # AI agents
│   ├── shipment_agent.py  # Main LangGraph agent
│   └── nlu_agent.py       # Natural language understanding
├── integrations/          # External service integrations
│   ├── carrier_api.py     # Carrier API clients
│   └── email_service.py   # Email automation
├── memory/                # Memory management
│   └── memory_manager.py  # Multi-type memory system
├── models/                # Data models
│   └── state.py           # Pydantic state models
├── ui/                    # User interfaces
│   └── streamlit_app.py   # Demo UI
├── data/                  # Sample data
│   └── sample_data.py     # Test shipments and templates
├── config.py              # Configuration management
├── main.py               # Application entry point
└── requirements.txt      # Dependencies
```

## 🚀 Deployment

### Local Development
```bash
python main.py --mode streamlit
```

### Production API
```bash
python main.py --mode api
```

### Docker (Optional)
```bash
docker build -t shipment-chatbot .
docker run -p 8000:8000 shipment-chatbot
```

## 🎓 Learning Outcomes

This project demonstrates:

1. **LangGraph Usage**: Complex state management and conversation flow
2. **Memory Systems**: Semantic, episodic, and procedural memory implementation
3. **NLU Techniques**: Intent classification and entity extraction
4. **API Integration**: Real-world carrier API patterns
5. **Production Readiness**: Error handling, logging, configuration management

## 🤝 Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Ensure memory systems are properly utilized

## 📞 Support

For questions about the implementation or logistics concepts:
- Review the code comments (extensive documentation included)
- Check the demo scenarios in `main.py`
- Examine the sample data in `data/sample_data.py`

---

**Built with ❤️ for Worldwide Express by the Technical Team**