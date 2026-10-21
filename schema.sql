-- Counterwise: beginner-friendly, relational restaurant data model.
-- Money is stored as integer cents to prevent floating-point rounding errors.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    quantity_on_hand INTEGER NOT NULL CHECK (quantity_on_hand >= 0),
    unit_cost_cents INTEGER NOT NULL CHECK (unit_cost_cents >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0)
);

CREATE TABLE IF NOT EXISTS recipes (
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    units_required INTEGER NOT NULL CHECK (units_required > 0),
    PRIMARY KEY (menu_item_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    unit_food_cost_cents INTEGER NOT NULL CHECK (unit_food_cost_cents >= 0)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    order_id INTEGER REFERENCES orders(id),
    delta_units INTEGER NOT NULL CHECK (delta_units != 0),
    reason TEXT NOT NULL CHECK (reason IN ('sale', 'restock')),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_movements_ingredient_id ON inventory_movements(ingredient_id);