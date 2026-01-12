"""
Stripe payment client for generating payment links and handling payments.
"""

import os
from typing import Optional, Dict, Any
import stripe
from stripe.error import StripeError

from stripe.models import PaymentLinkResult
from monitoring.logger import get_logger

logger = get_logger(__name__)


class StripePaymentClient:
    """Client for creating payment links and managing payments via Stripe."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ):
        """
        Initialize Stripe payment client.
        
        Args:
            api_key: Stripe API key (defaults to STRIPE_API_KEY env var)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
        """
        self.api_key = api_key or os.getenv("STRIPE_API_KEY")
        self.success_url = success_url or os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success")
        self.cancel_url = cancel_url or os.getenv("STRIPE_CANCEL_URL", "https://example.com/cancel")
        
        if not self.api_key:
            raise ValueError(
                "Stripe API key not configured. Set STRIPE_API_KEY environment variable."
            )
        
        stripe.api_key = self.api_key
        logger.info("Stripe payment client initialized")
    
    async def create_payment_link(
        self,
        amount: int,
        order_id: str,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """
        Create a Stripe payment link for an order.
        
        Args:
            amount: Amount in cents (e.g., 1000 for $10.00)
            order_id: Order ID for reference
            customer_phone: Customer phone number (optional)
            customer_name: Customer name (optional)
            description: Payment description (optional)
            
        Returns:
            Payment link URL
            
        Raises:
            StripeError: If payment link creation fails
        """
        try:
            # Create a price for this order
            price = stripe.Price.create(
                unit_amount=amount,
                currency="usd",
                product_data={
                    "name": f"Restaurant Order #{order_id}",
                    "description": description or f"Order payment for {order_id}",
                },
            )
            
            # Build metadata
            metadata = {
                "order_id": order_id,
                "source": "voice_agent",
            }
            
            if customer_phone:
                metadata["customer_phone"] = customer_phone
            if customer_name:
                metadata["customer_name"] = customer_name
            
            # Create payment link
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                after_completion={
                    "type": "redirect",
                    "redirect": {"url": self.success_url},
                },
                metadata=metadata,
                phone_number_collection={"enabled": True},
                allow_promotion_codes=True,
            )
            
            logger.info(
                f"Payment link created",
                extra={
                    "order_id": order_id,
                    "amount": amount,
                    "payment_link_id": payment_link.id,
                }
            )
            
            return payment_link.url
        
        except StripeError as e:
            logger.error(
                f"Failed to create payment link",
                extra={
                    "order_id": order_id,
                    "error_type": e.error.type if hasattr(e, 'error') else None,
                    "error_message": str(e),
                },
                exc_info=True
            )
            raise
    
    async def create_checkout_session(
        self,
        amount: int,
        order_id: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
    ) -> str:
        """
        Create a Stripe Checkout Session (alternative to payment links).
        
        Args:
            amount: Amount in cents
            order_id: Order ID
            customer_email: Customer email (optional)
            customer_phone: Customer phone (optional)
            
        Returns:
            Checkout session URL
        """
        try:
            # Create price
            price = stripe.Price.create(
                unit_amount=amount,
                currency="usd",
                product_data={
                    "name": f"Restaurant Order #{order_id}",
                },
            )
            
            # Build session params
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": price.id,
                    "quantity": 1,
                }],
                "mode": "payment",
                "success_url": self.success_url + f"?order_id={order_id}",
                "cancel_url": self.cancel_url + f"?order_id={order_id}",
                "metadata": {
                    "order_id": order_id,
                },
            }
            
            if customer_email:
                session_params["customer_email"] = customer_email
            
            if customer_phone:
                session_params["phone_number_collection"] = {"enabled": True}
            
            # Create checkout session
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(
                f"Checkout session created",
                extra={
                    "order_id": order_id,
                    "session_id": session.id,
                }
            )
            
            return session.url
        
        except StripeError as e:
            logger.error(
                f"Failed to create checkout session: {e}",
                exc_info=True
            )
            raise
    
    def get_payment_status(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Get the status of a payment intent.
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Dictionary with payment status details
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                "id": payment_intent.id,
                "status": payment_intent.status,
                "amount": payment_intent.amount,
                "currency": payment_intent.currency,
                "created": payment_intent.created,
                "metadata": payment_intent.metadata,
            }
        
        except StripeError as e:
            logger.error(f"Failed to retrieve payment intent: {e}", exc_info=True)
            raise
    
    def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refund a payment.
        
        Args:
            payment_intent_id: Payment Intent ID to refund
            amount: Amount to refund in cents (None for full refund)
            reason: Reason for refund
            
        Returns:
            Refund details
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
            }
            
            if amount:
                refund_params["amount"] = amount
            
            if reason:
                refund_params["reason"] = reason
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(
                f"Refund created",
                extra={
                    "refund_id": refund.id,
                    "payment_intent": payment_intent_id,
                    "amount": refund.amount,
                }
            )
            
            return {
                "id": refund.id,
                "status": refund.status,
                "amount": refund.amount,
                "reason": refund.reason,
            }
        
        except StripeError as e:
            logger.error(f"Failed to create refund: {e}", exc_info=True)
            raise
