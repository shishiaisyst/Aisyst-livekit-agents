# LiveKit Agent-Assisted Warm Transfer Implementation Guide

**Last Updated:** February 10, 2026  
**Purpose:** Complete guide for implementing warm transfer from AI agent to human operator  
**Official Documentation:** https://docs.livekit.io/telephony/features/transfers/warm/

---

## Table of Contents

1. [Overview](#overview)
2. [What is Warm Transfer?](#what-is-warm-transfer)
3. [Prerequisites](#prerequisites)
4. [Implementation Approaches](#implementation-approaches)
5. [Method 1: Using WarmTransferTask (Recommended)](#method-1-using-warmtransfertask-recommended)
6. [Method 2: Manual Implementation](#method-2-manual-implementation)
7. [Success Rate Factors](#success-rate-factors)
8. [Testing & Validation](#testing--validation)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

**Agent-assisted warm transfer** allows our AI voice agent to transfer a call to a human operator while:
- ✅ Placing the customer on hold
- ✅ Providing context/summary to the human operator
- ✅ Ensuring smooth handoff without dropping the call
- ✅ Allowing the agent to introduce both parties before disconnecting

This is critical for scenarios where the AI cannot resolve customer queries and human intervention is needed.

---

## What is Warm Transfer?

### Warm Transfer vs Cold Transfer
### Livekit provides two ways to transfer a call to a human operator:

1. Warm Transfer
2. Cold Transfer

### We are only interested in using Warm Transfer

| Feature | Warm Transfer | Cold Transfer |
|---------|--------------|---------------|
| **Customer Experience** | Placed on hold, then connected | Directly transferred |
| **Context Sharing** | Agent briefs human operator first | No context provided |
| **Fallback Option** | Agent can return if operator unavailable | Call may fail |
| **Professional** | ✅ Yes | ❌ Less professional |

### How It Works (Customer Perspective)

```
1. Customer speaks with AI Agent
2. Customer requests human assistance
3. AI Agent: "Let me connect you with a specialist. Please hold."
4. [Hold music plays]
5. Human operator answers and is briefed by AI
6. Customer is connected to human operator
7. AI Agent (optional): "Hi [Customer], I have [Operator] on the line to help you."
8. AI Agent disconnects
9. Customer continues conversation with human operator
```

### Behind the Scenes Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Customer in active call with SupportAgent          │
│  Customer: "I need to speak with a manager"                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: SupportAgent places customer on hold               │
│  - Disable customer audio input/output                      │
│  - Play hold music (optional)                               │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Create consultation room                           │
│  - New private room for agent-supervisor conversation       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Call supervisor's phone number                     │
│  - Uses SIP trunk to dial human operator                    │
│  - Supervisor joins consultation room                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: TransferAgent summarizes call to supervisor        │
│  Agent: "Customer Vlad called about a dietary restriction
  and want to talk to the staff directly    │
│                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Move supervisor to customer's room                 │
│  - Supervisor is transferred to main call room              │
│  - Customer is taken off hold                               │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 7: (Optional) Agent introduces both parties           │
│  Agent: "Hi John, I have Sarah from our support team."      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 8: Both agents disconnect                             │
│  - SupportAgent leaves customer room                        │
│  - TransferAgent leaves consultation room                   │
│  - Customer and supervisor continue 1-on-1                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. **SIP Trunk Configuration**

We **must** have an outbound SIP trunk configured to dial external phone numbers.

**Required:**
- ✅ Outbound trunk ID (to call the human operator)
- ✅ Supervisor's phone number (human operator to transfer to)

**Optional (for receiving calls):**
- Inbound trunk
- Dispatch rule

**Setup Guide:** https://docs.livekit.io/telephony/start/sip-trunk-setup/


## Implementation Approaches

LiveKit offers **two methods** for implementing warm transfer:

| Method | Complexity | Control | Use Case |
|--------|-----------|---------|----------|
| **WarmTransferTask** | ⭐ Easy | Limited | Most use cases (recommended) |
| **Manual Implementation** | ⭐⭐⭐ Advanced | Full | Custom workflows, special requirements |

---

## Method 1: Using WarmTransferTask (Recommended)

### Overview

The `WarmTransferTask` is a **prebuilt agent task** that handles the entire warm transfer workflow automatically.

### Advantages

- ✅ **Simple implementation** (3 lines of code)
- ✅ **Automatic orchestration** (handles all steps)
- ✅ **Error handling** built-in
- ✅ **Conversation history** passed automatically
- ✅ **Production-ready**

---

## Integration with Our Existing CodeBase comleted by Ahmed

Based on your current `Livekit_Voice_Agent.py` implementation, here's exactly where to add the warm transfer functionality:

### Step 1: We need to add a couple opf additional import at the top of file.

**Location:** Line 5-18 (with other imports)

```python
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    llm,
    metrics,
)
from livekit.plugins import cartesia, deepgram, groq, openai, silero
from livekit import api  # ← ADD THIS LINE for warm transfer APIs
from livekit.agents.beta.workflows import WarmTransferTask  # ← ADD THIS LINE
```

### Step 2: Add Configuration Constants

**Location:** After line 26 (after logger definitions)

```python
logger = logging.getLogger("voice-agent")
latency_logger = logging.getLogger("latency")

# ← ADD THESE LINES
# Warm Transfer Configuration
SUPERVISOR_PHONE = os.getenv("SUPERVISOR_PHONE", "+61412345678")  # Our supervisor's phone
SIP_TRUNK_ID = os.getenv("SIP_TRUNK_ID", "trunk_abc123xyz")      # Our SIP trunk ID
```

### Step 3: Add Transfer Function to RestaurantAgent Class

**Location:** Inside `RestaurantAgent` class, after line 928 (after `end_call` function)

```python
    @function_tool()
    async def end_call(self, reason: str = "completed") -> str:
        """
        End the call with a friendly goodbye. Call this when the order is complete or customer wants to hang up.

        Args:
            reason: Why the call is ending (completed, cancelled, customer_request)
        """
        if reason == "completed":
            return "Thank you for your order! Have a great day. Goodbye!"
        elif reason == "cancelled":
            return "No problem! Feel free to call back anytime. Goodbye!"
        else:
            return "Thanks for calling! Goodbye!"

    # ← ADD THIS NEW FUNCTION HERE
    @function_tool()
    async def transfer_to_human(self, reason: str = "customer request") -> str:
        """
        Transfer the call to a human operator when the AI cannot resolve the customer's issue.
        
        Use this when:
        - Customer explicitly requests to speak with a human
        - Customer has dietary restrictions or special requirements
        - Issue is too complex for AI to handle
        - Customer is frustrated or upset
        
        Args:
            reason: Reason for transfer (for logging purposes)
        """
        logger.info(f"🔄 Transfer initiated for call {self.call_id}. Reason: {reason}")
        
        # Inform customer
        await self.say(
            "I understand. Let me connect you with one of our staff members "
            "who can better assist you. Please hold for just a moment."
        )
        
        try:
            # Execute warm transfer using WarmTransferTask
            result = await WarmTransferTask(
                target_phone_number=SUPERVISOR_PHONE,
                sip_trunk_id=SIP_TRUNK_ID,
                chat_ctx=self.chat_ctx,  # Pass conversation history
            )
            
            if result.success:
                logger.info(f"✅ Transfer successful: {self.call_id} → {SUPERVISOR_PHONE}")
                return {
                    "status": "transferred",
                    "message": "Call transferred successfully to human operator"
                }
            else:
                logger.error(f"❌ Transfer failed: {result.error}")
                await self.say(
                    "I apologize, but our staff is currently unavailable. "
                    "Let me see how I can help you directly."
                )
                return {
                    "status": "failed",
                    "error": result.error
                }
                
        except Exception as e:
            logger.exception(f"❌ Transfer exception: {e}")
            await self.say(
                "I apologize for the technical difficulty. "
                "How can I assist you with your order?"
            )
            return {
                "status": "error",
                "error": str(e)
            }
```

### Step 4: Store Chat Context in Agent

**Location:** Modify `RestaurantAgent.__init__()` at line 575

**Current code:**
```python
class RestaurantAgent(Agent):
    """Restaurant order-taking voice agent."""

    def __init__(self, language: str = "en", menu_items: str = ""):
        # Use concise English-only prompt with preloaded menu
        super().__init__(
            instructions=get_system_prompt(language, multilingual=False, menu_items=menu_items),
        )
        # Order state
        self.current_order = []
        self.call_id = None
        self.caller_number = None
        # Language state
        self.current_language = language
```

**Modified code:**
```python
class RestaurantAgent(Agent):
    """Restaurant order-taking voice agent."""

    def __init__(self, language: str = "en", menu_items: str = ""):
        # Use concise English-only prompt with preloaded menu
        super().__init__(
            instructions=get_system_prompt(language, multilingual=False, menu_items=menu_items),
        )
        # Order state
        self.current_order = []
        self.call_id = None
        self.caller_number = None
        # Language state
        self.current_language = language
        # ← ADD THIS LINE: We need to store chat context as well to pass the past context to the human operator for warm transfer
        self.chat_ctx = llm.ChatContext()
```

### Step 5: Update System Prompt (Optional but Recommended)


---

## Complete Integration Example

Here's how our modified `Livekit_Voice_Agent.py` will look with warm transfer:

```python
"""Main voice agent implementation using LiveKit Agents framework (v1.3+)."""
import logging
import os
import time
from datetime import datetime
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    llm,
    metrics,
)
from livekit.plugins import cartesia, deepgram, groq, openai, silero
from livekit import api  # ← NEW: For warm transfer
from livekit.agents.beta.workflows import WarmTransferTask  # ← NEW

from .config import settings
from .prompts import get_system_prompt, get_greeting
from .tools.supabase_client import supabase

logger = logging.getLogger("voice-agent")
latency_logger = logging.getLogger("latency")

# ← NEW: Warm Transfer Configuration
SUPERVISOR_PHONE = os.getenv("SUPERVISOR_PHONE", "+61412345678")
SIP_TRUNK_ID = os.getenv("SIP_TRUNK_ID", "trunk_abc123xyz")

# ... rest of our existing code (create_llm, LatencyTracker, etc.) ...

class RestaurantAgent(Agent):
    """Restaurant order-taking voice agent."""

    def __init__(self, language: str = "en", menu_items: str = ""):
        super().__init__(
            instructions=get_system_prompt(language, multilingual=False, menu_items=menu_items),
        )
        self.current_order = []
        self.call_id = None
        self.caller_number = None
        self.current_language = language
        self.chat_ctx = llm.ChatContext()  # ← NEW: For warm transfer

    # ... all our existing function_tool methods ...
    # (get_menu_items, add_to_order, submit_order, etc.)

    @function_tool()
    async def transfer_to_human(self, reason: str = "customer request") -> str:
        """Transfer call to human operator."""
        logger.info(f"🔄 Transfer initiated: {reason}")
        
        await self.say("Let me connect you with our staff. Please hold.")
        
        try:
            result = await WarmTransferTask(
                target_phone_number=SUPERVISOR_PHONE,
                sip_trunk_id=SIP_TRUNK_ID,
                chat_ctx=self.chat_ctx,
            )
            
            if result.success:
                logger.info(f"✅ Transfer successful")
                return {"status": "transferred"}
            else:
                logger.error(f"❌ Transfer failed: {result.error}")
                await self.say("Staff unavailable. How can I help you?")
                return {"status": "failed", "error": result.error}
                
        except Exception as e:
            logger.exception(f"❌ Transfer error: {e}")
            await self.say("Technical difficulty. How can I assist you?")
            return {"status": "error", "error": str(e)}

# ... rest of your existing code (entrypoint, main, etc.) ...
```

---

## Environment Variables to Add

Add these to your `.env` file:

```bash
# Warm Transfer Configuration
SUPERVISOR_PHONE="+61412345678"    # Replace with actual supervisor phone
SIP_TRUNK_ID="trunk_abc123xyz"    # Replace with your SIP trunk ID from LiveKit
```

---

## Testing the Integration

### 1. Test Locally

```bash
# Set environment variables
export SUPERVISOR_PHONE="+61412345678"
export SIP_TRUNK_ID="trunk_abc123"

# Run the agent
python -m livekit.Livekit_Voice_Agent
```

### 2. Test Transfer Trigger

Make a test call and say:
- "I need to speak with someone"
- "Can I talk to a human?"
- "I have dietary restrictions"
- "Transfer me to staff"

### 3. Monitor Logs

Watch for these log messages:
```
🔄 Transfer initiated for call <call_id>. Reason: customer request
✅ Transfer successful: <call_id> → +61412345678
```

---

## Implementation

### Step 1: Import Required Modules

```python
from livekit.agents.beta.workflows import WarmTransferTask
from livekit import rtc, api
```

#### Step 2: Define Transfer Logic in Your Agent

```python
from livekit.agents import Agent, llm
from livekit.agents.beta.workflows import WarmTransferTask

class SupportAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a customer support agent who solves queries regarding menu and order. "
                "If the customer requests to speak with a human, "
                "or if you cannot resolve their issue, "
                "offer to transfer them to a supervisor."
            ),
            # ... other agent configuration
        )
        
        # Store conversation context
        self.chat_ctx = llm.ChatContext()
    
    async def handle_transfer_request(self, supervisor_phone: str, trunk_id: str):
        """
        Execute warm transfer when customer requests human assistance
        
        Args:
            supervisor_phone: Phone number of human operator (e.g., "+1234567890")
            trunk_id: Your outbound SIP trunk ID
        """
        try:
            # Execute warm transfer
            result = await WarmTransferTask(
                target_phone_number=supervisor_phone,  # Supervisor's phone
                sip_trunk_id=trunk_id,                 # Outbound trunk ID
                chat_ctx=self.chat_ctx,                # Conversation history
            )
            
            if result.success:
                print(f"✅ Transfer successful to {supervisor_phone}")
            else:
                print(f"❌ Transfer failed: {result.error}")
                # Fallback: Return to customer and explain
                await self.say("I'm sorry, the supervisor is unavailable. How else can I help?")
                
        except Exception as e:
            print(f"❌ Transfer error: {e}")
            await self.say("I apologize, but I'm having trouble connecting you. Let me try to help you myself.")
```

#### Step 3: Trigger Transfer Based on Customer Intent

```python
from livekit.agents import function_tool

class SupportAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a support agent. Use transfer_to_human when needed.",
        )
        self.chat_ctx = llm.ChatContext()
        
        # Define transfer as a tool/function
        self.register_function(self.transfer_to_human)
    
    @function_tool(
        description="Transfer the call to a human supervisor when the customer requests it or when you cannot help"
    )
    async def transfer_to_human(self):
        """Transfer call to human operator"""
        SUPERVISOR_PHONE = "+61412345678"  # Your supervisor's phone
        SIP_TRUNK_ID = "trunk_abc123xyz"   # Your outbound trunk ID
        
        # Inform customer
        await self.say("Let me connect you with a specialist. Please hold for a moment.")
        
        # Execute transfer
        result = await WarmTransferTask(
            target_phone_number=SUPERVISOR_PHONE,
            sip_trunk_id=SIP_TRUNK_ID,
            chat_ctx=self.chat_ctx,
        )
        
        return {"success": result.success}
```

#### Step 4: Full Example with Agent Deployment

```python
import asyncio
import os
from livekit import rtc, api
from livekit.agents import Agent, JobContext, WorkerOptions, cli, llm
from livekit.agents.beta.workflows import WarmTransferTask

# Configuration
SUPERVISOR_PHONE = os.getenv("SUPERVISOR_PHONE", "+61412345678")
SIP_TRUNK_ID = os.getenv("SIP_TRUNK_ID", "trunk_abc123")

class SupportAgent(Agent):
    def __init__(self, ctx: JobContext):
        self.ctx = ctx
        self.chat_ctx = llm.ChatContext()
        
        super().__init__(
            instructions=(
                "You are a friendly customer support agent for Aisyst. "
                "Help customers with their queries. "
                "If you cannot resolve an issue or the customer requests a human, "
                "use the transfer_to_human function."
            ),
            llm=llm.LLM(model="gpt-4"),
        )
        
        # Register transfer function
        self.register_function(self.transfer_to_human)
    
    @llm.function_tool(
        description="Transfer the customer to a human supervisor"
    )
    async def transfer_to_human(self):
        """Execute warm transfer to human operator"""
        
        # Notify customer
        await self.say("I'll connect you with one of our specialists. Please hold.")
        
        try:
            # Execute warm transfer
            result = await WarmTransferTask(
                target_phone_number=SUPERVISOR_PHONE,
                sip_trunk_id=SIP_TRUNK_ID,
                chat_ctx=self.chat_ctx,
            )
            
            if result.success:
                return {"status": "transferred", "message": "Call transferred successfully"}
            else:
                await self.say("I'm sorry, our specialist is unavailable. Let me help you instead.")
                return {"status": "failed", "error": result.error}
                
        except Exception as e:
            await self.say("I apologize for the technical difficulty. How can I assist you?")
            return {"status": "error", "error": str(e)}

# Entry point for LiveKit agent
async def entrypoint(ctx: JobContext):
    """Main entry point for the agent"""
    
    # Wait for participant to join
    await ctx.connect()
    
    # Create and start the agent
    agent = SupportAgent(ctx)
    await agent.start(ctx.room)

if __name__ == "__main__":
    # Run the agent worker
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

### Additional WarmTransferTask Parameters

```python
result = await WarmTransferTask(
    target_phone_number="+61412345678",      # Required: Supervisor's phone
    sip_trunk_id="trunk_abc123",             # Required: Outbound trunk ID
    chat_ctx=self.chat_ctx,                  # Required: Conversation history
    
    # Optional parameters:
    participant_identity="Supervisor",        # Identity for supervisor in room
    wait_until_answered=True,                # Wait for supervisor to answer
    consultation_room_name="consult-123",    # Custom consultation room name
    introduction_message="Hi, connecting you now",  # Custom introduction
)
```

---

## Method 2: Manual Implementation

### When to Use Manual Implementation

Use manual implementation when you need:
- Custom consultation room logic
- Multiple transfer attempts with different supervisors
- Complex state management
- Custom hold music or messaging
- Integration with external systems during transfer

### Architecture Overview

Manual implementation requires **two agent sessions**:

1. **SupportAgent**: Handles initial customer interaction
2. **TransferAgent**: Briefs the supervisor in consultation room

### Full Manual Implementation

#### Step 1: Session Management Class

```python
from enum import Enum
from typing import Optional
from livekit import rtc

class CallerState(Enum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    INACTIVE = "inactive"

class SupervisorState(Enum):
    INACTIVE = "inactive"
    SUMMARIZING = "summarizing"
    MERGED = "merged"
    FAILED = "failed"

class TransferSessionManager:
    """Manages state across agents and participants during warm transfer"""
    
    def __init__(self):
        self.caller_state = CallerState.ACTIVE
        self.supervisor_state = SupervisorState.INACTIVE
        self.customer_room: Optional[rtc.Room] = None
        self.consult_room: Optional[rtc.Room] = None
        self.customer_identity: Optional[str] = None
        self.supervisor_identity: Optional[str] = None
    
    async def place_caller_on_hold(self, session):
        """Place caller on hold by disabling audio"""
        self.caller_state = CallerState.ESCALATED
        
        # Disable audio input/output
        session.input.set_audio_enabled(False)
        session.output.set_audio_enabled(False)
        
        # Optional: Play hold music
        await self.play_hold_music(session)
    
    async def play_hold_music(self, session):
        """Play hold music to customer"""
        # Implementation depends on your audio setup
        # See: https://docs.livekit.io/agents/logic/audio/
        pass
    
    async def take_caller_off_hold(self, session):
        """Resume customer audio"""
        self.caller_state = CallerState.ACTIVE
        session.input.set_audio_enabled(True)
        session.output.set_audio_enabled(True)
    
    async def create_consultation_room(self, room_name: str) -> rtc.Room:
        """Create private room for agent-supervisor consultation"""
        self.consult_room = rtc.Room()
        return self.consult_room
```

#### Step 2: SupportAgent (Initial Agent)

```python
from livekit.agents import Agent, JobContext, llm
from livekit import api, rtc
import os

class SupportAgent(Agent):
    def __init__(self, ctx: JobContext, session_manager: TransferSessionManager):
        self.ctx = ctx
        self.session_manager = session_manager
        self.chat_ctx = llm.ChatContext()
        
        super().__init__(
            instructions="You are a support agent. Transfer to human when needed.",
        )
        
        self.register_function(self.initiate_transfer)
    
    @llm.function_tool(description="Initiate transfer to human supervisor")
    async def initiate_transfer(self):
        """Start the warm transfer process"""
        
        # Step 1: Place caller on hold
        await self.say("Let me connect you with a specialist. Please hold.")
        await self.session_manager.place_caller_on_hold(self.ctx.session)
        
        # Step 2: Create consultation room
        consult_room_name = f"consult-{self.ctx.room.name}"
        consult_room = await self.session_manager.create_consultation_room(consult_room_name)
        
        # Step 3: Generate token for TransferAgent
        transfer_agent_identity = "transfer-agent"
        token = self.generate_token(consult_room_name, transfer_agent_identity)
        
        # Step 4: Connect TransferAgent to consultation room
        await consult_room.connect(os.getenv("LIVEKIT_URL"), token)
        
        # Step 5: Call supervisor
        await self.call_supervisor(consult_room_name)
        
        # Step 6: Create TransferAgent with conversation history
        transfer_agent = TransferAgent(prev_ctx=self.chat_ctx, session_manager=self.session_manager)
        
        return {"status": "transfer_initiated"}
    
    def generate_token(self, room_name: str, identity: str) -> str:
        """Generate access token for consultation room"""
        access_token = (
            api.AccessToken()
            .with_identity(identity)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_update_own_metadata=True,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
        )
        return access_token.to_jwt()
    
    async def call_supervisor(self, consult_room_name: str):
        """Dial supervisor into consultation room"""
        SIP_TRUNK_ID = os.getenv("SIP_TRUNK_ID")
        SUPERVISOR_PHONE = os.getenv("SUPERVISOR_PHONE")
        
        await self.ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=SIP_TRUNK_ID,
                sip_call_to=SUPERVISOR_PHONE,
                room_name=consult_room_name,
                participant_identity="Supervisor",
                wait_until_answered=True,
            )
        )
```

#### Step 3: TransferAgent (Consultation Agent)

```python
class TransferAgent(Agent):
    def __init__(self, prev_ctx: llm.ChatContext, session_manager: TransferSessionManager):
        self.session_manager = session_manager
        
        # Extract conversation history
        prev_convo = self.extract_conversation_history(prev_ctx)
        
        super().__init__(
            instructions=(
                f"You are briefing a supervisor about a customer call. "
                f"Here is the conversation history:\n{prev_convo}\n\n"
                f"Summarize the customer's issue and provide relevant context."
            ),
        )
    
    def extract_conversation_history(self, prev_ctx: llm.ChatContext) -> str:
        """Convert chat context to readable conversation history"""
        prev_convo = ""
        context_copy = prev_ctx.copy(
            exclude_empty_message=True,
            exclude_instructions=True,
            exclude_function_call=True
        )
        
        for msg in context_copy.items:
            if msg.role == "user":
                prev_convo += f"Customer: {msg.text_content}\n"
            else:
                prev_convo += f"Assistant: {msg.text_content}\n"
        
        return prev_convo
    
    async def brief_supervisor(self):
        """Provide summary to supervisor"""
        self.session_manager.supervisor_state = SupervisorState.SUMMARIZING
        
        # Agent automatically speaks based on instructions
        # The LLM will generate a summary from the conversation history
        
    async def move_supervisor_to_customer(self, ctx: JobContext):
        """Move supervisor from consultation room to customer room"""
        
        await ctx.api.room.move_participant(
            api.MoveParticipantRequest(
                room=self.session_manager.consult_room.name,
                identity="Supervisor",
                destination_room=self.session_manager.customer_room.name,
            )
        )
        
        self.session_manager.supervisor_state = SupervisorState.MERGED
        
        # Take customer off hold
        await self.session_manager.take_caller_off_hold(ctx.session)
    
    async def provide_introduction(self):
        """Optional: Introduce customer and supervisor"""
        await self.say("Hi, I have our specialist on the line to assist you.")
    
    async def disconnect(self):
        """Leave the consultation room"""
        await self.session_manager.consult_room.disconnect()
```

#### Step 4: Complete Workflow Orchestration

```python
async def execute_warm_transfer(
    support_agent: SupportAgent,
    customer_session: JobContext,
    supervisor_phone: str,
    sip_trunk_id: str
):
    """
    Complete warm transfer workflow
    """
    
    # Initialize session manager
    session_manager = TransferSessionManager()
    session_manager.customer_room = customer_session.room
    session_manager.customer_identity = customer_session.participant.identity
    
    try:
        # Step 1: Place customer on hold
        await session_manager.place_caller_on_hold(customer_session.session)
        
        # Step 2: Create consultation room
        consult_room_name = f"consult-{customer_session.room.name}"
        consult_room = await session_manager.create_consultation_room(consult_room_name)
        
        # Step 3: Generate token and connect TransferAgent
        token = support_agent.generate_token(consult_room_name, "transfer-agent")
        await consult_room.connect(os.getenv("LIVEKIT_URL"), token)
        
        # Step 4: Call supervisor
        await customer_session.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=sip_trunk_id,
                sip_call_to=supervisor_phone,
                room_name=consult_room_name,
                participant_identity="Supervisor",
                wait_until_answered=True,
            )
        )
        
        # Step 5: Create TransferAgent and brief supervisor
        transfer_agent = TransferAgent(
            prev_ctx=support_agent.chat_ctx,
            session_manager=session_manager
        )
        await transfer_agent.brief_supervisor()
        
        # Step 6: Move supervisor to customer room
        await transfer_agent.move_supervisor_to_customer(customer_session)
        
        # Step 7: Optional introduction
        await transfer_agent.provide_introduction()
        
        # Step 8: Disconnect agents
        await transfer_agent.disconnect()
        await support_agent.disconnect()
        
        return {"success": True}
        
    except Exception as e:
        # Fallback: Return to customer
        await session_manager.take_caller_off_hold(customer_session.session)
        await support_agent.say("I apologize, the supervisor is unavailable. How can I help you?")
        return {"success": False, "error": str(e)}
```

---

## Success Rate Factors

### Factors Affecting Transfer Success

| Factor | Impact | Mitigation |
|--------|--------|------------|
| **Supervisor availability** | High | Use `wait_until_answered=True` |
| **SIP trunk reliability** | High | Use reputable provider (Twilio, Telnyx) |
| **Network latency** | Medium | Deploy agents close to SIP trunk region |
| **Token expiration** | Low | Generate tokens with sufficient TTL |
| **Room capacity** | Low | Monitor concurrent transfers |

### Expected Success Rates

**With proper setup:**
- ✅ **95-98%** success rate for answered calls
- ✅ **80-85%** success rate including unanswered calls
- ❌ **2-5%** failure rate (network issues, busy signals)

### Improving Success Rate

```python
# 1. Add retry logic
async def transfer_with_retry(phone: str, trunk_id: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            result = await WarmTransferTask(
                target_phone_number=phone,
                sip_trunk_id=trunk_id,
                chat_ctx=self.chat_ctx,
                wait_until_answered=True,  # Wait for answer
            )
            
            if result.success:
                return result
            
            # Wait before retry
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            continue
    
    return {"success": False, "error": "Max retries exceeded"}

# 2. Multiple supervisor fallback
async def transfer_to_available_supervisor(supervisors: list[str], trunk_id: str):
    """Try multiple supervisors until one answers"""
    for supervisor_phone in supervisors:
        result = await WarmTransferTask(
            target_phone_number=supervisor_phone,
            sip_trunk_id=trunk_id,
            chat_ctx=self.chat_ctx,
        )
        
        if result.success:
            return result
    
    return {"success": False, "error": "No supervisors available"}

# 3. Timeout handling
async def transfer_with_timeout(phone: str, trunk_id: str, timeout: int = 30):
    """Transfer with timeout"""
    try:
        result = await asyncio.wait_for(
            WarmTransferTask(
                target_phone_number=phone,
                sip_trunk_id=trunk_id,
                chat_ctx=self.chat_ctx,
            ),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        return {"success": False, "error": "Transfer timeout"}
```

---

## Testing & Validation

### Test Checklist

- [ ] **SIP trunk configured** and tested
- [ ] **Supervisor phone number** is correct and reachable
- [ ] **Environment variables** are set correctly
- [ ] **Agent can place calls** using the SIP trunk
- [ ] **Hold music** plays correctly (if implemented)
- [ ] **Conversation history** is passed to TransferAgent
- [ ] **Supervisor receives context** before customer connection
- [ ] **Customer is taken off hold** when supervisor joins
- [ ] **Both agents disconnect** cleanly after transfer
- [ ] **Error handling** works for unavailable supervisor

### Testing in Agent Playground

LiveKit provides an Agent Playground as well for testing this feature:

1. Go to https://cloud.livekit.io/
2. Navigate to **Agent Playground**
3. Deploy your agent
4. Make a test call
5. Request transfer: "I need to speak with a human"
6. Verify the workflow

**Note:** Outbound trunk is required for playground testing.

### Local Testing

```bash
# 1. Set environment variables
export LIVEKIT_URL="wss://your-project.livekit.cloud"
export LIVEKIT_API_KEY="your-api-key"
export LIVEKIT_API_SECRET="your-api-secret"
export SIP_TRUNK_ID="trunk_abc123"
export SUPERVISOR_PHONE="+61412345678"

# 2. Run your agent locally
python your_agent.py

# 3. Make a test call to your agent's number
# 4. Request transfer during the call
```

### Monitoring Transfer Success

```python
import logging

# Add logging to track transfers
logger = logging.getLogger(__name__)

async def transfer_to_human(self):
    logger.info(f"Transfer initiated for customer {self.customer_id}")
    
    try:
        result = await WarmTransferTask(
            target_phone_number=SUPERVISOR_PHONE,
            sip_trunk_id=SIP_TRUNK_ID,
            chat_ctx=self.chat_ctx,
        )
        
        if result.success:
            logger.info(f"✅ Transfer successful: {self.customer_id} → {SUPERVISOR_PHONE}")
        else:
            logger.error(f"❌ Transfer failed: {result.error}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Transfer exception: {e}")
        raise
```

---

## Troubleshooting

### Common Issues

#### 1. **Transfer fails immediately**

**Symptoms:**
- Transfer returns `success: False` instantly
- No call is placed to supervisor

**Causes:**
- Invalid SIP trunk ID
- Incorrect supervisor phone number format
- SIP trunk not configured for outbound calls

**Solutions:**
```python
# Verify SIP trunk ID
print(f"Using trunk: {SIP_TRUNK_ID}")

# Verify phone number format (E.164)
# Correct: "+61412345678"
# Wrong: "0412345678", "61412345678"

# Test SIP trunk separately
await ctx.api.sip.create_sip_participant(
    api.CreateSIPParticipantRequest(
        sip_trunk_id=SIP_TRUNK_ID,
        sip_call_to="+61412345678",  # Test number
        room_name="test-room",
        participant_identity="test",
    )
)
```

#### 2. **Supervisor doesn't receive call**

**Symptoms:**
- Transfer appears to succeed
- Supervisor's phone doesn't ring

**Causes:**
- SIP trunk routing issue
- Phone number blocked/invalid
- Carrier rejection

**Solutions:**
- Check SIP trunk logs in LiveKit dashboard
- Verify phone number is reachable
- Test with alternative phone number
- Contact SIP provider support

#### 3. **Customer hears silence instead of hold music**

**Symptoms:**
- Customer is on hold but hears nothing

**Solutions:**
```python
# Implement hold music
async def play_hold_music(self, session):
    """Play hold music from audio file"""
    from livekit.agents import audio
    
    hold_music_path = "path/to/hold_music.mp3"
    await audio.play_file(session, hold_music_path, loop=True)
```

#### 4. **Conversation history not passed to supervisor**

**Symptoms:**
- Supervisor has no context about the call

**Solutions:**
```python
# Ensure chat_ctx is populated
self.chat_ctx = llm.ChatContext()

# Verify context before transfer
print(f"Chat history items: {len(self.chat_ctx.items)}")

# Pass to WarmTransferTask
result = await WarmTransferTask(
    target_phone_number=SUPERVISOR_PHONE,
    sip_trunk_id=SIP_TRUNK_ID,
    chat_ctx=self.chat_ctx,  # ← Ensure this is passed
)
```

#### 5. **Agents don't disconnect after transfer**

**Symptoms:**
- Agents remain in rooms after transfer
- Resources not cleaned up

**Solutions:**
```python
# Explicitly disconnect agents
async def complete_transfer(self):
    # After supervisor is connected
    await self.support_agent.disconnect()
    await self.transfer_agent.disconnect()
    
    # Close rooms
    await self.consult_room.disconnect()
```

#### 6. **Token expiration errors**

**Symptoms:**
- `Invalid token` or `Token expired` errors

**Solutions:**
```python
# Generate token with longer TTL
access_token = (
    api.AccessToken()
    .with_identity(identity)
    .with_ttl(3600)  # 1 hour TTL
    .with_grants(...)
)
```

---

## Best Practices

### 1. **Always Inform the Customer**

```python
# Good
await self.say("Let me connect you with a specialist. Please hold for a moment.")
await execute_transfer()

# Bad
await execute_transfer()  # Customer has no idea what's happening
```

### 2. **Provide Context to Supervisor**

```python
# Include relevant information in conversation history
self.chat_ctx.append(
    role="system",
    content=f"Customer ID: {customer_id}, Issue: {issue_type}, Priority: {priority}"
)
```

### 3. **Handle Failures Gracefully**

```python
result = await WarmTransferTask(...)

if not result.success:
    # Don't just fail silently
    await self.say(
        "I apologize, but our specialist is currently unavailable. "
        "Let me see how I can help you directly, or you can try calling back later."
    )
    
    # Log for follow-up
    logger.error(f"Transfer failed for customer {customer_id}: {result.error}")
```

### 4. **Use Retry Logic for Critical Transfers**

```python
async def transfer_with_retry(self, max_attempts: int = 3):
    for attempt in range(max_attempts):
        result = await WarmTransferTask(...)
        
        if result.success:
            return result
        
        if attempt < max_attempts - 1:
            await self.say("Having trouble connecting. Let me try again.")
            await asyncio.sleep(2)
    
    # All attempts failed
    await self.say("I'm unable to connect you right now. How else can I help?")
```

### 5. **Monitor and Log Transfers**

```python
# Track transfer metrics
transfer_metrics = {
    "timestamp": datetime.now(),
    "customer_id": customer_id,
    "supervisor_phone": supervisor_phone,
    "success": result.success,
    "duration": transfer_duration,
    "error": result.error if not result.success else None,
}

# Send to analytics/monitoring system
await analytics.track("warm_transfer", transfer_metrics)
```

### 6. **Test Regularly**

- Schedule weekly test calls
- Rotate through different supervisors
- Test during peak hours
- Verify hold music playback
- Check conversation history accuracy

### 7. **Have Fallback Supervisors**

```python
SUPERVISORS = [
    "+61412345678",  # Primary
    "+61498765432",  # Secondary
    "+61487654321",  # Tertiary
]

async def transfer_to_available_supervisor(self):
    for supervisor in SUPERVISORS:
        result = await WarmTransferTask(
            target_phone_number=supervisor,
            sip_trunk_id=SIP_TRUNK_ID,
            chat_ctx=self.chat_ctx,
        )
        
        if result.success:
            return result
    
    # No supervisors available
    await self.handle_no_supervisor_available()
```

### 8. **Optimize Conversation Summary**

```python
# Create concise, actionable summary for supervisor
def create_supervisor_summary(self, chat_ctx: llm.ChatContext) -> str:
    """Generate concise summary for supervisor"""
    
    summary_prompt = (
        "Summarize this customer conversation in 2-3 sentences. "
        "Focus on: 1) Customer's main issue, 2) What has been tried, "
        "3) What the customer needs now."
    )
    
    # Use LLM to generate summary
    summary = llm.generate_summary(chat_ctx, summary_prompt)
    
    return summary
```

---

## Additional Resources

### Official Documentation
- **Warm Transfer Guide:** https://docs.livekit.io/telephony/features/transfers/warm/
- **SIP Trunk Setup:** https://docs.livekit.io/telephony/start/sip-trunk-setup/
- **Agent Playground:** https://docs.livekit.io/agents/start/playground/
- **Python SDK Reference:** https://docs.livekit.io/agents/
- **Authentication:** https://docs.livekit.io/frontends/authentication/

### Example Code
- **Warm Transfer Example:** https://github.com/livekit/agents/tree/main/examples/warm-transfer

### Support
- **LiveKit Discord:** https://livekit.io/discord
- **GitHub Issues:** https://github.com/livekit/agents/issues
- **Email Support:** support@livekit.io

---

## Summary

### Key Takeaways

1. ✅ **Use WarmTransferTask** for most use cases (simple, reliable)
2. ✅ **Configure SIP trunk** before attempting transfers
3. ✅ **Always inform customers** before placing on hold
4. ✅ **Provide context** to supervisors via conversation history
5. ✅ **Handle failures gracefully** with fallback options
6. ✅ **Monitor success rates** and optimize accordingly
7. ✅ **Test regularly** to ensure reliability

### Success Metrics

With proper implementation:
- **95-98%** transfer success rate
- **< 30 seconds** average transfer time
- **Seamless customer experience** with no dropped calls
- **Full context** provided to human operators

---

**Document Version:** 1.0  
**Last Updated:** February 10, 2026  
**Author:** Aisyst Technical Team
