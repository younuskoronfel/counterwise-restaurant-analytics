"""SQLite operations for Counterwise. Only standard-library modules are used."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "counterwise.db"


class InventoryError(ValueError):
    """An order cannot be fulfilled with the inventory available."""


def db_path() -> Path:
    return Path(os.environ.get("COUNTERWISE_DB", DEFAULT_DB))


@contextmanager
def connect(path: Path | str | None = None):
    path = Path(path) if path is not None else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def initialize(path: Path | str | None = None) -> None:
    """Create the database and synthetic demo records on first run."""
    with connect(path) as conn:
        conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        if conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]:
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executemany(
                "INSERT INTO ingredients(name,unit,quantity_on_hand,unit_cost_cents,reorder_level) VALUES (?,?,?,?,?)",
                [
                    ("Dough", "portions", 150, 110, 25),
                    ("Tomato sauce", "portions", 160, 45, 25),
                    ("Mozzarella", "portions", 150, 90, 25),
                    ("Pepperoni", "portions", 95, 130, 18),
                    ("Vegetable mix", "portions", 85, 85, 18),
                    ("Fresh basil", "portions", 65, 20, 12),
                ],
            )
            conn.executemany(
                "INSERT INTO menu_items(name, price_cents) VALUES (?, ?)",
                [("Margherita Pizza", 1450), ("Pepperoni Pizza", 1700),
                 ("Garden Pizza", 1600), ("Garlic Bread", 850)],
            )
            conn.executemany(
                "INSERT INTO recipes(menu_item_id,ingredient_id,units_required) VALUES (?,?,?)",
                [(1,1,1),(1,2,1),(1,3,1),(1,6,1),
                 (2,1,1),(2,2,1),(2,3,1),(2,4,1),
                 (3,1,1),(3,2,1),(3,3,1),(3,5,1),
                 (4,1,1),(4,3,1)],
            )
            # Deterministic product choices and quantities, but dates are recent.
            # All data is invented for a demo, NOT from a real restaurant.
            now = datetime.now(timezone.utc)
            for days_ago in reversed(range(10)):
                for i in range(3 + (days_ago % 2)):
                    menu_id = (days_ago * 3 + i * 2) % 4 + 1
                    quantity = 1 + (i % 2)
                    sold_at = (now - timedelta(days=days_ago, hours=8-i)).isoformat(timespec="seconds")
                    _place_order(conn, menu_id, quantity, sold_at)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _place_order(conn: sqlite3.Connection, menu_id: int, quantity: int, when: str) -> int:
    """Internal helper; caller already holds a write transaction."""
    if not 1 <= quantity <= 20:
        raise ValueError("Quantity must be between 1 and 20.")
    menu = conn.execute(
        "SELECT * FROM menu_items WHERE id = ? AND active = 1", (menu_id,)
    ).fetchone()
    if menu is None:
        raise ValueError("Choose an available menu item.")

    requirements = conn.execute("""
        SELECT i.id, i.name, i.quantity_on_hand, i.unit_cost_cents, r.units_required
        FROM recipes r JOIN ingredients i ON r.ingredient_id = i.id
        WHERE r.menu_item_id = ?
    """, (menu_id,)).fetchall()
    if not requirements:
        raise ValueError("This menu item does not have a recipe.")

    for ingredient in requirements:
        needed = ingredient["units_required"] * quantity
        if needed > ingredient["quantity_on_hand"]:
            raise InventoryError(
                f"Not enough {ingredient['name']}: need {needed}, "
                f"have {ingredient['quantity_on_hand']}."
            )

    # Food cost is recorded at the time of sale, so later cost changes
    # do not rewrite the economics of past orders.
    unit_food_cost = sum(i["unit_cost_cents"] * i["units_required"] for i in requirements)
    order_id = conn.execute("INSERT INTO orders(created_at) VALUES (?)", (when,)).lastrowid
    conn.execute("""
        INSERT INTO order_items(order_id,menu_item_id,quantity,unit_price_cents,unit_food_cost_cents)
        VALUES (?,?,?,?,?)
    """, (order_id, menu_id, quantity, menu["price_cents"], unit_food_cost))
    for ingredient in requirements:
        used = ingredient["units_required"] * quantity
        conn.execute(
            "UPDATE ingredients SET quantity_on_hand = quantity_on_hand - ? WHERE id = ?",
            (used, ingredient["id"]),
        )
        conn.execute("""
            INSERT INTO inventory_movements(ingredient_id,order_id,delta_units,reason,created_at)
            VALUES (?,?,?,'sale',?)
        """, (ingredient["id"], order_id, -used, when))
    return order_id


def place_order(menu_id: int, quantity: int, path: Path | str | None = None) -> int:
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            order_id = _place_order(conn, menu_id, quantity,
                                    datetime.now(timezone.utc).isoformat(timespec="seconds"))
            conn.commit()
            return order_id
        except Exception:
            conn.rollback()
            raise


def restock(ingredient_id: int, quantity: int, path: Path | str | None = None) -> None:
    if not 1 <= quantity <= 10000:
        raise ValueError("Restock quantity must be between 1 and 10,000.")
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            updated = conn.execute(
                "UPDATE ingredients SET quantity_on_hand = quantity_on_hand + ? WHERE id = ?",
                (quantity, ingredient_id),
            )
            if updated.rowcount == 0:
                raise ValueError("Choose a valid ingredient.")
            conn.execute("""
                INSERT INTO inventory_movements(ingredient_id,delta_units,reason,created_at)
                VALUES (?,?,'restock',?)
            """, (ingredient_id, quantity, datetime.now(timezone.utc).isoformat(timespec="seconds")))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def dashboard(path: Path | str | None = None) -> dict:
    with connect(path) as conn:
        totals = dict(conn.execute("""
            SELECT COUNT(DISTINCT o.id) AS orders,
                   COALESCE(SUM(oi.quantity * oi.unit_price_cents),0) AS revenue_cents,
                   COALESCE(SUM(oi.quantity * oi.unit_food_cost_cents),0) AS food_cost_cents
            FROM orders o JOIN order_items oi ON o.id = oi.order_id
        """).fetchone())
        days = [dict(r) for r in conn.execute("""
            SELECT SUBSTR(o.created_at,1,10) AS day,
                   SUM(oi.quantity * oi.unit_price_cents) AS sales_cents
            FROM orders o JOIN order_items oi ON o.id = oi.order_id
            GROUP BY SUBSTR(o.created_at,1,10) ORDER BY day DESC LIMIT 10
        """).fetchall()][::-1]
        popular = [dict(r) for r in conn.execute("""
            SELECT m.name, SUM(oi.quantity) AS units,
                   SUM(oi.quantity * oi.unit_price_cents) AS sales_cents
            FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id
            GROUP BY m.id ORDER BY units DESC, m.name LIMIT 4
        """)]
        inventory = [dict(r) for r in conn.execute(
            "SELECT * FROM ingredients ORDER BY quantity_on_hand ASC, name"
        )]
        menu = [dict(r) for r in conn.execute(
            "SELECT * FROM menu_items WHERE active = 1 ORDER BY name"
        )]
        recent = [dict(r) for r in conn.execute("""
            SELECT o.id, o.created_at, m.name, oi.quantity,
                   (oi.unit_price_cents * oi.quantity) AS total_cents
            FROM orders o JOIN order_items oi ON o.id = oi.order_id
            JOIN menu_items m ON m.id = oi.menu_item_id
            ORDER BY o.created_at DESC, o.id DESC LIMIT 7
        """)]
    return dict(totals=totals, days=days, popular=popular, inventory=inventory, menu=menu, recent=recent)


def export_rows(path: Path | str | None = None) -> list[dict]:
    with connect(path) as conn:
        return [dict(row) for row in conn.execute("""
            SELECT o.id AS order_id, o.created_at, m.name AS menu_item,
                   oi.quantity, oi.quantity * oi.unit_price_cents AS revenue_cents,
                   oi.quantity * oi.unit_food_cost_cents AS food_cost_cents,
                   oi.quantity * (oi.unit_price_cents - oi.unit_food_cost_cents) AS estimated_gross_margin_cents
            FROM orders o JOIN order_items oi ON o.id = oi.order_id
            JOIN menu_items m ON m.id = oi.menu_item_id
            ORDER BY o.created_at DESC, o.id DESC
        """)]