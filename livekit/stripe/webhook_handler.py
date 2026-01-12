"""
Webhook handler for Stripe payment events.
"""

import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
import stripe
from stripe.error import SignatureVerificationError

from monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks/stripe", tags=["stripe"])

# Get webhook secret from environment
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/payment")
async def handle_payment_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
) -> Dict[str, str]:
    """
    Handle Stripe payment webhook events.
    
    Stripe sends events for:
    - payment_intent.succeeded: Payment was successful
    - payment_intent.payment_failed: Payment failed
    - charge.refunded: Charge was refunded
    - checkout.session.completed: Checkout session completed
    """
    try:
        # Get raw request body
        payload = await request.body()
        
        # Verify webhook signature if secret is configured
        if WEBHOOK_SECRET and stripe_signature:
            try:
                event = stripe.Webhook.construct_event(
                    payload, stripe_signature, WEBHOOK_SECRET
                )
            except SignatureVerificationError as e:
                logger.error(f"Invalid webhook signature: {e}")
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            # Parse event without signature verification (not recommended for production)
            event = stripe.Event.construct_from(
                stripe.util.convert_to_dict(payload), stripe.api_key
            )
        
        event_type = event.type
        event_data = event.data.object
        
        logger.info(
            f"Stripe webhook received",
            extra={
                "event_type": event_type,
                "event_id": event.id,
            }
        )
        
        # Handle different event types
        if event_type == "payment_intent.succeeded":
            await handle_payment_succeeded(event_data)
        
        elif event_type == "payment_intent.payment_failed":
            await handle_payment_failed(event_data)
        
        elif event_type == "charge.refunded":
            await handle_charge_refunded(event_data)
        
        elif event_type == "checkout.session.completed":
            await handle_checkout_completed(event_data)
        
        elif event_type == "payment_link.created":
            logger.info(f"Payment link created: {event_data.get('id')}")
        
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        return {"status": "success"}
    
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def handle_payment_succeeded(payment_intent: Dict[str, Any]) -> None:
    """Handle successful payment event."""
    order_id = payment_intent.get("metadata", {}).get("order_id")
    amount = payment_intent.get("amount")
    payment_id = payment_intent.get("id")
    
    logger.info(
        f"Payment succeeded",
        extra={
            "order_id": order_id,
            "payment_id": payment_id,
            "amount": amount,
        }
    )
    
    # TODO: Update order status in database
    # TODO: Send confirmation SMS to customer
    # TODO: Notify restaurant staff
    
    # For now, just log
    logger.info(f"Order {order_id} paid: ${amount/100:.2f}")


async def handle_payment_failed(payment_intent: Dict[str, Any]) -> None:
    """Handle failed payment event."""
    order_id = payment_intent.get("metadata", {}).get("order_id")
    payment_id = payment_intent.get("id")
    error_message = payment_intent.get("last_payment_error", {}).get("message")
    
    logger.error(
        f"Payment failed",
        extra={
            "order_id": order_id,
            "payment_id": payment_id,
            "error": error_message,
        }
    )
    
    # TODO: Notify customer of payment failure
    # TODO: Update order status
    # TODO: Implement retry logic or alternative payment method


async def handle_charge_refunded(charge: Dict[str, Any]) -> None:
    """Handle refund event."""
    charge_id = charge.get("id")
    amount_refunded = charge.get("amount_refunded")
    metadata = charge.get("metadata", {})
    order_id = metadata.get("order_id")
    
    logger.info(
        f"Charge refunded",
        extra={
            "charge_id": charge_id,
            "order_id": order_id,
            "amount_refunded": amount_refunded,
        }
    )
    
    # TODO: Update order status
    # TODO: Notify customer of refund


async def handle_checkout_completed(session: Dict[str, Any]) -> None:
    """Handle completed checkout session."""
    session_id = session.get("id")
    order_id = session.get("metadata", {}).get("order_id")
    amount_total = session.get("amount_total")
    customer_email = session.get("customer_details", {}).get("email")
    
    logger.info(
        f"Checkout session completed",
        extra={
            "session_id": session_id,
            "order_id": order_id,
            "amount": amount_total,
            "customer_email": customer_email,
        }
    )
    
    # TODO: Mark order as paid
    # TODO: Send receipt to customer
