
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "fridge_scan.db"


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

            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)


def get_inventory():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM fridge_items ORDER BY name
        """).fetchall()
        return [dict(row) for row in rows]


def add_inventory_item(
    name, quantity=1, unit="item", category="Other",
    low_stock_threshold=1
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
                category = excluded.category,
                low_stock_threshold = excluded.low_stock_threshold,
                updated_at = CURRENT_TIMESTAMP
        """, (name, quantity, unit, category, low_stock_threshold))

    sync_low_stock_items()


def update_inventory_item(
    item_id, name, quantity, unit, category, low_stock_threshold
):
    name = name.strip()
    if not name:
        raise ValueError("Item name cannot be empty.")
    if quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Quantity and threshold cannot be negative.")

    with get_connection() as connection:
        connection.execute("""
            UPDATE fridge_items
            SET name = ?, quantity = ?, unit = ?, category = ?,
                low_stock_threshold = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            name, quantity, unit, category, low_stock_threshold, item_id
        ))

    sync_low_stock_items()


def delete_inventory_item(item_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM fridge_items WHERE id = ?", (item_id,)
        )


def sync_low_stock_items():
    """Add low-stock products to the grocery list automatically."""
    with get_connection() as connection:
        low_items = connection.execute("""
            SELECT name, low_stock_threshold
            FROM fridge_items
            WHERE quantity <= low_stock_threshold
        """).fetchall()

        for item in low_items:
            connection.execute("""
                INSERT INTO grocery_items
                    (name, quantity, source)
                VALUES (?, ?, 'low_stock')
                ON CONFLICT(name) DO NOTHING
            """, (
                item["name"],
                max(1, item["low_stock_threshold"])
            ))


def get_grocery_items():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM grocery_items
            ORDER BY checked ASC, name ASC
        """).fetchall()
        return [dict(row) for row in rows]


def add_grocery_item(name, quantity=1, unit="item"):
    name = name.strip()
    if not name:
        raise ValueError("Grocery item name cannot be empty.")
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


def set_grocery_checked(item_id, checked):
    with get_connection() as connection:
        connection.execute("""
            UPDATE grocery_items SET checked = ?
            WHERE id = ?
        """, (int(checked), item_id))


def delete_grocery_item(item_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM grocery_items WHERE id = ?", (item_id,)
        )


def record_scan(item_names):
    """Record scan metadata only; never save the uploaded photo."""
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO scans (item_count) VALUES (?)",
            (len(item_names),)
        )

        for name in item_names:
            name = name.strip()
            if not name:
                continue

            connection.execute("""
                INSERT INTO fridge_items (name)
                VALUES (?)
                ON CONFLICT(name) DO NOTHING
            """, (name,))

    sync_low_stock_items()
