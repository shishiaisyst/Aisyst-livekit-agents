"""
Restaurant menu data configuration.
Customize this file with your actual menu items.
"""

from agents.models.menu import Menu, MenuCategory, MenuItem, DietaryRestriction


def get_restaurant_menu() -> Menu:
    """
    Get the restaurant menu with all categories and items.
    Customize this function with your actual menu data.
    """
    
    # Appetizers
    appetizers = MenuCategory(
        id="appetizers",
        name="Appetizers",
        description="Start your meal with one of our delicious appetizers",
        display_order=1,
        items=[
            MenuItem(
                id="app-001",
                name="Mozzarella Sticks",
                description="Crispy breaded mozzarella served with marinara sauce",
                price=8.99,
                category="appetizers",
                calories=450,
                prep_time=10,
                customizable=False,
            ),
            MenuItem(
                id="app-002",
                name="Buffalo Wings",
                description="Spicy chicken wings with ranch or blue cheese",
                price=11.99,
                category="appetizers",
                calories=680,
                prep_time=15,
                customizable=True,
                customization_options={
                    "sauce": ["Buffalo", "BBQ", "Honey Garlic", "Plain"],
                    "dressing": ["Ranch", "Blue Cheese"],
                },
            ),
            MenuItem(
                id="app-003",
                name="Hummus Platter",
                description="House-made hummus with vegetables and pita bread",
                price=9.99,
                category="appetizers",
                calories=320,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="app-004",
                name="Calamari",
                description="Lightly fried squid with lemon aioli",
                price=12.99,
                category="appetizers",
                calories=520,
                prep_time=12,
                allergens=["shellfish", "gluten"],
            ),
        ],
    )
    
    # Salads
    salads = MenuCategory(
        id="salads",
        name="Salads",
        description="Fresh, crisp salads made daily",
        display_order=2,
        items=[
            MenuItem(
                id="sal-001",
                name="Caesar Salad",
                description="Romaine lettuce, parmesan, croutons, Caesar dressing",
                price=10.99,
                category="salads",
                calories=380,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
                customizable=True,
                customization_options={
                    "protein": ["None", "Grilled Chicken +$5", "Grilled Salmon +$7"],
                },
            ),
            MenuItem(
                id="sal-002",
                name="Greek Salad",
                description="Mixed greens, feta, olives, tomatoes, cucumber, red onion",
                price=11.99,
                category="salads",
                calories=290,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.GLUTEN_FREE],
            ),
            MenuItem(
                id="sal-003",
                name="Cobb Salad",
                description="Mixed greens, chicken, bacon, egg, avocado, blue cheese",
                price=13.99,
                category="salads",
                calories=540,
                prep_time=8,
                dietary_restrictions=[DietaryRestriction.GLUTEN_FREE],
            ),
        ],
    )
    
    # Burgers & Sandwiches
    burgers = MenuCategory(
        id="burgers",
        name="Burgers & Sandwiches",
        description="Served with choice of fries or salad",
        display_order=3,
        items=[
            MenuItem(
                id="burg-001",
                name="Classic Cheeseburger",
                description="8oz beef patty, cheddar, lettuce, tomato, onion, pickles",
                price=12.99,
                category="burgers",
                calories=720,
                prep_time=15,
                customizable=True,
                customization_options={
                    "cheese": ["Cheddar", "Swiss", "Pepper Jack", "No Cheese"],
                    "temperature": ["Rare", "Medium Rare", "Medium", "Medium Well", "Well Done"],
                    "extras": ["Bacon +$2", "Avocado +$2", "Mushrooms +$1", "Fried Egg +$2"],
                },
            ),
            MenuItem(
                id="burg-002",
                name="Bacon BBQ Burger",
                description="8oz beef patty, bacon, cheddar, BBQ sauce, onion rings",
                price=14.99,
                category="burgers",
                calories=890,
                prep_time=15,
            ),
            MenuItem(
                id="burg-003",
                name="Veggie Burger",
                description="House-made black bean patty, avocado, sprouts, chipotle aioli",
                price=11.99,
                category="burgers",
                calories=480,
                prep_time=12,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            ),
            MenuItem(
                id="sand-001",
                name="Grilled Chicken Sandwich",
                description="Marinated chicken breast, lettuce, tomato, mayo",
                price=11.99,
                category="burgers",
                calories=520,
                prep_time=12,
            ),
            MenuItem(
                id="sand-002",
                name="BLT",
                description="Bacon, lettuce, tomato on toasted sourdough",
                price=9.99,
                category="burgers",
                calories=450,
                prep_time=8,
            ),
        ],
    )
    
    # Entrees
    entrees = MenuCategory(
        id="entrees",
        name="Main Entrees",
        description="Hearty meals served with two sides",
        display_order=4,
        items=[
            MenuItem(
                id="ent-001",
                name="Grilled Salmon",
                description="Fresh Atlantic salmon with lemon butter sauce",
                price=19.99,
                category="entrees",
                calories=580,
                prep_time=20,
                dietary_restrictions=[DietaryRestriction.GLUTEN_FREE],
                allergens=["fish"],
            ),
            MenuItem(
                id="ent-002",
                name="New York Strip Steak",
                description="12oz premium cut with garlic herb butter",
                price=24.99,
                category="entrees",
                calories=680,
                prep_time=25,
                dietary_restrictions=[DietaryRestriction.GLUTEN_FREE],
                customizable=True,
                customization_options={
                    "temperature": ["Rare", "Medium Rare", "Medium", "Medium Well", "Well Done"],
                },
            ),
            MenuItem(
                id="ent-003",
                name="Chicken Parmesan",
                description="Breaded chicken breast, marinara, mozzarella, spaghetti",
                price=16.99,
                category="entrees",
                calories=890,
                prep_time=20,
            ),
            MenuItem(
                id="ent-004",
                name="Vegetable Stir Fry",
                description="Seasonal vegetables in teriyaki sauce over rice",
                price=14.99,
                category="entrees",
                calories=420,
                prep_time=15,
                dietary_restrictions=[
                    DietaryRestriction.VEGETARIAN,
                    DietaryRestriction.VEGAN,
                    DietaryRestriction.GLUTEN_FREE,
                ],
            ),
        ],
    )
    
    # Sides
    sides = MenuCategory(
        id="sides",
        name="Sides",
        description="Perfect additions to any meal",
        display_order=5,
        items=[
            MenuItem(
                id="side-001",
                name="French Fries",
                description="Crispy golden fries",
                price=4.99,
                category="sides",
                calories=380,
                prep_time=8,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="side-002",
                name="Sweet Potato Fries",
                description="Sweet and savory fries",
                price=5.99,
                category="sides",
                calories=420,
                prep_time=10,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="side-003",
                name="Onion Rings",
                description="Beer-battered onion rings",
                price=5.99,
                category="sides",
                calories=480,
                prep_time=10,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            ),
            MenuItem(
                id="side-004",
                name="Steamed Vegetables",
                description="Seasonal vegetable medley",
                price=4.99,
                category="sides",
                calories=80,
                prep_time=8,
                dietary_restrictions=[
                    DietaryRestriction.VEGETARIAN,
                    DietaryRestriction.VEGAN,
                    DietaryRestriction.GLUTEN_FREE,
                ],
            ),
            MenuItem(
                id="side-005",
                name="Mashed Potatoes",
                description="Creamy mashed potatoes with gravy",
                price=4.99,
                category="sides",
                calories=240,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.GLUTEN_FREE],
            ),
        ],
    )
    
    # Desserts
    desserts = MenuCategory(
        id="desserts",
        name="Desserts",
        description="Sweet endings to your meal",
        display_order=6,
        items=[
            MenuItem(
                id="des-001",
                name="Chocolate Lava Cake",
                description="Warm chocolate cake with molten center, vanilla ice cream",
                price=7.99,
                category="desserts",
                calories=620,
                prep_time=8,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            ),
            MenuItem(
                id="des-002",
                name="New York Cheesecake",
                description="Classic creamy cheesecake with berry compote",
                price=6.99,
                category="desserts",
                calories=480,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            ),
            MenuItem(
                id="des-003",
                name="Apple Pie",
                description="Warm apple pie with cinnamon, served a la mode",
                price=6.99,
                category="desserts",
                calories=520,
                prep_time=10,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            ),
        ],
    )
    
    # Drinks
    drinks = MenuCategory(
        id="drinks",
        name="Beverages",
        description="Refresh yourself",
        display_order=7,
        items=[
            MenuItem(
                id="drink-001",
                name="Soft Drink",
                description="Coke, Diet Coke, Sprite, Root Beer, Lemonade",
                price=2.99,
                category="drinks",
                calories=150,
                prep_time=1,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="drink-002",
                name="Iced Tea",
                description="Freshly brewed, sweetened or unsweetened",
                price=2.99,
                category="drinks",
                calories=90,
                prep_time=1,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="drink-003",
                name="Coffee",
                description="Fresh brewed coffee",
                price=2.49,
                category="drinks",
                calories=5,
                prep_time=2,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN, DietaryRestriction.VEGAN],
            ),
            MenuItem(
                id="drink-004",
                name="Milkshake",
                description="Chocolate, Vanilla, or Strawberry",
                price=5.99,
                category="drinks",
                calories=520,
                prep_time=5,
                dietary_restrictions=[DietaryRestriction.VEGETARIAN],
                customizable=True,
                customization_options={
                    "flavor": ["Chocolate", "Vanilla", "Strawberry"],
                },
            ),
        ],
    )
    
    # Create and return the complete menu
    menu = Menu(
        restaurant_name="Your Restaurant Name",
        categories=[
            appetizers,
            salads,
            burgers,
            entrees,
            sides,
            desserts,
            drinks,
        ],
    )
    
    return menu
