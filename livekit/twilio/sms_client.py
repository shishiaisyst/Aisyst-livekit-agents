"""
Twilio SMS client for sending order notifications and payment links.
"""

import os
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from twilio.templates import (
    format_order_confirmation,
    format_payment_link_message,
    format_order_status_update,
)
from monitoring.logger import get_logger

logger = get_logger(__name__)


class TwilioSMSClient:
    """Client for sending SMS messages via Twilio."""
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        """
        Initialize Twilio SMS client.
        
        Args:
            account_sid: Twilio Account SID (defaults to TWILIO_ACCOUNT_SID env var)
            auth_token: Twilio Auth Token (defaults to TWILIO_AUTH_TOKEN env var)
            from_number: Twilio phone number to send from (defaults to TWILIO_PHONE_NUMBER env var)
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables."
            )
        
        self.client = Client(self.account_sid, self.auth_token)
        logger.info("Twilio SMS client initialized")
    
    async def send_sms(
        self,
        to: str,
        message: str,
        status_callback: Optional[str] = None,
    ) -> str:
        """
        Send an SMS message.
        
        Args:
            to: Recipient phone number (E.164 format, e.g., +1234567890)
            message: Message content
            status_callback: Optional webhook URL for delivery status
            
        Returns:
            Message SID
            
        Raises:
            TwilioRestException: If SMS sending fails
        """
        try:
            params = {
                "from_": self.from_number,
                "to": to,
                "body": message,
            }
            
            if status_callback:
                params["status_callback"] = status_callback
            
            sms = self.client.messages.create(**params)
            
            logger.info(
                f"SMS sent successfully",
                extra={
                    "to": to,
                    "message_sid": sms.sid,
                    "status": sms.status,
                }
            )
            
            return sms.sid
        
        except TwilioRestException as e:
            logger.error(
                f"Failed to send SMS",
                extra={
                    "to": to,
                    "error_code": e.code,
                    "error_message": e.msg,
                },
                exc_info=True
            )
            raise
    
    async def send_order_confirmation(
        self,
        to: str,
        order_id: str,
        total: float,
        payment_link: Optional[str] = None,
        order_type: str = "pickup",
    ) -> str:
        """
        Send an order confirmation SMS.
        
        Args:
            to: Customer phone number
            order_id: Order ID
            total: Order total amount
            payment_link: Optional payment link URL
            order_type: Type of order (pickup, delivery, dine-in)
            
        Returns:
            Message SID
        """
        message = format_order_confirmation(
            order_id=order_id,
            total=total,
            payment_link=payment_link,
            order_type=order_type,
        )
        
        logger.info(
            f"Sending order confirmation",
            extra={"order_id": order_id, "to": to}
        )
        
        return await self.send_sms(to=to, message=message)
    
    async def send_payment_link(
        self,
        to: str,
        order_id: str,
        payment_link: str,
        amount: float,
    ) -> str:
        """
        Send a payment link SMS.
        
        Args:
            to: Customer phone number
            order_id: Order ID
            payment_link: Stripe payment link URL
            amount: Payment amount
            
        Returns:
            Message SID
        """
        message = format_payment_link_message(
            order_id=order_id,
            payment_link=payment_link,
            amount=amount,
        )
        
        logger.info(
            f"Sending payment link",
            extra={"order_id": order_id, "to": to}
        )
        
        return await self.send_sms(to=to, message=message)
    
    async def send_order_status_update(
        self,
        to: str,
        order_id: str,
        status: str,
        estimated_time: Optional[int] = None,
    ) -> str:
        """
        Send an order status update SMS.
        
        Args:
            to: Customer phone number
            order_id: Order ID
            status: New order status
            estimated_time: Estimated time in minutes (optional)
            
        Returns:
            Message SID
        """
        message = format_order_status_update(
            order_id=order_id,
            status=status,
            estimated_time=estimated_time,
        )
        
        logger.info(
            f"Sending order status update",
            extra={"order_id": order_id, "status": status, "to": to}
        )
        
        return await self.send_sms(to=to, message=message)
    
    def get_message_status(self, message_sid: str) -> dict:
        """
        Get the status of a sent message.
        
        Args:
            message_sid: Message SID from Twilio
            
        Returns:
            Dictionary with message status details
        """
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "from": message.from_,
                "date_sent": message.date_sent,
                "error_code": message.error_code,
                "error_message": message.error_message,
            }
        
        except TwilioRestException as e:
            logger.error(f"Failed to fetch message status: {e}", exc_info=True)
            raise
