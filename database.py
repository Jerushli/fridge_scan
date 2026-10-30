import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "fridge_scan.db"

VALID_STOCK_STATUSES = {"Full", "Medium", "Low"}
def normalize_food_name(name):
    """Normalize simple singular/plural food-name variations."""
    name = " ".join(name.casefold().strip().split())

    # Handle common irregular plurals and special cases.
    irregular = {
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
    }

    if name in irregular:
        return irregular[name]

    # Only normalize single-word names. Keep descriptive names
    # such as "red apple" and "ham slices" unchanged.
    if " " in name:
        return name

    if name.endswith("ies") and len(name) > 4:
        return name[:-3] + "y"

    if name.endswith(("ches", "shes", "xes", "zes", "sses")):
        return name[:-2]

    if name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        return name[:-1]

    return name

def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS fridge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT NOT NULL DEFAULT 'item',
                category TEXT NOT NULL DEFAULT 'Other',
                low_stock_threshold REAL NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS grocery_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT NOT NULL DEFAULT 'item',
                checked INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS recipe_suggestions (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                recipes_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Safely upgrade databases created by earlier versions.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(fridge_items)"
            ).fetchall()
        }

        if "visual_stock_status" not in columns:
            connection.execute("""
                ALTER TABLE fridge_items
                ADD COLUMN visual_stock_status TEXT
            """)


def get_inventory():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM fridge_items ORDER BY name
        """).fetchall()
        return [dict(row) for row in rows]


def add_inventory_item(
    name,
    quantity=1,
    unit="item",
    category="Other",
    low_stock_threshold=1,
):
    name = name.strip()
    if not name:
        raise ValueError("Item name cannot be empty.")

    if quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Quantity and threshold cannot be negative.")

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO fridge_items
                (name, quantity, unit, category, low_stock_threshold)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                quantity = excluded.quantity,
                unit = excluded.unit,
                category = CASE
                    WHEN excluded.category != 'Other'
                    THEN excluded.category
                    ELSE fridge_items.category
                END,
                low_stock_threshold = excluded.low_stock_threshold,
                updated_at = CURRENT_TIMESTAMP
        """, (
            name,
            quantity,
            unit,
            category,
            low_stock_threshold,
        ))

    sync_low_stock_items()

def update_inventory_item(
    item_id,
    name,
    quantity,
    unit,
    category,
    low_stock_threshold,
):
    name = name.strip()
    if not name:
        raise ValueError("Item name cannot be empty.")

    if quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Quantity and threshold cannot be negative.")

    with get_connection() as connection:
        connection.execute("""
            UPDATE fridge_items
            SET name = ?,
                quantity = ?,
                unit = ?,
                category = ?,
                low_stock_threshold = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            name,
            quantity,
            unit,
            category,
            low_stock_threshold,
            item_id,
        ))

    sync_low_stock_items()
def update_inventory_quantity_unit(item_id, quantity, unit):
    unit = unit.strip()

    if quantity <= 0:
        raise ValueError("Inventory quantity must be greater than zero.")

    if not unit:
        raise ValueError("Inventory unit cannot be empty.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE fridge_items
            SET quantity = ?,
                unit = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (quantity, unit, item_id))

        if cursor.rowcount == 0:
            raise ValueError("Inventory item not found.")

        row = connection.execute("""
            SELECT *
            FROM fridge_items
            WHERE id = ?
        """, (item_id,)).fetchone()

        return dict(row)

def delete_inventory_item(item_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM fridge_items WHERE id = ?",
            (item_id,),
        )

    sync_low_stock_items()



def sync_low_stock_items():
    """
    Automatically add inventory items explicitly assessed as Low.

    Items assessed as Medium or Full are not added.
    Items without a visual stock assessment are not added automatically.
    Manually added grocery entries are preserved.
    """
    with get_connection() as connection:
        low_items = connection.execute("""
            SELECT name, low_stock_threshold
            FROM fridge_items
            WHERE visual_stock_status = 'Low'
        """).fetchall()

        for item in low_items:
            connection.execute("""
                INSERT INTO grocery_items
                    (name, quantity, source)
                VALUES (?, ?, 'low_stock')
                ON CONFLICT(name) DO NOTHING
            """, (
                item["name"],
                max(1, item["low_stock_threshold"]),
            ))

        # Remove automatically generated entries for inventory items
        # that are no longer explicitly assessed as Low.
        # Preserve manually added grocery entries.
        connection.execute("""
            DELETE FROM grocery_items
            WHERE source = 'low_stock'
              AND EXISTS (
                  SELECT 1
                  FROM fridge_items
                  WHERE fridge_items.name = grocery_items.name
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM fridge_items
                  WHERE fridge_items.name = grocery_items.name
                    AND visual_stock_status = 'Low'
              )
        """)


def get_grocery_items():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM grocery_items
            ORDER BY checked ASC, name ASC
        """).fetchall()
        return [dict(row) for row in rows]

def add_grocery_item(name, quantity=1, unit="item"):
    name = name.strip()
    unit = unit.strip()

    if not name:
        raise ValueError("Grocery item name cannot be empty.")

    if not unit:
        raise ValueError("Grocery unit cannot be empty.")

    if quantity <= 0:
        raise ValueError("Grocery quantity must be greater than zero.")

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO grocery_items (name, quantity, unit, source)
            VALUES (?, ?, ?, 'manual')
            ON CONFLICT(name) DO UPDATE SET
                quantity = grocery_items.quantity + excluded.quantity,
                unit = excluded.unit
        """, (name, quantity, unit))

        row = connection.execute("""
            SELECT *
            FROM grocery_items
            WHERE name = ?
        """, (name,)).fetchone()

        return dict(row)
def set_grocery_checked(item_id, checked):
    with get_connection() as connection:
        connection.execute("""
            UPDATE grocery_items
            SET checked = ?
            WHERE id = ?
        """, (int(bool(checked)), item_id))

def update_grocery_item(item_id, quantity, unit):
    unit = unit.strip()

    if quantity <= 0:
        raise ValueError("Grocery quantity must be greater than zero.")

    if not unit:
        raise ValueError("Grocery unit cannot be empty.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE grocery_items
            SET quantity = ?, unit = ?
            WHERE id = ?
        """, (quantity, unit, item_id))

        if cursor.rowcount == 0:
            raise ValueError("Grocery item not found.")

        row = connection.execute("""
            SELECT *
            FROM grocery_items
            WHERE id = ?
        """, (item_id,)).fetchone()

        return dict(row)
def update_inventory_item(item_id, quantity, unit):
    unit = unit.strip()

    if quantity <= 0:
        raise ValueError("Inventory quantity must be greater than zero.")

    if not unit:
        raise ValueError("Inventory unit cannot be empty.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE inventory
            SET quantity = ?, unit = ?
            WHERE id = ?
        """, (quantity, unit, item_id))

        if cursor.rowcount == 0:
            raise ValueError("Inventory item not found.")

        row = connection.execute("""
            SELECT *
            FROM inventory
            WHERE id = ?
        """, (item_id,)).fetchone()

        return dict(row)

def delete_grocery_item(item_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM grocery_items WHERE id = ?",
            (item_id,),
        )



def record_scan(item_names):
    """
    Record scan metadata and synchronize detected foods.

    Match simple singular/plural variations to existing items.
    Preserve existing numeric quantities and update visual status.
    Uploaded photos are never saved.
    """
    prepared_items = []

    for item in item_names:
        if isinstance(item, str):
            food = {
                "name": item.strip(),
                "category": "Other",
                "quantity": 1,
                "unit": "item",
                "quantity_status": None,
            }
        elif isinstance(item, dict):
            food = {
                "name": str(item.get("name", "")).strip(),
                "category": str(item.get("category") or "Other").strip(),
                "quantity": item.get("quantity", 1),
                "unit": str(item.get("unit") or "item").strip(),
                "quantity_status": item.get("quantity_status"),
            }
        else:
            continue

        if not food["name"]:
            continue

        if food["quantity_status"] not in VALID_STOCK_STATUSES:
            food["quantity_status"] = None

        prepared_items.append(food)

    with get_connection() as connection:
        # Build a lookup of existing names, including items added
        # earlier in this same scan.
        existing = connection.execute(
            "SELECT id, name FROM fridge_items"
        ).fetchall()

        name_lookup = {
            normalize_food_name(row["name"]): row["name"]
            for row in existing
        }

        # Prevent duplicate entries within a single scan too.
        scan_items = {}

        for food in prepared_items:
            normalized = normalize_food_name(food["name"])
            canonical_name = name_lookup.get(normalized, food["name"])

            if canonical_name in scan_items:
                previous = scan_items[canonical_name]

                # Prefer a valid visual status; Low takes priority
                # so an alert isn't accidentally lost.
                statuses = {
                    previous["quantity_status"],
                    food["quantity_status"],
                }
                previous["quantity_status"] = (
                    "Low" if "Low" in statuses
                    else "Medium" if "Medium" in statuses
                    else "Full" if "Full" in statuses
                    else None
                )

                if previous["category"] == "Other":
                    previous["category"] = food["category"]
                continue

            food["name"] = canonical_name
            scan_items[canonical_name] = food
            name_lookup[normalized] = canonical_name

        connection.execute(
            "INSERT INTO scans (item_count) VALUES (?)",
            (len(scan_items),),
        )

        for food in scan_items.values():
            connection.execute(
                """
                INSERT INTO fridge_items
                    (name, quantity, unit, category, visual_stock_status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    category = CASE
                        WHEN excluded.category != 'Other'
                        THEN excluded.category
                        ELSE fridge_items.category
                    END,
                    visual_stock_status = excluded.visual_stock_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    food["name"],
                    food["quantity"],
                    food["unit"],
                    food["category"],
                    food["quantity_status"],
                ),
            )

    sync_low_stock_items()
def save_recipe_suggestions(recipes):
    """Save the latest AI-generated recipe suggestions."""
    if not isinstance(recipes, list):
        recipes = []

    recipes_json = json.dumps(recipes)

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO recipe_suggestions (id, recipes_json)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                recipes_json = excluded.recipes_json,
                updated_at = CURRENT_TIMESTAMP
        """, (recipes_json,))


def get_recipe_suggestions():
    """Return the latest saved AI-generated recipes."""
    with get_connection() as connection:
        row = connection.execute("""
            SELECT recipes_json
            FROM recipe_suggestions
            WHERE id = 1
        """).fetchone()

    if not row:
        return []

    try:
        recipes = json.loads(row["recipes_json"])
        return recipes if isinstance(recipes, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def sync_recipe_groceries(recipes):
    """
    Add ingredients missing from the latest AI recipes.

    Preserve manual and low-stock grocery entries.
    Remove outdated, unchecked recipe-generated entries.
    """
    missing_names = {}

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue

        ingredients = recipe.get("additional_ingredients_needed", [])

        if not isinstance(ingredients, list):
            continue

        for ingredient in ingredients:
            if not isinstance(ingredient, str):
                continue

            name = ingredient.strip()
            if name:
                missing_names[name.casefold()] = name

    with get_connection() as connection:
        # Remove outdated recipe-generated items only if they
        # have not already been checked off.
        existing_recipe_items = connection.execute("""
            SELECT id, name
            FROM grocery_items
            WHERE source = 'recipe' AND checked = 0
        """).fetchall()

        current_names = set(missing_names.keys())

        for item in existing_recipe_items:
            if item["name"].casefold() not in current_names:
                connection.execute(
                    "DELETE FROM grocery_items WHERE id = ?",
                    (item["id"],),
                )

        # Add missing ingredients without duplicating existing
        # manual, low-stock, or recipe grocery entries.
        for name in missing_names.values():
            connection.execute("""
                INSERT INTO grocery_items
                    (name, quantity, unit, source)
                VALUES (?, 1, 'item', 'recipe')
                ON CONFLICT(name) DO NOTHING
            """, (name,))
