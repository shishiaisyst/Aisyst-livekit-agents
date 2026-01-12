"""
Pytest configuration and fixtures.
"""

import pytest
import os
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(".env.local")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment."""
    # Ensure we're in test mode
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    yield
    
    # Cleanup after tests


@pytest.fixture
def mock_order():
    """Create a mock order for testing."""
    from agents.models.order import Order, OrderItem
    
    order = Order()
    order.add_item(
        menu_item_id="burg-001",
        name="Classic Cheeseburger",
        quantity=1,
        unit_price=12.99,
    )
    
    return order


@pytest.fixture
def mock_menu():
    """Get the restaurant menu for testing."""
    from agents.config.menu_data import get_restaurant_menu
    return get_restaurant_menu()
