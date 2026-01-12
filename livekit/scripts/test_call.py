#!/usr/bin/env python3
"""
Script to make a test call to the agent using LiveKit API.
"""

import asyncio
import argparse
import os
from livekit import api


async def make_test_call(phone_number: str, agent_name: str = "restaurant-order-agent"):
    """
    Make a test outbound call to the specified phone number.
    
    Args:
        phone_number: Phone number to call (E.164 format: +1234567890)
        agent_name: Name of the agent to dispatch
    """
    # Get LiveKit credentials from environment
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not all([livekit_url, api_key, api_secret]):
        raise ValueError("Missing LiveKit credentials in environment variables")
    
    # Create LiveKit API client
    lkapi = api.LiveKitAPI(livekit_url, api_key, api_secret)
    
    # Create a room for this call
    room_name = f"test-call-{phone_number.replace('+', '')}"
    
    print(f"Creating room: {room_name}")
    room = await lkapi.room.create_room(
        api.CreateRoomRequest(name=room_name)
    )
    print(f"Room created: {room.name}")
    
    # Create agent dispatch
    print(f"Dispatching agent: {agent_name}")
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            room=room_name,
            agent_name=agent_name,
        )
    )
    print(f"Agent dispatched: {dispatch.id}")
    
    # Create SIP participant (make the call)
    print(f"Calling {phone_number}...")
    sip_participant = await lkapi.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=os.getenv("SIP_TRUNK_ID"),  # You'll need to configure this
            sip_call_to=phone_number,
            participant_identity=f"caller-{phone_number.replace('+', '')}",
        )
    )
    
    print(f"\n✅ Test call initiated!")
    print(f"   Room: {room_name}")
    print(f"   Phone: {phone_number}")
    print(f"   Participant: {sip_participant.participant_identity}")
    print(f"\nThe agent should answer and greet the caller.")
    print(f"Monitor the call in LiveKit dashboard: {livekit_url}/projects/p_/sessions")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Make a test call to the voice agent")
    parser.add_argument(
        "--phone",
        required=True,
        help="Phone number to call (E.164 format: +1234567890)"
    )
    parser.add_argument(
        "--agent",
        default="restaurant-order-agent",
        help="Agent name (default: restaurant-order-agent)"
    )
    
    args = parser.parse_args()
    
    # Validate phone number format
    if not args.phone.startswith("+"):
        print("Error: Phone number must be in E.164 format (e.g., +1234567890)")
        return 1
    
    try:
        asyncio.run(make_test_call(args.phone, args.agent))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
