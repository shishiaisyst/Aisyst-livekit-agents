"""
Menu data models for restaurant items and categories.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class DietaryRestriction(str, Enum):
    """Dietary restriction types."""
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    NUT_FREE = "nut_free"
    HALAL = "halal"
    KOSHER = "kosher"


class MenuItem(BaseModel):
    """Represents a single menu item."""
    
    id: str = Field(..., description="Unique identifier for the menu item")
    name: str = Field(..., description="Name of the menu item")
    description: str = Field(..., description="Detailed description of the item")
    price: float = Field(..., gt=0, description="Price in dollars")
    category: str = Field(..., description="Category this item belongs to")
    
    # Optional fields
    image_url: Optional[str] = Field(None, description="URL to item image")
    calories: Optional[int] = Field(None, description="Calorie count")
    prep_time: Optional[int] = Field(None, description="Preparation time in minutes")
    
    # Dietary information
    dietary_restrictions: List[DietaryRestriction] = Field(
        default_factory=list,
        description="List of dietary restrictions this item satisfies"
    )
    allergens: List[str] = Field(
        default_factory=list,
        description="List of allergens present in this item"
    )
    
    # Availability
    available: bool = Field(True, description="Whether item is currently available")
    seasonal: bool = Field(False, description="Whether this is a seasonal item")
    
    # Customization
    customizable: bool = Field(False, description="Whether item can be customized")
    customization_options: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Available customization options"
    )
    
    @validator("price")
    def price_must_be_positive(cls, v: float) -> float:
        """Ensure price is positive."""
        if v <= 0:
            raise ValueError("Price must be positive")
        return round(v, 2)
    
    def to_speech_description(self) -> str:
        """Convert item to natural speech description."""
        desc = f"{self.name} for ${self.price:.2f}"
        if self.description:
            desc += f". {self.description}"
        
        if self.dietary_restrictions:
            restrictions = ", ".join([r.value.replace("_", " ") for r in self.dietary_restrictions])
            desc += f". This item is {restrictions}"
        
        if not self.available:
            desc += ". Currently unavailable"
        
        return desc


class MenuCategory(BaseModel):
    """Represents a category of menu items."""
    
    id: str = Field(..., description="Unique identifier for the category")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    items: List[MenuItem] = Field(default_factory=list, description="Items in this category")
    display_order: int = Field(0, description="Order to display this category")
    
    def get_available_items(self) -> List[MenuItem]:
        """Get only available items in this category."""
        return [item for item in self.items if item.available]
    
    def find_item_by_name(self, name: str) -> Optional[MenuItem]:
        """Find an item by name (case-insensitive)."""
        name_lower = name.lower()
        for item in self.items:
            if name_lower in item.name.lower():
                return item
        return None


class Menu(BaseModel):
    """Represents the complete restaurant menu."""
    
    restaurant_name: str = Field(..., description="Name of the restaurant")
    categories: List[MenuCategory] = Field(
        default_factory=list,
        description="Menu categories"
    )
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    
    def get_category(self, category_name: str) -> Optional[MenuCategory]:
        """Get a category by name (case-insensitive)."""
        name_lower = category_name.lower()
        for category in self.categories:
            if name_lower in category.name.lower():
                return category
        return None
    
    def search_items(
        self,
        query: str,
        category: Optional[str] = None,
        dietary_restriction: Optional[DietaryRestriction] = None,
        max_price: Optional[float] = None,
    ) -> List[MenuItem]:
        """
        Search for menu items based on various criteria.
        
        Args:
            query: Search term for item name or description
            category: Filter by category name
            dietary_restriction: Filter by dietary restriction
            max_price: Maximum price filter
            
        Returns:
            List of matching menu items
        """
        results = []
        query_lower = query.lower() if query else ""
        
        categories_to_search = self.categories
        if category:
            cat = self.get_category(category)
            categories_to_search = [cat] if cat else []
        
        for cat in categories_to_search:
            for item in cat.get_available_items():
                # Text search
                if query and query_lower not in item.name.lower() and \
                   query_lower not in item.description.lower():
                    continue
                
                # Dietary restriction filter
                if dietary_restriction and dietary_restriction not in item.dietary_restrictions:
                    continue
                
                # Price filter
                if max_price and item.price > max_price:
                    continue
                
                results.append(item)
        
        return results
    
    def get_all_items(self) -> List[MenuItem]:
        """Get all available items across all categories."""
        items = []
        for category in self.categories:
            items.extend(category.get_available_items())
        return items
    
    def to_summary(self) -> str:
        """Generate a text summary of the menu."""
        summary = f"Menu for {self.restaurant_name}\n"
        summary += "=" * 50 + "\n\n"
        
        for category in sorted(self.categories, key=lambda c: c.display_order):
            summary += f"{category.name}\n"
            summary += "-" * len(category.name) + "\n"
            
            for item in category.get_available_items():
                summary += f"  {item.name} - ${item.price:.2f}\n"
                if item.description:
                    summary += f"    {item.description}\n"
            
            summary += "\n"
        
        return summary
