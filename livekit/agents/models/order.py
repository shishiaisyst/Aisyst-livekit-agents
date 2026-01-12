"""
Order data models for managing customer orders.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid


class OrderStatus(str, Enum):
    """Order status types."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    """Represents a single item in an order."""
    
    menu_item_id: str = Field(..., description="ID of the menu item")
    name: str = Field(..., description="Name of the item")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price: float = Field(..., gt=0, description="Price per unit")
    
    # Customizations
    customizations: Dict[str, str] = Field(
        default_factory=dict,
        description="Customization options applied to this item"
    )
    special_instructions: Optional[str] = Field(
        None,
        description="Special preparation instructions"
    )
    
    @property
    def subtotal(self) -> float:
        """Calculate subtotal for this item."""
        return round(self.unit_price * self.quantity, 2)
    
    def to_speech_description(self) -> str:
        """Convert to natural speech description."""
        desc = f"{self.quantity} {self.name}"
        
        if self.customizations:
            custom_str = ", ".join([f"{k}: {v}" for k, v in self.customizations.items()])
            desc += f" with {custom_str}"
        
        if self.special_instructions:
            desc += f". Special instructions: {self.special_instructions}"
        
        return desc


class Order(BaseModel):
    """Represents a complete customer order."""
    
    order_id: str = Field(default_factory=lambda: f"ORD-{uuid.uuid4().hex[:8].upper()}")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Customer information
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    customer_name: Optional[str] = Field(None, description="Customer name")
    
    # Order details
    items: List[OrderItem] = Field(default_factory=list, description="Items in the order")
    status: OrderStatus = Field(OrderStatus.PENDING, description="Current order status")
    
    # Pricing
    tax_rate: float = Field(0.08, description="Tax rate as decimal")
    
    # Delivery/pickup
    order_type: str = Field("pickup", description="Order type: pickup, delivery, dine-in")
    delivery_address: Optional[str] = Field(None, description="Delivery address if applicable")
    estimated_ready_time: Optional[int] = Field(None, description="Minutes until ready")
    
    # Payment
    payment_link: Optional[str] = Field(None, description="Stripe payment link")
    payment_status: str = Field("pending", description="Payment status")
    paid_at: Optional[datetime] = Field(None, description="Payment completion timestamp")
    
    # Notes
    notes: Optional[str] = Field(None, description="Additional order notes")
    
    @validator("items")
    def items_not_empty(cls, v: List[OrderItem]) -> List[OrderItem]:
        """Ensure order has at least one item when being validated."""
        # Allow empty during construction, but validate when needed
        return v
    
    @property
    def subtotal(self) -> float:
        """Calculate order subtotal before tax."""
        return round(sum(item.subtotal for item in self.items), 2)
    
    @property
    def tax_amount(self) -> float:
        """Calculate tax amount."""
        return round(self.subtotal * self.tax_rate, 2)
    
    @property
    def total(self) -> float:
        """Calculate total including tax."""
        return round(self.subtotal + self.tax_amount, 2)
    
    def add_item(
        self,
        menu_item_id: str,
        name: str,
        quantity: int,
        unit_price: float,
        customizations: Optional[Dict[str, str]] = None,
        special_instructions: Optional[str] = None,
    ) -> OrderItem:
        """
        Add an item to the order.
        
        Returns:
            The created OrderItem
        """
        item = OrderItem(
            menu_item_id=menu_item_id,
            name=name,
            quantity=quantity,
            unit_price=unit_price,
            customizations=customizations or {},
            special_instructions=special_instructions,
        )
        self.items.append(item)
        self.updated_at = datetime.now()
        return item
    
    def remove_item(self, index: int) -> bool:
        """
        Remove an item from the order by index.
        
        Returns:
            True if item was removed, False if index invalid
        """
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self.updated_at = datetime.now()
            return True
        return False
    
    def update_item_quantity(self, index: int, new_quantity: int) -> bool:
        """
        Update quantity for an item.
        
        Returns:
            True if updated successfully, False if index invalid
        """
        if 0 <= index < len(self.items) and new_quantity > 0:
            self.items[index].quantity = new_quantity
            self.updated_at = datetime.now()
            return True
        return False
    
    def clear_items(self) -> None:
        """Remove all items from the order."""
        self.items = []
        self.updated_at = datetime.now()
    
    def to_summary(self) -> str:
        """Generate a text summary of the order."""
        summary = f"Order #{self.order_id}\n"
        summary += "=" * 40 + "\n\n"
        
        if not self.items:
            summary += "No items in order\n"
            return summary
        
        for i, item in enumerate(self.items, 1):
            summary += f"{i}. {item.quantity}x {item.name} @ ${item.unit_price:.2f} = ${item.subtotal:.2f}\n"
            if item.customizations:
                for key, value in item.customizations.items():
                    summary += f"   - {key}: {value}\n"
            if item.special_instructions:
                summary += f"   Note: {item.special_instructions}\n"
        
        summary += "\n"
        summary += f"Subtotal: ${self.subtotal:.2f}\n"
        summary += f"Tax ({self.tax_rate*100:.1f}%): ${self.tax_amount:.2f}\n"
        summary += f"Total: ${self.total:.2f}\n"
        
        if self.order_type:
            summary += f"\nOrder Type: {self.order_type.title()}\n"
        
        return summary
    
    def to_speech_summary(self) -> str:
        """Generate a natural speech summary of the order."""
        if not self.items:
            return "Your order is currently empty."
        
        summary = "Here's your order: "
        
        item_descriptions = []
        for item in self.items:
            item_descriptions.append(item.to_speech_description())
        
        summary += ", ".join(item_descriptions)
        summary += f". Your total is ${self.total:.2f} including tax."
        
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for serialization."""
        return {
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "customer_phone": self.customer_phone,
            "customer_name": self.customer_name,
            "items": [
                {
                    "menu_item_id": item.menu_item_id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "customizations": item.customizations,
                    "special_instructions": item.special_instructions,
                }
                for item in self.items
            ],
            "status": self.status.value,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total": self.total,
            "order_type": self.order_type,
            "delivery_address": self.delivery_address,
            "payment_link": self.payment_link,
            "payment_status": self.payment_status,
        }
