"""
SMS message templates for Twilio notifications.
"""

import os
from typing import Optional

RESTAURANT_NAME = os.getenv("RESTAURANT_NAME", "Our Restaurant")
RESTAURANT_PHONE = os.getenv("RESTAURANT_PHONE", "")


def format_order_confirmation(
    order_id: str,
    total: float,
    payment_link: Optional[str] = None,
    order_type: str = "pickup",
) -> str:
    """
    Format an order confirmation message.
    
    Args:
        order_id: Order ID
        total: Order total
        payment_link: Optional payment link
        order_type: Order type (pickup, delivery, dine-in)
        
    Returns:
        Formatted SMS message
    """
    message = f"✅ {RESTAURANT_NAME}\n\n"
    message += f"Order #{order_id} confirmed!\n"
    message += f"Total: ${total:.2f}\n"
    message += f"Type: {order_type.title()}\n\n"
    
    if payment_link:
        message += f"💳 Pay securely:\n{payment_link}\n\n"
    
    message += f"⏱️ Ready in 20-30 mins\n"
    
    if RESTAURANT_PHONE:
        message += f"\nQuestions? Call {RESTAURANT_PHONE}"
    
    return message


def format_payment_link_message(
    order_id: str,
    payment_link: str,
    amount: float,
) -> str:
    """
    Format a payment link message.
    
    Args:
        order_id: Order ID
        payment_link: Stripe payment link
        amount: Payment amount
        
    Returns:
        Formatted SMS message
    """
    message = f"💳 {RESTAURANT_NAME}\n\n"
    message += f"Payment for Order #{order_id}\n"
    message += f"Amount: ${amount:.2f}\n\n"
    message += f"Click to pay securely:\n{payment_link}\n\n"
    message += "Your order will be prepared after payment."
    
    return message


def format_order_status_update(
    order_id: str,
    status: str,
    estimated_time: Optional[int] = None,
) -> str:
    """
    Format an order status update message.
    
    Args:
        order_id: Order ID
        status: New order status
        estimated_time: Estimated time in minutes
        
    Returns:
        Formatted SMS message
    """
    status_emoji = {
        "confirmed": "✅",
        "preparing": "👨‍🍳",
        "ready": "🎉",
        "completed": "✨",
        "cancelled": "❌",
    }
    
    emoji = status_emoji.get(status.lower(), "ℹ️")
    
    message = f"{emoji} {RESTAURANT_NAME}\n\n"
    message += f"Order #{order_id}\n"
    message += f"Status: {status.title()}\n"
    
    if estimated_time:
        message += f"\n⏱️ Ready in {estimated_time} minutes"
    
    if status.lower() == "ready":
        message += "\n\nYour order is ready for pickup!"
    elif status.lower() == "preparing":
        message += "\n\nYour order is being prepared."
    
    return message


def format_payment_receipt(
    order_id: str,
    total: float,
    payment_method: str = "card",
) -> str:
    """
    Format a payment receipt message.
    
    Args:
        order_id: Order ID
        total: Total paid
        payment_method: Payment method used
        
    Returns:
        Formatted SMS message
    """
    message = f"✅ {RESTAURANT_NAME}\n\n"
    message += f"Payment Received\n"
    message += f"Order #{order_id}\n"
    message += f"Amount: ${total:.2f}\n"
    message += f"Method: {payment_method.title()}\n\n"
    message += "Thank you! Your order is being prepared."
    
    return message
