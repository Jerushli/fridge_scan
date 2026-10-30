import re

import streamlit as st

from database import (
    init_db,
    get_inventory,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    get_grocery_items,
    add_grocery_item,
    set_grocery_checked,
    delete_grocery_item,
    record_scan,
)
from food_detection import analyze_fridge


st.set_page_config(
    page_title="Fridge Scan",
    page_icon="🥑",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


# --------------------------------------------------
# PAGE STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@1,600&display=swap');

    :root {
        --green: #214333;
        --sage: #5b8468;
        --cream: #f7f8f4;
        --line: #e0e6dc;
        --muted: #78847b;
    }

    .stApp {
        background: var(--cream);
        color: #25362d;
        font-family: 'DM Sans', sans-serif;
    }

    .block-container {
        max-width: 1120px;
        padding: 2rem 1.5rem 4rem;
    }

    h1, h2, h3 {
        color: #25362d;
        letter-spacing: -0.035em;
    }

    h1 {
        font-size: clamp(2rem, 5vw, 3.6rem) !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] {
        background: #fff;
        border-right: 1px solid var(--line);
    }

    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 20px;
    }

    [data-testid="stMetricValue"] {
        color: var(--green);
        font-weight: 700;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 44px;
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid var(--line);
        transition: all 0.2s ease;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--green);
        color: white;
        border-color: var(--green);
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        border-color: var(--sage);
        color: var(--sage);
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff;
        border-color: var(--line);
        border-radius: 16px;
    }

    [data-testid="stFileUploader"] {
        background: #fff;
        border: 1px dashed #a8b9a8;
        border-radius: 14px;
        padding: 12px;
    }

    [data-testid="stImage"] img {
        border-radius: 12px;
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.8rem 2rem;
        }

        h1 {
            font-size: 2.1rem !important;
        }

        [data-testid="stMetric"] {
            padding: 12px;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.8rem;
        }

        .stButton > button,
        .stFormSubmitButton > button {
            width: 100%;
            min-height: 46px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SHARED HELPERS
# --------------------------------------------------

def title_block(title, subtitle):
    st.title(title)
    st.caption(subtitle)



def get_food_category(name):
    """Classify detected foods consistently."""
    import re

    food = " ".join(str(name).casefold().replace("&", " ").split())
    words = set(re.findall(r"[a-z]+", food))

    categories = {
        "Vegetables": {
            "tomato", "tomatoes", "pepper", "peppers", "carrot",
            "carrots", "cucumber", "cucumbers", "broccoli", "cabbage",
            "onion", "onions", "potato", "potatoes", "spinach",
            "lettuce", "cauliflower", "celery", "garlic", "ginger",
            "zucchini", "corn", "mushroom", "mushrooms", "eggplant",
            "beetroot", "radish", "peas", "beans",
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
        "Pantry": {
            "oil", "rice", "flour", "pasta", "bread", "salt",
            "sugar", "oats", "cereal", "noodles", "lentils", "grain",
            "quinoa", "spice", "spices",
        },
        "Condiments": {
            "pickle", "pickles", "ketchup", "mustard", "mayonnaise",
            "mayo", "sauce", "sauces", "dressing", "relish", "chutney",
        },
    }

    # Check complete names first, so "cherry tomatoes" are vegetables.
    if "tomato" in words or "tomatoes" in words:
        return "Vegetables"

    # "Bell pepper" is a vegetable; peppercorn is a pantry item.
    if "peppercorn" in words:
        return "Pantry"

    # Prefer meat over dairy, and use word matches for descriptive names.
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

def normalize_detected_inventory(raw_inventory):
    """
    Convert the AI response fields:
        item, quantity
    into the fields expected by the app and database:
        name, quantity_status, category, quantity, unit
    """
    normalized = []

    for item in raw_inventory:
        if not isinstance(item, dict):
            continue

        # Current AI response uses "item" and "quantity".
        # Also accept the app's normalized field names.
        name = item.get("name") or item.get("item")
        status = item.get("quantity_status") or item.get("quantity")

        if not isinstance(name, str) or not name.strip():
            continue

        if not isinstance(status, str):
            continue

        status = status.strip().title()

        if status not in {"Full", "Medium", "Low"}:
            continue

        name = " ".join(name.strip().split())

        normalized.append({
            "name": name,
            "quantity": 1,
            "unit": "item",
            "category": get_food_category(name),
            "quantity_status": status,
        })

    return normalized



def is_item_low_stock(item):
    """
    Use AI visual stock status for scanned foods.
    Use numeric quantity and threshold for manually managed items.
    """
    visual_status = item.get("visual_stock_status")

    if isinstance(visual_status, str):
        visual_status = visual_status.strip().title()

        if visual_status in {"Full", "Medium", "Low"}:
            return visual_status == "Low"

    return (
        float(item["quantity"])
        <= float(item["low_stock_threshold"])
    )


def show_inventory_summary(items):
    total = len(items)
    low = sum(is_item_low_stock(item) for item in items)
    available = total - low

    c1, c2, c3 = st.columns(3)
    c1.metric("Unique items", total)
    c2.metric("In stock", available)
    c3.metric("Low stock", low)

# --------------------------------------------------
# SCAN FRIDGE
# --------------------------------------------------

def scan_page():
    title_block(
        "🥑 Scan your fridge",
        "Upload photos or use your camera to keep track of what's inside.",
    )

    st.info(
        "Your photos are processed temporarily and are not saved as image "
        "files by this interface. Groq AI analyzes your photos to identify "
        "foods and suggest recipes."
    )

    uploaded = st.file_uploader(
        "Upload fridge photos (up to 8)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="fridge_uploads",
    )

    camera_image = st.camera_input(
        "Or take a photo of your fridge",
        key="fridge_camera",
    )

    image_bytes = [file.getvalue() for file in (uploaded or [])]

    if camera_image is not None:
        image_bytes.append(camera_image.getvalue())

    if len(image_bytes) > 8:
        st.error(
            "Please use at most 8 images in total, including the camera photo."
        )
        return

    if image_bytes:
        st.subheader(f"Photos selected: {len(image_bytes)}")
        columns = st.columns(min(4, len(image_bytes)))

        for index, data in enumerate(image_bytes):
            with columns[index % len(columns)]:
                st.image(
                    data,
                    caption=f"Photo {index + 1}",
                    width="stretch",
                )

    if st.button(
        "🔍 Analyze fridge",
        type="primary",
        disabled=not image_bytes,
    ):
        try:
            with st.spinner(
                "Groq AI is analyzing your photos and preparing recipes..."
            ):
                analysis = analyze_fridge(image_bytes)

                # IMPORTANT:
                # The AI returns {"item": ..., "quantity": ...}.
                # Convert it before displaying or saving to the database.
                detected = normalize_detected_inventory(
                    analysis.get("inventory", [])
                )

                suggested_recipes = analysis.get("suggested_recipes", [])
                low_stock_alerts = analysis.get("low_stock_alerts", [])

                if not detected:
                    raise RuntimeError(
                        "The AI response contained no valid food items. "
                        "Please try another photo."
                    )

                # Save normalized food records to the existing database.
                record_scan(detected)

                st.session_state["last_detected"] = detected
                st.session_state["last_suggested_recipes"] = suggested_recipes
                st.session_state["last_low_stock_alerts"] = low_stock_alerts

            st.success(
                f"AI scan completed. {len(detected)} food items were detected "
                "and the inventory was updated."
            )
            st.rerun()

        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"Could not analyze the photos: {error}")

        except Exception as error:
            st.error(
                f"An unexpected error occurred during the scan: {error}"
            )

    detected = st.session_state.get("last_detected", [])

    if detected:
        st.subheader("Latest scan results")

        for item in detected:
            name = item.get("name", "Unknown food")
            status = item.get("quantity_status", "Not specified")
            category = item.get("category", "Other")

            st.write(f"**{name}** — {category} · Stock: {status}")

    alerts = st.session_state.get("last_low_stock_alerts", [])

    if alerts:
        st.subheader("Low-stock alerts")

        for alert in alerts:
            if isinstance(alert, dict):
                name = alert.get("name") or alert.get("item", "Food item")
                message = alert.get("message", "Stock is running low.")
                st.warning(f"**{name}:** {message}")
            else:
                st.warning(f"**{alert}**: Stock is running low.")


# --------------------------------------------------
# INVENTORY
# --------------------------------------------------

def inventory_page():
    title_block(
        "🧊 Fridge inventory",
        "Track quantities, update food details, and monitor low-stock items.",
    )

    items = get_inventory()
    show_inventory_summary(items)

    with st.expander("➕ Add an inventory item", expanded=False):
        with st.form("add_inventory_form"):
            name = st.text_input("Food name")

            c1, c2 = st.columns(2)

            quantity = c1.number_input(
                "Quantity",
                min_value=0.0,
                value=1.0,
            )

            unit = c2.selectbox(
                "Unit",
                [
                    "item", "items", "pack", "carton",
                    "bottle", "kg", "g", "litre",
                ],
            )

            category = st.selectbox(
                "Category",
                [
                    "Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                    "Meat", "Meat & Seafood", "Pantry",
                    "Condiments", "Other",
                ],
            )

            threshold = st.number_input(
                "Low-stock threshold",
                min_value=0.0,
                value=1.0,
            )

            submitted = st.form_submit_button("Add item")

            if submitted:
                try:
                    add_inventory_item(
                        name,
                        quantity,
                        unit,
                        category,
                        threshold,
                    )
                    st.success("Inventory item saved.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not save item: {error}")

    items = get_inventory()

    if not items:
        st.info("Your inventory is empty. Add an item or scan your fridge.")
        return

    st.subheader("Your food")

    for item in items:
        is_low = is_item_low_stock(item)
        visual_status = item.get("visual_stock_status")

        with st.container(border=True):
            left, middle, right = st.columns([3, 2, 1])

            left.markdown(f"**{item['name']}**")
            left.caption(item["category"])

            middle.write(f"{item['quantity']:g} {item['unit']}")

            if visual_status in {"Full", "Medium", "Low"}:
                if visual_status == "Low":
                    middle.warning("Visual stock: Low")
                else:
                    middle.caption(f"Visual stock: {visual_status}")
            elif is_low:
                middle.warning("Low stock")
            else:
                middle.caption("In stock")

            if right.button("Edit", key=f"edit_inventory_{item['id']}"):
                st.session_state["editing_inventory_id"] = item["id"]

            if right.button("Delete", key=f"delete_inventory_{item['id']}"):
                delete_inventory_item(item["id"])
                st.rerun()

        if st.session_state.get("editing_inventory_id") == item["id"]:
            with st.form(f"edit_form_{item['id']}"):
                new_name = st.text_input(
                    "Food name",
                    value=item["name"],
                )

                units = [
                    "item", "items", "pack", "carton",
                    "bottle", "kg", "g", "litre",
                ]

                categories = [
                    "Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                    "Meat", "Meat & Seafood", "Pantry",
                    "Condiments", "Other",
                ]

                c1, c2 = st.columns(2)

                new_quantity = c1.number_input(
                    "Quantity",
                    min_value=0.0,
                    value=float(item["quantity"]),
                    key=f"qty_{item['id']}",
                )

                new_unit = c2.selectbox(
                    "Unit",
                    units,
                    index=units.index(item["unit"]) if item["unit"] in units else 0,
                    key=f"unit_{item['id']}",
                )

                new_category = st.selectbox(
                    "Category",
                    categories,
                    index=(
                        categories.index(item["category"])
                        if item["category"] in categories
                        else categories.index("Other")
                    ),
                    key=f"category_{item['id']}",
                )

                new_threshold = st.number_input(
                    "Low-stock threshold",
                    min_value=0.0,
                    value=float(item["low_stock_threshold"]),
                    key=f"threshold_{item['id']}",
                )

                save = st.form_submit_button("Save changes")
                cancel = st.form_submit_button("Cancel")

                if save:
                    try:
                        update_inventory_item(
                            item["id"],
                            new_name,
                            new_quantity,
                            new_unit,
                            new_category,
                            new_threshold,
                        )
                        del st.session_state["editing_inventory_id"]
                        st.success("Item updated.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not update item: {error}")

                if cancel:
                    del st.session_state["editing_inventory_id"]
                    st.rerun()


# --------------------------------------------------
# GROCERY LIST
# --------------------------------------------------

def grocery_page():
    title_block(
        "🛒 Grocery list",
        "Items running low are added automatically. You can also add items manually.",
    )

    with st.form("add_grocery_form"):
        name = st.text_input("Add a grocery item")

        c1, c2 = st.columns(2)

        quantity = c1.number_input(
            "Quantity",
            min_value=0.1,
            value=1.0,
            step=1.0,
        )

        unit = c2.selectbox(
            "Unit",
            [
                "item", "items", "pack", "carton",
                "bottle", "kg", "g", "litre",
            ],
        )

        submitted = st.form_submit_button("Add to list")

        if submitted:
            try:
                add_grocery_item(name, quantity, unit)
                st.success("Added to your grocery list.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    items = get_grocery_items()

    if not items:
        st.info("Your grocery list is empty.")
        return

    pending = sum(not item["checked"] for item in items)
    st.metric("Items left to buy", pending)

    for item in items:
        c1, c2, c3 = st.columns([5, 2, 1])

        checked = c1.checkbox(
            item["name"],
            value=bool(item["checked"]),
            key=f"grocery_check_{item['id']}",
        )

        c2.write(f"{item['quantity']:g} {item['unit']}")

        if checked != bool(item["checked"]):
            set_grocery_checked(item["id"], checked)
            st.rerun()

        if item["source"] == "low_stock":
            c1.caption("Automatically added from low stock")

        if c3.button("✕", key=f"delete_grocery_{item['id']}"):
            delete_grocery_item(item["id"])
            st.rerun()


# --------------------------------------------------
# RECIPES
# --------------------------------------------------

def recipes_page():
    title_block(
        "🍳 Recipes for your fridge",
        "Explore AI-generated meals based on the foods detected in your fridge.",
    )

    recipes = st.session_state.get("last_suggested_recipes", [])

    if not recipes:
        st.info(
            "No AI recipes are available yet. Open Scan Fridge, upload "
            "your photos, and select Analyze fridge to generate recipes."
        )
        return

    for index, recipe in enumerate(recipes):
        name = recipe.get("name", f"Recipe {index + 1}")
        used_ingredients = recipe.get("used_ingredients", [])
        missing_ingredients = recipe.get(
            "additional_ingredients_needed",
            [],
        )
        instructions = recipe.get("instructions", [])

        with st.container(border=True):
            st.subheader(name)

            description = recipe.get("description", "")
            if description:
                st.write(description)

            with st.expander("Ingredients and instructions", expanded=True):
                st.markdown("**Ingredients you have**")

                if used_ingredients:
                    for ingredient in used_ingredients:
                        st.write(f"✓ {ingredient}")
                else:
                    st.write("No available ingredients were listed.")

                st.markdown("**Missing ingredients**")

                if missing_ingredients:
                    for ingredient in missing_ingredients:
                        st.write(f"• {ingredient}")

                    if st.button(
                        "Add missing ingredients to grocery list",
                        key=f"missing_{index}_{name}",
                    ):
                        added_count = 0

                        for ingredient in missing_ingredients:
                            try:
                                add_grocery_item(ingredient)
                                added_count += 1
                            except ValueError as error:
                                st.warning(
                                    f"Could not add {ingredient}: {error}"
                                )

                        if added_count:
                            st.success(
                                f"Added {added_count} ingredient(s) "
                                "to your grocery list."
                            )
                            st.rerun()
                else:
                    st.success("You have all the listed ingredients!")

                st.markdown("**Instructions**")

                if instructions:
                    for step_number, instruction in enumerate(
                        instructions,
                        start=1,
                    ):
                        st.write(f"{step_number}. {instruction}")
                else:
                    st.write("No cooking instructions were provided.")


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

st.sidebar.title("🥑 Fridge Scan")
st.sidebar.caption("Your kitchen, organized.")

page = st.sidebar.radio(
    "Navigate",
    ["Scan Fridge", "Inventory", "Grocery List", "Recipes"],
)

if page == "Scan Fridge":
    scan_page()
elif page == "Inventory":
    inventory_page()
elif page == "Grocery List":
    grocery_page()
else:
    recipes_page()

st.sidebar.divider()
st.sidebar.caption("Local prototype · Groq AI food analysis")
