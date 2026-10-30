
import base64
import json
import os
import re
from io import BytesIO

from dotenv import load_dotenv
from groq import Groq
from PIL import Image, UnidentifiedImageError


load_dotenv()

SUPPORTED_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

ALLOWED_STATUSES = {"Full", "Medium", "Low"}
MAX_IMAGES = 8
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
MAX_FOOD_NAME_LENGTH = 100

DEFAULT_MODEL = "qwen/qwen3.8-27b"


def validate_image(image_bytes):
    """Check that an uploaded image is valid and supported."""
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("The uploaded image is empty or invalid.")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError("Each image must be 10 MB or smaller.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format

            if image_format not in SUPPORTED_MIME_TYPES:
                raise ValueError(
                    "Unsupported image format. Use JPEG, PNG, or WEBP."
                )

            image.verify()

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(
            "The uploaded file is not a valid image."
        ) from exc

    return True


def _normalize_food_name(name):
    """Normalize a food name for consistent comparisons."""
    if not isinstance(name, str):
        return ""

    return " ".join(name.strip().casefold().split())


def _ingredient_key(name):
    """Normalize common singular and plural ingredient names."""
    normalized = _normalize_food_name(name)

    if not normalized:
        return ""

    if " " in normalized:
        return normalized

    plural_map = {
        "apples": "apple",
        "oranges": "orange",
        "pears": "pear",
        "tomatoes": "tomato",
        "potatoes": "potato",
        "strawberries": "strawberry",
        "blueberries": "blueberry",
        "cherries": "cherry",
        "carrots": "carrot",
        "lemons": "lemon",
        "limes": "lime",
        "sausages": "sausage",
        "cucumbers": "cucumber",
        "onions": "onion",
        "grapes": "grape",
        "bananas": "banana",
        "peaches": "peach",
        "peppers": "pepper",
        "eggs": "egg",
        "mushrooms": "mushroom",
        "prawns": "prawn",
        "raspberries": "raspberry",
        "blackberries": "blackberry",
    }

    return plural_map.get(normalized, normalized)


def _get_food_category(name):
    """Assign a category using food-name keywords."""
    food = _normalize_food_name(name)
    words = set(re.findall(r"[a-z]+", food))

    if not words:
        return "Other"

    # Tomatoes, including cherry tomatoes, are classified as vegetables.
    if words & {"tomato", "tomatoes"}:
        return "Vegetables"

    categories = {
        "Vegetables": {
            "pepper", "peppers", "carrot", "carrots", "cucumber",
            "cucumbers", "broccoli", "cabbage", "onion", "onions",
            "potato", "potatoes", "spinach", "lettuce", "cauliflower",
            "celery", "garlic", "ginger", "zucchini", "corn",
            "mushroom", "mushrooms", "eggplant", "beetroot", "radish",
            "peas", "beans", "vegetable", "vegetables",
        },
        "Fruits": {
            "apple", "apples", "pear", "pears", "orange", "oranges",
            "lemon", "lemons", "lime", "limes", "strawberry",
            "strawberries", "blueberry", "blueberries", "raspberry",
            "raspberries", "blackberry", "blackberries", "banana",
            "bananas", "grape", "grapes", "kiwi", "mango", "mangoes",
            "pineapple", "watermelon", "melon", "peach", "peaches",
            "plum", "cherry", "cherries", "avocado", "papaya",
        },
        "Dairy & Eggs": {
            "milk", "cheese", "cheddar", "mozzarella", "parmesan",
            "gouda", "butter", "yogurt", "yoghurt", "cream",
            "curd", "egg", "eggs", "paneer",
        },
        "Meat & Seafood": {
            "chicken", "beef", "pork", "fish", "salmon", "shrimp",
            "prawn", "prawns", "sausage", "sausages", "ham", "bacon",
            "salami", "pepperoni", "bologna", "prosciutto", "turkey",
            "lamb", "meat", "tuna", "crab", "seafood",
        },
        "Condiments": {
            "pickle", "pickles", "ketchup", "mustard", "mayonnaise",
            "mayo", "sauce", "sauces", "dressing", "relish", "chutney",
            "vinegar",
        },
        "Pantry": {
            "oil", "rice", "flour", "pasta", "bread", "salt",
            "sugar", "oats", "cereal", "noodles", "lentils", "grain",
            "quinoa", "spice", "spices", "peppercorn",
        },
    }

    for category in (
        "Vegetables",
        "Fruits",
        "Meat & Seafood",
        "Dairy & Eggs",
        "Condiments",
        "Pantry",
    ):
        if words & categories[category]:
            return category

    return "Other"


def _clean_food_name(name):
    """Validate and clean a food name returned by the AI."""
    if not isinstance(name, str):
        return None

    name = " ".join(name.strip().split())

    if not name or len(name) > MAX_FOOD_NAME_LENGTH:
        return None

    if not re.search(r"[a-zA-Z]", name):
        return None

    return name


def _clean_inventory(raw_inventory):
    """Validate detected foods and their visual stock estimates."""
    if not isinstance(raw_inventory, list):
        raise RuntimeError("The AI returned an invalid inventory.")

    cleaned_inventory = []
    seen_items = set()

    for entry in raw_inventory:
        if not isinstance(entry, dict):
            continue

        name = _clean_food_name(
            entry.get("item", entry.get("name", ""))
        )

        if not name:
            continue

        key = _ingredient_key(name)

        if not key or key in seen_items:
            continue

        status = entry.get(
            "quantity",
            entry.get("quantity_status", "Medium"),
        )

        if not isinstance(status, str):
            status = "Medium"

        status = status.strip().title()

        if status not in ALLOWED_STATUSES:
            status = "Medium"

        cleaned_inventory.append({
            "item": name,
            "quantity": status,
        })

        seen_items.add(key)

    if not cleaned_inventory:
        raise RuntimeError(
            "No identifiable food items were returned. "
            "Try a clearer photo with better lighting."
        )

    return cleaned_inventory


def _clean_alerts(raw_alerts, inventory):
    """Build low-stock alerts from the validated inventory."""
    low_stock_names = [
        item["item"]
        for item in inventory
        if item["quantity"] == "Low"
    ]

    if not isinstance(raw_alerts, list):
        return low_stock_names

    inventory_lookup = {
        _ingredient_key(name): name
        for name in low_stock_names
    }

    cleaned_alerts = []
    seen = set()

    for alert in raw_alerts:
        if not isinstance(alert, str):
            continue

        key = _ingredient_key(alert)

        if key in inventory_lookup and key not in seen:
            cleaned_alerts.append(inventory_lookup[key])
            seen.add(key)

    # Use the inventory itself as the source of truth.
    return low_stock_names


def _clean_instructions(raw_instructions):
    """Validate recipe cooking instructions."""
    if not isinstance(raw_instructions, list):
        return []

    instructions = []

    for instruction in raw_instructions:
        if not isinstance(instruction, str):
            continue

        instruction = instruction.strip()

        if instruction:
            instructions.append(instruction)

    return instructions[:12]


def _clean_recipes(raw_recipes, inventory):
    """Validate recipes against the foods actually detected."""
    if not isinstance(raw_recipes, list):
        raise RuntimeError("The AI returned an invalid recipe list.")

    inventory_by_key = {
        _ingredient_key(item["item"]): item["item"]
        for item in inventory
    }

    cleaned_recipes = []
    seen_recipe_names = set()

    for recipe in raw_recipes:
        if not isinstance(recipe, dict):
            continue

        recipe_name = recipe.get("name")

        if not isinstance(recipe_name, str):
            continue

        recipe_name = " ".join(recipe_name.strip().split())

        if not recipe_name:
            continue

        recipe_key = recipe_name.casefold()

        if recipe_key in seen_recipe_names:
            continue

        raw_used = recipe.get("used_ingredients", [])
        raw_additional = recipe.get(
            "additional_ingredients_needed", []
        )

        if not isinstance(raw_used, list):
            raw_used = []

        if not isinstance(raw_additional, list):
            raw_additional = []

        used_ingredients = []
        used_keys = set()

        for ingredient in raw_used:
            if not isinstance(ingredient, str):
                continue

            key = _ingredient_key(ingredient)

            # Only ingredients present in the detected inventory
            # are allowed in used_ingredients.
            if key in inventory_by_key and key not in used_keys:
                used_ingredients.append(inventory_by_key[key])
                used_keys.add(key)

        if not used_ingredients:
            continue

        additional_ingredients = []
        additional_keys = set()

        for ingredient in raw_additional:
            if not isinstance(ingredient, str):
                continue

            ingredient = " ".join(ingredient.strip().split())
            key = _ingredient_key(ingredient)

            if (
                not ingredient
                or not key
                or key in inventory_by_key
                or key in additional_keys
            ):
                continue

            additional_ingredients.append(ingredient)
            additional_keys.add(key)

        instructions = _clean_instructions(
            recipe.get("instructions", [])
        )

        if not instructions:
            continue

        cleaned_recipes.append({
            "name": recipe_name,
            "used_ingredients": used_ingredients,
            "additional_ingredients_needed": additional_ingredients,
            "instructions": instructions,
        })

        seen_recipe_names.add(recipe_key)


        if not cleaned_recipes:
            raise RuntimeError(
            "The AI did not return valid recipes using "
            "detected foods. Please try scanning again."
        )

    # Rank recipes by ingredient availability.
    def recipe_priority(recipe):
        available_count = len(recipe["used_ingredients"])
        missing_count = len(
            recipe["additional_ingredients_needed"]
        )
        total_count = available_count + missing_count

        availability_ratio = (
            available_count / total_count
            if total_count > 0
            else 0
        )

        return (
            -availability_ratio,
            missing_count,
            -available_count,
        )

    cleaned_recipes.sort(key=recipe_priority)

    return cleaned_recipes


def analyze_fridge(image_bytes_list):
    """
    Analyze one or more fridge images with Groq AI.

    Returns:
        {
            "inventory": [
                {"item": "eggs", "quantity": "Medium"}
            ],
            "low_stock_alerts": ["blueberries"],
            "suggested_recipes": [...]
        }
    """
    if isinstance(image_bytes_list, (bytes, bytearray)):
        image_bytes_list = [bytes(image_bytes_list)]

    if not isinstance(image_bytes_list, (list, tuple)):
        raise ValueError("Provide one or more image files.")

    if not image_bytes_list:
        raise ValueError("Please upload at least one fridge photo.")

    if len(image_bytes_list) > MAX_IMAGES:
        raise ValueError(
            f"You can upload a maximum of {MAX_IMAGES} images at once."
        )

    validated_images = []

    for image_bytes in image_bytes_list:
        if not isinstance(image_bytes, bytes):
            raise ValueError("Each uploaded image must contain image bytes.")

        validate_image(image_bytes)

        # Detect the MIME type from the image itself.
        with Image.open(BytesIO(image_bytes)) as image:
            mime_type = SUPPORTED_MIME_TYPES[image.format]

        validated_images.append((image_bytes, mime_type))

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your .env file "
            "and restart the application."
        )

    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    prompt = """
You are a careful kitchen assistant analyzing refrigerator photos.

INVENTORY RULES:
1. Inspect every supplied photo carefully, including all visible shelves,
   drawers, containers, trays, and partly obscured foods.
2. Return a comprehensive inventory of every food item that can reasonably
   be identified, not just the most prominent items.
3. Look specifically for cooked chicken, other cooked meats, leftovers,
   white cheese, other cheeses, rice, milk, eggs, fruits, vegetables,
   sauces, oils, and packaged foods when visible.
4. Identify raw, cooked, and prepared foods separately when distinguishable.
5. Do not invent foods that are not visibly supported by the photos.
6. If an item is partly obscured, include it only when its identity is
   reasonably clear. Do not guess exact ingredients without evidence.
7. Use short, consistent names, such as "cooked chicken", "white rice",
   "white cheese", "olive oil", and "yellow bell peppers".
8. Do not merge different foods into one item. Remove duplicate entries
   only when they refer to the same food.
9. Estimate visible stock as exactly Full, Medium, or Low. These are visual
   estimates, not measured quantities.
10. Include all detected foods in inventory, even if they are not needed
    for the recipes.
11. low_stock_alerts must contain the items marked Low.

RECIPE RULES:
1. Suggest up to 10 practical recipes.
Prioritize recipes that use the largest possible proportion of
ingredients already detected in the fridge.
Include:
- Recipes that can be prepared with all available ingredients.
- Recipes missing only one or two ingredients.
- Other practical recipes that use several available ingredients.
Return complete ingredient lists so missing ingredients can be identified.
2. Each recipe must use at least one ingredient from the detected inventory.
3. used_ingredients must contain only detected ingredients, using their
   exact names from inventory.
4. Put ingredients that are not detected in additional_ingredients_needed.
5. Do not claim that missing ingredients are available in the fridge.
6. Provide practical cooking instructions.
7. Do not suggest a recipe that cannot reasonably use the detected foods.

Return only a valid JSON object in this format:
{
  "inventory": [
    {"item": "cooked chicken", "quantity": "Medium"},
    {"item": "white rice", "quantity": "Full"}
  ],
  "low_stock_alerts": [],
  "suggested_recipes": [
    {
      "name": "Example recipe one",
      "used_ingredients": ["cooked chicken"],
      "additional_ingredients_needed": ["oil"],
      "instructions": [
        "Prepare the ingredients.",
        "Cook thoroughly."
      ]
    },
    {
      "name": "Example recipe two",
      "used_ingredients": ["white rice"],
      "additional_ingredients_needed": [],
      "instructions": [
        "Prepare the ingredients.",
        "Cook until ready."
      ]
    }
  ]
}

The foods in the example are illustrative only. Return the actual foods
identified in the supplied photos.
"""

    message_content = [
        {
            "type": "text",
            "text": prompt,
        }
    ]

    for image_bytes, mime_type in validated_images:
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded_image}"
            },
        })

    try:
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": message_content,
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        response_text = response.choices[0].message.content

        if not response_text:
            raise RuntimeError("The AI returned an empty response.")

        result = json.loads(response_text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "The AI returned invalid JSON. Please try scanning again."
        ) from exc

    except Exception as exc:
        # Keep the error understandable without exposing the API key.
        raise RuntimeError(
            "Fridge analysis failed. Check your internet connection, "
            "Groq API key, model configuration, and API usage limits. "
            f"Details: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError("The AI returned an invalid response.")

    inventory = _clean_inventory(result.get("inventory", []))

    low_stock_alerts = _clean_alerts(
        result.get("low_stock_alerts", []),
        inventory,
    )

    suggested_recipes = _clean_recipes(
        result.get("suggested_recipes", []),
        inventory,
    )

    return {
        "inventory": inventory,
        "low_stock_alerts": low_stock_alerts,
        "suggested_recipes": suggested_recipes,
    }


def detect_foods(image_bytes_list):
    """
    Return detected foods in the format used by the inventory database.
    """
    analysis = analyze_fridge(image_bytes_list)

    detected_foods = []

    for item in analysis["inventory"]:
        name = item["item"]
        status = item["quantity"]

        detected_foods.append({
            "name": name,
            "quantity": 1,
            "unit": "item",
            "category": _get_food_category(name),
            "quantity_status": status,
        })

    return detected_foods
