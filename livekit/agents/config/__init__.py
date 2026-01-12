"""
Configuration module for the restaurant voice agent.
"""

from agents.config.prompts import AGENT_INSTRUCTIONS, GREETING_INSTRUCTIONS
from agents.config.menu_data import get_restaurant_menu

__all__ = [
    "AGENT_INSTRUCTIONS",
    "GREETING_INSTRUCTIONS",
    "get_restaurant_menu",
]
