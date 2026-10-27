
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
from food_detection import detect_foods
from recipes import recommend_recipes


st.set_page_config(
    page_title="Fridge Scan",
    page_icon="🥑",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

st.markdown("""

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

""", unsafe_allow_html=True)


def title_block(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def show_inventory_summary(items):
    total = len(items)
    low = sum(
        item["quantity"] <= item["low_stock_threshold"]
        for item in items
    )
    available = total - low

    c1, c2, c3 = st.columns(3)
    c1.metric("Unique items", total)
    c2.metric("In stock", available)
    c3.metric("Low stock", low)


def scan_page():
    title_block(
        "🥑 Scan your fridge",
        "Upload photos or use your camera to keep track of what's inside.",
    )

    st.info(
        "Privacy: photos are processed temporarily. "
        "This app does not save uploaded image files. "
        "Food recognition is currently a demo and does not truly identify "
        "items in your photos."
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

    image_bytes = [file.getvalue() for file in uploaded]
    if camera_image is not None:
        image_bytes.append(camera_image.getvalue())

    if len(image_bytes) > 8:
        st.error("Please use at most 8 images in total, including the camera photo.")
        return

    if image_bytes:
        st.subheader(f"Photos selected: {len(image_bytes)}")
        columns = st.columns(min(4, len(image_bytes)))
        for index, data in enumerate(image_bytes):
            with columns[index % len(columns)]:
                st.image(data, caption=f"Photo {index + 1}", use_container_width=True)

    if st.button("🔍 Analyze fridge", type="primary", disabled=not image_bytes):
        try:
            with st.spinner("Analyzing your photos..."):
                detected = detect_foods(image_bytes)
                record_scan([item["name"] for item in detected])

            st.session_state["last_detected"] = detected
            st.success(
                f"Demo scan complete. {len(detected)} sample food items "
                "were added to your inventory."
            )
            st.rerun()
        except (ValueError, OSError) as error:
            st.error(str(error))

    detected = st.session_state.get("last_detected", [])
    if detected:
        st.subheader("Latest scan results")
        st.caption("These are sample results, not AI-verified detections.")
        for item in detected:
            st.write(
                f"**{item['name']}** — {item['quantity']} "
                f"{item['unit']} · {item['category']}"
            )


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
            quantity = c1.number_input("Quantity", min_value=0.0, value=1.0)
            unit = c2.selectbox(
                "Unit",
                ["item", "items", "pack", "carton", "bottle", "kg", "g", "litre"],
            )
            category = st.selectbox(
                "Category",
                ["Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                 "Meat", "Pantry", "Other"],
            )
            threshold = st.number_input(
                "Low-stock threshold", min_value=0.0, value=1.0
            )
            submitted = st.form_submit_button("Add item")

            if submitted:
                try:
                    add_inventory_item(name, quantity, unit, category, threshold)
                    st.success("Inventory item saved.")
                    st.rerun()
                except (ValueError, Exception) as error:
                    st.error(f"Could not save item: {error}")

    items = get_inventory()
    if not items:
        st.info("Your inventory is empty. Add an item or scan your fridge.")
        return

    st.subheader("Your food")
    for item in items:
        is_low = item["quantity"] <= item["low_stock_threshold"]
        with st.container(border=True):
            left, middle, right = st.columns([3, 2, 1])

            left.markdown(f"**{item['name']}**")
            left.caption(item["category"])
            middle.write(f"{item['quantity']:g} {item['unit']}")
            if is_low:
                middle.warning("Low stock")
            else:
                middle.caption("In stock")

            edit_key = f"edit_inventory_{item['id']}"
            delete_key = f"delete_inventory_{item['id']}"

            if right.button("Edit", key=edit_key):
                st.session_state["editing_inventory_id"] = item["id"]

            if right.button("Delete", key=delete_key):
                delete_inventory_item(item["id"])
                st.rerun()

        if st.session_state.get("editing_inventory_id") == item["id"]:
            with st.form(f"edit_form_{item['id']}"):
                new_name = st.text_input("Food name", value=item["name"])
                c1, c2 = st.columns(2)
                new_quantity = c1.number_input(
                    "Quantity", min_value=0.0, value=float(item["quantity"]),
                    key=f"qty_{item['id']}"
                )
                new_unit = c2.selectbox(
                    "Unit",
                    ["item", "items", "pack", "carton", "bottle", "kg", "g", "litre"],
                    index=(
                        ["item", "items", "pack", "carton", "bottle", "kg", "g", "litre"]
                        .index(item["unit"])
                        if item["unit"] in
                        ["item", "items", "pack", "carton", "bottle", "kg", "g", "litre"]
                        else 0
                    ),
                    key=f"unit_{item['id']}",
                )
                new_category = st.selectbox(
                    "Category",
                    ["Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                     "Meat", "Pantry", "Other"],
                    index=(
                        ["Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                         "Meat", "Pantry", "Other"].index(item["category"])
                        if item["category"] in
                        ["Dairy", "Dairy & Eggs", "Vegetables", "Fruits",
                         "Meat", "Pantry", "Other"] else 6
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
                            item["id"], new_name, new_quantity, new_unit,
                            new_category, new_threshold
                        )
                        del st.session_state["editing_inventory_id"]
                        st.success("Item updated.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not update item: {error}")

                if cancel:
                    del st.session_state["editing_inventory_id"]
                    st.rerun()


def grocery_page():
    title_block(
        "🛒 Grocery list",
        "Items running low are added automatically. You can also add items manually.",
    )

    with st.form("add_grocery_form"):
        name = st.text_input("Add a grocery item")
        c1, c2 = st.columns(2)
        quantity = c1.number_input(
            "Quantity", min_value=0.1, value=1.0, step=1.0
        )
        unit = c2.selectbox(
            "Unit",
            ["item", "items", "pack", "carton", "bottle", "kg", "g", "litre"],
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


def recipes_page():
    title_block(
        "🍳 Recipes for your fridge",
        "Find meals you can make and see what you need to buy.",
    )

    inventory_names = [item["name"] for item in get_inventory()]
    if not inventory_names:
        st.info("Add food to your inventory to get recipe recommendations.")
        return

    recipes = recommend_recipes(inventory_names)

    for recipe in recipes:
        with st.container(border=True):
            st.subheader(recipe["name"])
            st.caption(
                f"{recipe['time']} minutes · {recipe['servings']} serving(s) "
                f"· {recipe['match_percent']}% ingredient match"
            )
            st.write(recipe["description"])
            st.progress(recipe["match_percent"] / 100)

            with st.expander("Ingredients and instructions"):
                st.markdown("**Ingredients you have**")
                if recipe["available_ingredients"]:
                    for ingredient in recipe["available_ingredients"]:
                        st.write(f"✓ {ingredient}")
                else:
                    st.write("None yet")

                st.markdown("**Missing ingredients**")
                if recipe["missing_ingredients"]:
                    for ingredient in recipe["missing_ingredients"]:
                        st.write(f"• {ingredient}")

                    if st.button(
                        "Add missing ingredients to grocery list",
                        key=f"missing_{recipe['name']}",
                    ):
                        for ingredient in recipe["missing_ingredients"]:
                            add_grocery_item(ingredient)
                        st.success("Missing ingredients added to your list.")
                        st.rerun()
                else:
                    st.success("You have all the listed ingredients!")

                st.markdown("**Instructions**")
                for step_number, instruction in enumerate(
                    recipe["instructions"], start=1
                ):
                    st.write(f"{step_number}. {instruction}")


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
st.sidebar.caption("Local prototype · Demo food detection")
