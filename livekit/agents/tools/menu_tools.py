"""
Menu-related function tools for the agent.
"""

from typing import Optional, List, Dict, Any
from livekit.agents import function_tool, RunContext

from agents.config.menu_data import get_restaurant_menu
from agents.models.menu import DietaryRestriction


# Load menu once at module level
RESTAURANT_MENU = get_restaurant_menu()


@function_tool()
async def search_menu(
    context: RunContext,
    query: Optional[str] = None,
    category: Optional[str] = None,
    dietary_restriction: Optional[str] = None,
    max_price: Optional[float] = None,
) -> str:
    """Search for menu items based on various criteria.
    
    Args:
        query: Search term for item name or description (e.g., "burger", "chicken")
        category: Filter by category name (e.g., "appetizers", "entrees", "desserts")
        dietary_restriction: Filter by dietary need (e.g., "vegetarian", "vegan", "gluten_free")
        max_price: Maximum price in dollars
        
    Returns:
        Formatted list of matching menu items with prices and descriptions
    """
    try:
        # Convert dietary restriction string to enum if provided
        diet_enum = None
        if dietary_restriction:
            try:
                diet_enum = DietaryRestriction(dietary_restriction.lower().replace(" ", "_"))
            except ValueError:
                return f"Invalid dietary restriction. Available options: {', '.join([d.value for d in DietaryRestriction])}"
        
        # Search menu
        results = RESTAURANT_MENU.search_items(
            query=query or "",
            category=category,
            dietary_restriction=diet_enum,
            max_price=max_price,
        )
        
        if not results:
            return "No menu items found matching your criteria. Please try different search terms."
        
        # Format results for speech
        response = f"I found {len(results)} item{'s' if len(results) != 1 else ''} for you:\n\n"
        
        for item in results[:10]:  # Limit to 10 results for speech
            response += f"- {item.name} (${item.price:.2f}): {item.description}\n"
            
            if item.dietary_restrictions:
                restrictions = ", ".join([r.value.replace("_", " ") for r in item.dietary_restrictions])
                response += f"  ({restrictions})\n"
        
        if len(results) > 10:
            response += f"\n...and {len(results) - 10} more items. Would you like me to narrow down the search?"
        
        return response
    
    except Exception as e:
        return f"Sorry, I encountered an error searching the menu: {str(e)}"


@function_tool()
async def get_menu_item_details(
    context: RunContext,
    item_name: str,
) -> str:
    """Get detailed information about a specific menu item.
    
    Args:
        item_name: Name of the menu item to get details for
        
    Returns:
        Detailed information including price, description, calories, dietary info, and customization options
    """
    try:
        # Search for the item
        results = RESTAURANT_MENU.search_items(query=item_name)
        
        if not results:
            return f"Sorry, I couldn't find '{item_name}' on our menu. Would you like me to search for something similar?"
        
        # Use the first match
        item = results[0]
        
        # Build detailed response
        response = f"{item.name} - ${item.price:.2f}\n\n"
        response += f"{item.description}\n\n"
        
        if item.calories:
            response += f"Calories: {item.calories}\n"
        
        if item.prep_time:
            response += f"Preparation time: approximately {item.prep_time} minutes\n"
        
        if item.dietary_restrictions:
            restrictions = ", ".join([r.value.replace("_", " ").title() for r in item.dietary_restrictions])
            response += f"Dietary: {restrictions}\n"
        
        if item.allergens:
            response += f"Contains allergens: {', '.join(item.allergens)}\n"
        
        if item.customizable and item.customization_options:
            response += "\nCustomization options:\n"
            for option_name, choices in item.customization_options.items():
                response += f"  {option_name.title()}: {', '.join(choices)}\n"
        
        if not item.available:
            response += "\nNote: This item is currently unavailable.\n"
        
        return response
    
    except Exception as e:
        return f"Sorry, I encountered an error getting item details: {str(e)}"


@function_tool()
async def list_menu_categories(
    context: RunContext,
) -> str:
    """List all available menu categories.
    
    Returns:
        List of menu categories with brief descriptions
    """
    try:
        response = "Here are our menu categories:\n\n"
        
        for category in sorted(RESTAURANT_MENU.categories, key=lambda c: c.display_order):
            item_count = len(category.get_available_items())
            response += f"- {category.name} ({item_count} items)"
            if category.description:
                response += f": {category.description}"
            response += "\n"
        
        response += "\nWhich category would you like to explore?"
        
        return response
    
    except Exception as e:
        return f"Sorry, I encountered an error listing categories: {str(e)}"
