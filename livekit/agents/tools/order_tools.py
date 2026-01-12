"""
Order management function tools for the agent.
"""

from typing import Optional, Dict
from livekit.agents import function_tool, RunContext

from agents.models.order import Order
from agents.config.menu_data import get_restaurant_menu
from monitoring.logger import get_logger

logger = get_logger(__name__)

# Load menu once at module level
RESTAURANT_MENU = get_restaurant_menu()


def get_current_order(context: RunContext) -> Order:
    """Get or create the current order from session context."""
    if not hasattr(context, "order") or context.order is None:
        context.order = Order()
        logger.info(f"Created new order: {context.order.order_id}")
    return context.order


@function_tool()
async def add_item_to_order(
    context: RunContext,
    item_name: str,
    quantity: int = 1,
    customizations: Optional[Dict[str, str]] = None,
    special_instructions: Optional[str] = None,
) -> str:
    """Add an item to the current order.
    
    Args:
        item_name: Name of the menu item to add
        quantity: Number of this item to add (default: 1)
        customizations: Dict of customization options (e.g., {"temperature": "Medium", "cheese": "Cheddar"})
        special_instructions: Any special preparation instructions
        
    Returns:
        Confirmation message with updated order total
    """
    try:
        order = get_current_order(context)
        
        # Find the menu item
        results = RESTAURANT_MENU.search_items(query=item_name)
        
        if not results:
            return f"Sorry, I couldn't find '{item_name}' on our menu. Could you try another item?"
        
        menu_item = results[0]
        
        # Check if item is available
        if not menu_item.available:
            return f"Sorry, {menu_item.name} is currently unavailable. Would you like to try something else?"
        
        # Validate customizations if provided
        if customizations and menu_item.customizable:
            invalid_options = []
            for key, value in customizations.items():
                if key not in menu_item.customization_options:
                    invalid_options.append(key)
                elif value not in menu_item.customization_options[key]:
                    invalid_options.append(f"{key}={value}")
            
            if invalid_options:
                return f"Invalid customization options: {', '.join(invalid_options)}. Please check available options."
        
        # Add item to order
        order.add_item(
            menu_item_id=menu_item.id,
            name=menu_item.name,
            quantity=quantity,
            unit_price=menu_item.price,
            customizations=customizations or {},
            special_instructions=special_instructions,
        )
        
        logger.info(
            f"Added to order {order.order_id}: {quantity}x {menu_item.name}",
            extra={"order_id": order.order_id, "item": menu_item.name, "quantity": quantity}
        )
        
        # Build confirmation message
        response = f"Added {quantity} {menu_item.name}"
        if quantity > 1:
            response += "s"
        response += f" to your order"
        
        if customizations:
            custom_str = ", ".join([f"{k}: {v}" for k, v in customizations.items()])
            response += f" with {custom_str}"
        
        if special_instructions:
            response += f" (Note: {special_instructions})"
        
        response += f". Your current subtotal is ${order.subtotal:.2f}."
        
        return response
    
    except Exception as e:
        logger.error(f"Error adding item to order: {e}", exc_info=True)
        return f"Sorry, I encountered an error adding that item: {str(e)}"


@function_tool()
async def remove_item_from_order(
    context: RunContext,
    item_index: int,
) -> str:
    """Remove an item from the current order.
    
    Args:
        item_index: The position of the item in the order (1-indexed, shown in order summary)
        
    Returns:
        Confirmation message with updated order total
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            return "Your order is currently empty. There's nothing to remove."
        
        # Convert to 0-indexed
        index = item_index - 1
        
        if index < 0 or index >= len(order.items):
            return f"Invalid item number. Please choose a number between 1 and {len(order.items)}."
        
        # Get item name before removing
        removed_item = order.items[index]
        item_name = removed_item.name
        
        # Remove the item
        order.remove_item(index)
        
        logger.info(
            f"Removed from order {order.order_id}: {item_name}",
            extra={"order_id": order.order_id, "item": item_name}
        )
        
        response = f"I've removed the {item_name} from your order."
        
        if order.items:
            response += f" Your new subtotal is ${order.subtotal:.2f}."
        else:
            response += " Your order is now empty."
        
        return response
    
    except Exception as e:
        logger.error(f"Error removing item from order: {e}", exc_info=True)
        return f"Sorry, I encountered an error removing that item: {str(e)}"


@function_tool()
async def update_item_quantity(
    context: RunContext,
    item_index: int,
    new_quantity: int,
) -> str:
    """Update the quantity of an item in the order.
    
    Args:
        item_index: The position of the item in the order (1-indexed)
        new_quantity: The new quantity for this item
        
    Returns:
        Confirmation message with updated order total
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            return "Your order is currently empty. There's nothing to update."
        
        # Convert to 0-indexed
        index = item_index - 1
        
        if index < 0 or index >= len(order.items):
            return f"Invalid item number. Please choose a number between 1 and {len(order.items)}."
        
        if new_quantity < 1:
            return "Quantity must be at least 1. To remove an item, use the remove_item_from_order function."
        
        item = order.items[index]
        old_quantity = item.quantity
        
        # Update quantity
        order.update_item_quantity(index, new_quantity)
        
        logger.info(
            f"Updated quantity in order {order.order_id}: {item.name} from {old_quantity} to {new_quantity}",
            extra={"order_id": order.order_id, "item": item.name}
        )
        
        response = f"Updated {item.name} quantity from {old_quantity} to {new_quantity}. "
        response += f"Your new subtotal is ${order.subtotal:.2f}."
        
        return response
    
    except Exception as e:
        logger.error(f"Error updating item quantity: {e}", exc_info=True)
        return f"Sorry, I encountered an error updating that quantity: {str(e)}"


@function_tool()
async def get_order_summary(
    context: RunContext,
) -> str:
    """Get a summary of the current order with all items and total.
    
    Returns:
        Formatted order summary with items, quantities, prices, and total
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            return "Your order is currently empty. What would you like to add?"
        
        return order.to_speech_summary()
    
    except Exception as e:
        logger.error(f"Error getting order summary: {e}", exc_info=True)
        return f"Sorry, I encountered an error getting your order summary: {str(e)}"


@function_tool()
async def clear_order(
    context: RunContext,
) -> str:
    """Clear all items from the current order.
    
    Returns:
        Confirmation message
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            return "Your order is already empty."
        
        item_count = len(order.items)
        order.clear_items()
        
        logger.info(
            f"Cleared order {order.order_id}: removed {item_count} items",
            extra={"order_id": order.order_id}
        )
        
        return f"I've cleared all {item_count} item{'s' if item_count != 1 else ''} from your order. Would you like to start fresh?"
    
    except Exception as e:
        logger.error(f"Error clearing order: {e}", exc_info=True)
        return f"Sorry, I encountered an error clearing your order: {str(e)}"
