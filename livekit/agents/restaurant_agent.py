"""
Main restaurant voice agent implementation using LiveKit Agents framework.
"""

import os
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, AgentServer, RunContext, room_io
from livekit.plugins import openai, deepgram, cartesia, silero, noise_cancellation, turn_detector

from agents.config import AGENT_INSTRUCTIONS, GREETING_INSTRUCTIONS
from agents.tools import (
    search_menu,
    get_menu_item_details,
    list_menu_categories,
    add_item_to_order,
    remove_item_from_order,
    get_order_summary,
    clear_order,
    update_item_quantity,
    complete_order,
    send_payment_link,
    send_order_confirmation,
)
from monitoring.logger import get_logger, setup_logging
from monitoring.metrics import get_metrics_collector, Metrics

# Load environment variables
load_dotenv(".env.local")

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Initialize metrics
metrics = get_metrics_collector()


class RestaurantAgent(Agent):
    """Restaurant order-taking voice agent."""
    
    def __init__(self):
        """Initialize the restaurant agent with instructions and tools."""
        super().__init__(
            instructions=AGENT_INSTRUCTIONS,
            tools=[
                # Menu tools
                search_menu,
                get_menu_item_details,
                list_menu_categories,
                # Order management tools
                add_item_to_order,
                remove_item_from_order,
                get_order_summary,
                clear_order,
                update_item_quantity,
                # Payment and SMS tools
                complete_order,
                send_payment_link,
                send_order_confirmation,
            ],
        )
        
        logger.info("Restaurant agent initialized")
    
    async def on_enter(self, context: RunContext) -> None:
        """
        Called when the agent enters the room.
        Generate a greeting for the customer.
        """
        logger.info(
            "Agent entered room",
            extra={"room_id": context.room.name if context.room else None}
        )
        
        metrics.increment_counter(Metrics.CALLS_TOTAL)
        metrics.increment_counter(Metrics.CALLS_ACTIVE)
        
        # Generate welcome greeting
        await context.session.generate_reply(
            instructions=GREETING_INSTRUCTIONS
        )
    
    async def on_exit(self, context: RunContext) -> None:
        """Called when the agent exits the room."""
        logger.info(
            "Agent exiting room",
            extra={"room_id": context.room.name if context.room else None}
        )
        
        metrics.increment_counter(Metrics.CALLS_ACTIVE, -1)
    
    async def on_tool_call(self, context: RunContext, tool_name: str, args: dict) -> None:
        """Called before a tool is executed."""
        logger.info(
            f"Tool called: {tool_name}",
            extra={"tool": tool_name, "args": args}
        )
        
        metrics.increment_counter(Metrics.TOOL_CALLS, labels={"tool": tool_name})
    
    async def on_error(self, context: RunContext, error: Exception) -> None:
        """Called when an error occurs."""
        logger.error(
            f"Agent error: {error}",
            exc_info=True,
            extra={"error_type": type(error).__name__}
        )
        
        metrics.increment_counter(Metrics.AGENT_ERRORS, labels={"error_type": type(error).__name__})


# Create agent server
server = AgentServer()


@server.rtc_session()
async def restaurant_order_agent(ctx: agents.JobContext):
    """
    Main entrypoint for the restaurant voice agent.
    
    This function is called when a new call/session is initiated.
    """
    logger.info(
        "New agent session starting",
        extra={
            "job_id": ctx.job.id,
            "room": ctx.room.name,
        }
    )
    
    # Track call start time
    metrics.start_timer(f"call_{ctx.job.id}")
    
    try:
        # Create agent session with STT-LLM-TTS pipeline
        session = AgentSession(
            # Speech-to-Text (Deepgram)
            stt=deepgram.STT(
                model="nova-2-general",
                language="en-US",
            ),
            
            # Large Language Model (OpenAI)
            llm=openai.LLM(
                model="gpt-4-turbo-preview",
                temperature=0.7,
            ),
            
            # Text-to-Speech (Cartesia)
            tts=cartesia.TTS(
                voice=os.getenv("TTS_VOICE_ID", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
                speed=float(os.getenv("TTS_SPEED", "1.0")),
            ),
            
            # Voice Activity Detection (Silero)
            vad=silero.VAD.load(),
            
            # Turn Detection (LiveKit Multilingual)
            turn_detection=turn_detector.MultilingualModel(),
        )
        
        # Start the agent session
        await session.start(
            room=ctx.room,
            agent=RestaurantAgent(),
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # Enable background voice cancellation for noisy restaurant environments
                    noise_cancellation=lambda params: (
                        noise_cancellation.BVCTelephony()
                        if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                        else noise_cancellation.BVC()
                    ),
                ),
            ),
        )
        
        logger.info(
            "Agent session started successfully",
            extra={"job_id": ctx.job.id}
        )
        
    except Exception as e:
        logger.error(
            f"Failed to start agent session: {e}",
            exc_info=True,
            extra={"job_id": ctx.job.id}
        )
        metrics.increment_counter(Metrics.AGENT_ERRORS, labels={"error_type": "session_start"})
        raise
    
    finally:
        # Record call duration
        duration = metrics.stop_timer(f"call_{ctx.job.id}")
        metrics.record_histogram(Metrics.CALL_DURATION, duration)
        
        logger.info(
            "Agent session ended",
            extra={
                "job_id": ctx.job.id,
                "duration": duration,
            }
        )


if __name__ == "__main__":
    """
    Run the agent server.
    
    Usage:
        # Console mode (local testing)
        python agents/restaurant_agent.py console
        
        # Development mode (connect to LiveKit Cloud)
        python agents/restaurant_agent.py dev
        
        # Production mode
        python agents/restaurant_agent.py start
        
        # Download model files
        python agents/restaurant_agent.py download-files
    """
    logger.info("Starting restaurant voice agent")
    agents.cli.run_app(server)
