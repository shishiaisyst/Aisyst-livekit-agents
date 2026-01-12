"""
Tests for the restaurant voice agent behavior.
"""

import pytest
from livekit.agents import AgentSession
from livekit.plugins import openai

from agents.restaurant_agent import RestaurantAgent


@pytest.fixture
def llm():
    """LLM instance for test validation."""
    return openai.LLM(model="gpt-4-turbo-preview")


@pytest.mark.asyncio
async def test_agent_greeting(llm):
    """Test that the agent greets the user appropriately."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Test greeting
    result = await session.run(user_input="Hello")
    
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Offers a friendly greeting and asks how they can help with ordering food"
    )


@pytest.mark.asyncio
async def test_menu_search(llm):
    """Test that the agent can search the menu."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Test menu search
    result = await session.run(user_input="What burgers do you have?")
    
    # Should call search_menu function
    result.expect.contains_function_call(name="search_menu")
    
    # Should respond with burger options
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Lists available burger options with descriptions and prices"
    )


@pytest.mark.asyncio
async def test_add_item_to_order(llm):
    """Test adding an item to the order."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Add item to order
    result = await session.run(user_input="I'd like a Classic Cheeseburger")
    
    # Should call add_item_to_order function
    result.expect.contains_function_call(name="add_item_to_order")
    
    # Should confirm the addition
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Confirms the burger was added to the order and mentions the price"
    )


@pytest.mark.asyncio
async def test_order_summary(llm):
    """Test getting an order summary."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Add item
    await session.run(user_input="Add a Classic Cheeseburger")
    
    # Get summary
    result = await session.run(user_input="What's in my order?")
    
    # Should call get_order_summary
    result.expect.contains_function_call(name="get_order_summary")
    
    # Should list the order
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Provides a summary of the order including items and total price"
    )


@pytest.mark.asyncio
async def test_dietary_restrictions(llm):
    """Test searching for items with dietary restrictions."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Search for vegan options
    result = await session.run(user_input="Do you have any vegan options?")
    
    # Should search menu with dietary filter
    result.expect.contains_function_call(name="search_menu")
    
    # Should list vegan items
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Lists available vegan menu items"
    )


@pytest.mark.asyncio
async def test_order_modification(llm):
    """Test modifying an order."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # Add item
    await session.run(user_input="Add a burger")
    
    # Remove item
    result = await session.run(user_input="Actually, remove that")
    
    # Should call remove_item_from_order
    result.expect.contains_function_call(name="remove_item_from_order")
    
    # Should confirm removal
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Confirms the item was removed from the order"
    )


@pytest.mark.asyncio
async def test_complete_order_flow(llm):
    """Test the complete order flow from start to payment."""
    agent = RestaurantAgent()
    session = AgentSession(
        stt="text-only",
        llm="openai/gpt-4-turbo-preview",
        tts="text-only",
    )
    
    await session.start(agent)
    
    # 1. Search menu
    await session.run(user_input="What burgers do you have?")
    
    # 2. Add item
    await session.run(user_input="I'll take a Classic Cheeseburger")
    
    # 3. Add another item
    await session.run(user_input="And some fries")
    
    # 4. Get summary
    await session.run(user_input="What's my total?")
    
    # 5. Complete order
    result = await session.run(user_input="I'm ready to complete my order. My phone is +15551234567")
    
    # Should call complete_order
    result.expect.contains_function_call(name="complete_order")
    
    # Should confirm order and mention payment link
    await result.expect.next_event().is_message(role="assistant").judge(
        llm,
        intent="Confirms the order was completed and payment link was sent via SMS"
    )
