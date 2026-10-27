
RECIPES = [
    {
        "name": "Classic Cheese Omelet",
        "description": "A quick American-style breakfast with eggs and cheese.",
        "ingredients": ["Eggs", "Cheddar Cheese", "Butter"],
        "instructions": [
            "Beat the eggs in a bowl.",
            "Melt butter in a non-stick pan.",
            "Add eggs and cook gently.",
            "Add cheese, fold the omelet, and serve."
        ],
        "time": 10,
        "servings": 1,
    },
    {
        "name": "Grilled Cheese Sandwich",
        "description": "A crispy, buttery sandwich with melted cheese.",
        "ingredients": ["Bread", "Cheddar Cheese", "Butter"],
        "instructions": [
            "Butter the outside of two bread slices.",
            "Place cheese between the slices.",
            "Cook in a pan until golden on both sides.",
            "Slice and serve warm."
        ],
        "time": 10,
        "servings": 1,
    },
    {
        "name": "Fresh Tomato and Lettuce Salad",
        "description": "A simple, refreshing vegetable salad.",
        "ingredients": ["Tomatoes", "Lettuce"],
        "instructions": [
            "Wash the tomatoes and lettuce.",
            "Slice the tomatoes and tear the lettuce.",
            "Combine in a bowl and add your preferred dressing."
        ],
        "time": 5,
        "servings": 2,
    },
    {
        "name": "American Cheeseburger",
        "description": "A classic burger with cheese and fresh vegetables.",
        "ingredients": [
            "Burger Buns", "Ground Beef", "Cheddar Cheese",
            "Tomatoes", "Lettuce"
        ],
        "instructions": [
            "Shape ground beef into a patty and cook thoroughly.",
            "Add cheese during the final minute of cooking.",
            "Toast the burger buns.",
            "Assemble with lettuce, tomato, and the cooked patty."
        ],
        "time": 20,
        "servings": 1,
    },
]


def recommend_recipes(inventory_names):
    """Return recipes ranked by how many ingredients are available."""
    available = {name.strip().casefold() for name in inventory_names}

    results = []

    for recipe in RECIPES:
        matched = [
            ingredient for ingredient in recipe["ingredients"]
            if ingredient.casefold() in available
        ]
        missing = [
            ingredient for ingredient in recipe["ingredients"]
            if ingredient.casefold() not in available
        ]

        results.append({
            **recipe,
            "available_ingredients": matched,
            "missing_ingredients": missing,
            "match_count": len(matched),
            "match_percent": round(
                len(matched) / len(recipe["ingredients"]) * 100
            ),
        })

    return sorted(
        results,
        key=lambda recipe: (
            recipe["match_percent"],
            recipe["match_count"]
        ),
        reverse=True,
    )
