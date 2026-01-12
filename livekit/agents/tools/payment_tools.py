"""
Payment and SMS notification function tools for the agent.
"""

from typing import Optional
from livekit.agents import function_tool, RunContext, ToolError

from agents.models.order import OrderStatus
from agents.tools.order_tools import get_current_order
from twilio.sms_client import TwilioSMSClient
from stripe.payment_client import StripePaymentClient
from monitoring.logger import get_logger

logger = get_logger(__name__)

# Initialize clients (will be created on first use)
_twilio_client: Optional[TwilioSMSClient] = None
_stripe_client: Optional[StripePaymentClient] = None


def get_twilio_client() -> TwilioSMSClient:
    """Get or create Twilio SMS client."""
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioSMSClient()
    return _twilio_client


def get_stripe_client() -> StripePaymentClient:
    """Get or create Stripe payment client."""
    global _stripe_client
    if _stripe_client is None:
        _stripe_client = StripePaymentClient()
    return _stripe_client


@function_tool()
async def complete_order(
    context: RunContext,
    customer_phone: str,
    customer_name: Optional[str] = None,
    order_type: str = "pickup",
) -> str:
    """Complete the order and send payment link and confirmation via SMS.
    
    Args:
        customer_phone: Customer's phone number for SMS (format: +1234567890)
        customer_name: Customer's name (optional)
        order_type: Type of order - "pickup", "delivery", or "dine-in" (default: pickup)
        
    Returns:
        Confirmation message indicating the order was completed and SMS sent
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            raise ToolError("Cannot complete an empty order. Please add items first.")
        
        # Validate phone number format
        if not customer_phone.startswith("+"):
            raise ToolError("Phone number must include country code (e.g., +1234567890)")
        
        # Update order with customer information
        order.customer_phone = customer_phone
        order.customer_name = customer_name
        order.order_type = order_type
        order.status = OrderStatus.CONFIRMED
        
        logger.info(
            f"Completing order {order.order_id}",
            extra={
                "order_id": order.order_id,
                "customer_phone": customer_phone,
                "total": order.total,
                "item_count": len(order.items),
            }
        )
        
        # Generate payment link
        stripe_client = get_stripe_client()
        payment_link = await stripe_client.create_payment_link(
            amount=int(order.total * 100),  # Convert to cents
            order_id=order.order_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
        )
        
        order.payment_link = payment_link
        
        # Send order confirmation and payment link via SMS
        twilio_client = get_twilio_client()
        await twilio_client.send_order_confirmation(
            to=customer_phone,
            order_id=order.order_id,
            total=order.total,
            payment_link=payment_link,
            order_type=order_type,
        )
        
        logger.info(
            f"Order {order.order_id} completed successfully",
            extra={
                "order_id": order.order_id,
                "payment_link_sent": True,
                "sms_sent": True,
            }
        )
        
        response = f"Perfect! Your order #{order.order_id} for ${order.total:.2f} has been confirmed. "
        response += f"I've sent a secure payment link to {customer_phone}. "
        response += f"Once payment is complete, your order will be prepared and ready for {order_type} "
        response += "in approximately 20-30 minutes. Thank you!"
        
        return response
    
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error completing order: {e}", exc_info=True)
        raise ToolError(f"Sorry, I encountered an error completing your order: {str(e)}")


@function_tool()
async def send_payment_link(
    context: RunContext,
    customer_phone: str,
) -> str:
    """Send a payment link to the customer via SMS.
    
    Args:
        customer_phone: Customer's phone number (format: +1234567890)
        
    Returns:
        Confirmation message
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            raise ToolError("Cannot send payment link for an empty order.")
        
        if not customer_phone.startswith("+"):
            raise ToolError("Phone number must include country code (e.g., +1234567890)")
        
        # Generate payment link
        stripe_client = get_stripe_client()
        payment_link = await stripe_client.create_payment_link(
            amount=int(order.total * 100),
            order_id=order.order_id,
            customer_phone=customer_phone,
        )
        
        order.payment_link = payment_link
        order.customer_phone = customer_phone
        
        # Send SMS with payment link
        twilio_client = get_twilio_client()
        await twilio_client.send_payment_link(
            to=customer_phone,
            order_id=order.order_id,
            payment_link=payment_link,
            amount=order.total,
        )
        
        logger.info(
            f"Payment link sent for order {order.order_id}",
            extra={"order_id": order.order_id, "customer_phone": customer_phone}
        )
        
        return f"I've sent the payment link to {customer_phone}. Please check your messages."
    
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error sending payment link: {e}", exc_info=True)
        raise ToolError(f"Sorry, I encountered an error sending the payment link: {str(e)}")


@function_tool()
async def send_order_confirmation(
    context: RunContext,
    customer_phone: str,
) -> str:
    """Send an order confirmation via SMS without payment link.
    
    Args:
        customer_phone: Customer's phone number (format: +1234567890)
        
    Returns:
        Confirmation message
    """
    try:
        order = get_current_order(context)
        
        if not order.items:
            raise ToolError("Cannot send confirmation for an empty order.")
        
        if not customer_phone.startswith("+"):
            raise ToolError("Phone number must include country code (e.g., +1234567890)")
        
        order.customer_phone = customer_phone
        
        # Send SMS confirmation
        twilio_client = get_twilio_client()
        await twilio_client.send_order_confirmation(
            to=customer_phone,
            order_id=order.order_id,
            total=order.total,
            order_type=order.order_type,
        )
        
        logger.info(
            f"Order confirmation sent for {order.order_id}",
            extra={"order_id": order.order_id, "customer_phone": customer_phone}
        )
        
        return f"I've sent an order confirmation to {customer_phone}."
    
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error sending confirmation: {e}", exc_info=True)
        raise ToolError(f"Sorry, I encountered an error sending the confirmation: {str(e)}")
