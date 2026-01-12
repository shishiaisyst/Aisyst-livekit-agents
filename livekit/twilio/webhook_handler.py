"""
Webhook handler for Twilio delivery status callbacks.
"""

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])


@router.post("/status")
async def handle_sms_status(request: Request) -> Dict[str, str]:
    """
    Handle Twilio SMS delivery status webhook.
    
    Twilio sends status updates for each SMS:
    - queued: Message is queued for delivery
    - sending: Message is being sent
    - sent: Message was sent to carrier
    - delivered: Message was delivered to recipient
    - failed: Message delivery failed
    - undelivered: Message could not be delivered
    """
    try:
        form_data = await request.form()
        
        message_sid = form_data.get("MessageSid")
        message_status = form_data.get("MessageStatus")
        to_number = form_data.get("To")
        error_code = form_data.get("ErrorCode")
        error_message = form_data.get("ErrorMessage")
        
        logger.info(
            f"SMS status update received",
            extra={
                "message_sid": message_sid,
                "status": message_status,
                "to": to_number,
                "error_code": error_code,
            }
        )
        
        # Handle specific statuses
        if message_status == "delivered":
            logger.info(f"SMS delivered successfully: {message_sid}")
        
        elif message_status in ["failed", "undelivered"]:
            logger.error(
                f"SMS delivery failed: {message_sid}",
                extra={
                    "error_code": error_code,
                    "error_message": error_message,
                }
            )
            # TODO: Implement retry logic or alternative notification method
        
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/incoming")
async def handle_incoming_sms(request: Request) -> Dict[str, str]:
    """
    Handle incoming SMS messages from customers.
    
    This can be used for customers to check order status, modify orders, etc.
    """
    try:
        form_data = await request.form()
        
        from_number = form_data.get("From")
        message_body = form_data.get("Body", "").strip().lower()
        message_sid = form_data.get("MessageSid")
        
        logger.info(
            f"Incoming SMS received",
            extra={
                "from": from_number,
                "message_sid": message_sid,
                "body": message_body,
            }
        )
        
        # TODO: Implement SMS command processing
        # Examples:
        # - "STATUS <order_id>" - Check order status
        # - "HELP" - Get help information
        # - "CANCEL <order_id>" - Cancel order
        
        # For now, just log and acknowledge
        response_message = (
            f"Thank you for your message! For immediate assistance, "
            f"please call {logger.get('RESTAURANT_PHONE', 'us')}."
        )
        
        # Return TwiML response
        return {
            "status": "received",
            "response": response_message
        }
    
    except Exception as e:
        logger.error(f"Error processing incoming SMS: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
