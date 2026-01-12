"""
Data models for Stripe payment integration.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PaymentStatus(str, Enum):
    """Payment status types."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentLinkResult(BaseModel):
    """Result of creating a payment link."""
    
    url: str = Field(..., description="Payment link URL")
    id: str = Field(..., description="Stripe payment link ID")
    created_at: datetime = Field(default_factory=datetime.now)
    order_id: str = Field(..., description="Associated order ID")
    amount: int = Field(..., description="Amount in cents")
    status: PaymentStatus = Field(PaymentStatus.PENDING, description="Payment status")


class PaymentIntentDetails(BaseModel):
    """Details of a Stripe Payment Intent."""
    
    id: str = Field(..., description="Payment Intent ID")
    amount: int = Field(..., description="Amount in cents")
    currency: str = Field("usd", description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    created: int = Field(..., description="Unix timestamp of creation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_phone: Optional[str] = Field(None, description="Customer phone")
    
    receipt_url: Optional[str] = Field(None, description="Receipt URL")
    invoice_url: Optional[str] = Field(None, description="Invoice URL")


class RefundDetails(BaseModel):
    """Details of a payment refund."""
    
    id: str = Field(..., description="Refund ID")
    payment_intent_id: str = Field(..., description="Original payment intent ID")
    amount: int = Field(..., description="Refund amount in cents")
    status: str = Field(..., description="Refund status")
    reason: Optional[str] = Field(None, description="Refund reason")
    created: int = Field(..., description="Unix timestamp of creation")


class WebhookEvent(BaseModel):
    """Stripe webhook event data."""
    
    id: str = Field(..., description="Event ID")
    type: str = Field(..., description="Event type")
    created: int = Field(..., description="Unix timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")
    livemode: bool = Field(..., description="Whether this is a live event")
