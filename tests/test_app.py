"""Run: python -m unittest discover -s tests -v"""

import csv
import io
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import CounterwiseHandler
from db import InventoryError, connect, dashboard, export_rows, initialize, place_order, restock


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.db"
        initialize(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_first_start_creates_usable_demo_data(self):
        summary = dashboard(self.path)
        self.assertEqual(len(summary["menu"]), 4)
        self.assertGreater(summary["totals"]["orders"], 0)
        self.assertGreater(summary["totals"]["revenue_cents"], 0)
        self.assertGreater(len(export_rows(self.path)), 0)

    def test_second_initialize_does_not_duplicate_data(self):
        before = dashboard(self.path)["totals"]["orders"]
        initialize(self.path)
        self.assertEqual(dashboard(self.path)["totals"]["orders"], before)

    def test_sale_adds_revenue_and_deducts_recipe_inventory(self):
        with connect(self.path) as conn:
            before = {r["name"]: r["quantity_on_hand"] for r in conn.execute("SELECT * FROM ingredients")}
            movement_count_before = conn.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0]
        summary_before = dashboard(self.path)["totals"]
        order_id = place_order(2, 2, self.path)  # Pepperoni: dough, sauce, cheese, pepperoni
        with connect(self.path) as conn:
            after = {r["name"]: r["quantity_on_hand"] for r in conn.execute("SELECT * FROM ingredients")}
            sold = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchone()
            movements = conn.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0]
        self.assertEqual(sold["unit_price_cents"], 1700)
        self.assertEqual(sold["unit_food_cost_cents"], 375)
        for ingredient in ["Dough", "Tomato sauce", "Mozzarella", "Pepperoni"]:
            self.assertEqual(after[ingredient], before[ingredient] - 2)
        self.assertEqual(after["Fresh basil"], before["Fresh basil"])
        self.assertEqual(movements, movement_count_before + 4)
        after_totals = dashboard(self.path)["totals"]
        self.assertEqual(after_totals["orders"], summary_before["orders"] + 1)
        self.assertEqual(after_totals["revenue_cents"], summary_before["revenue_cents"] + 3400)
        self.assertEqual(after_totals["food_cost_cents"], summary_before["food_cost_cents"] + 750)

    def test_unavailable_stock_rolls_back_entire_order(self):
        with connect(self.path) as conn:
            conn.execute("UPDATE ingredients SET quantity_on_hand = 0 WHERE name = 'Mozzarella'")
        before_orders = dashboard(self.path)["totals"]["orders"]
        with self.assertRaises(InventoryError):
            place_order(2, 1, self.path)
        self.assertEqual(dashboard(self.path)["totals"]["orders"], before_orders)

    def test_database_failure_mid_sale_rolls_back_every_write(self):
        # Fail after an order and line item were inserted but before inventory
        # could be fully updated: no partial sale should remain.
        with connect(self.path) as conn:
            conn.execute("""
                CREATE TRIGGER reject_sale_movement
                BEFORE INSERT ON inventory_movements
                WHEN NEW.reason = 'sale'
                BEGIN SELECT RAISE(ABORT, 'injected failure'); END
            """)
        old = dashboard(self.path)["totals"]
        with self.assertRaises(sqlite3.IntegrityError):
            place_order(1, 1, self.path)
        new = dashboard(self.path)["totals"]
        self.assertEqual(new, old)

    def test_invalid_quantities_do_not_change_data(self):
        before = dashboard(self.path)["totals"]["orders"]
        for qty in [0, -1, 21]:
            with self.assertRaises(ValueError):
                place_order(1, qty, self.path)
        self.assertEqual(dashboard(self.path)["totals"]["orders"], before)

    def test_restock_increases_count_and_keeps_audit_record(self):
        with connect(self.path) as conn:
            before = conn.execute("SELECT quantity_on_hand FROM ingredients WHERE id = 1").fetchone()[0]
        restock(1, 11, self.path)
        with connect(self.path) as conn:
            after = conn.execute("SELECT quantity_on_hand FROM ingredients WHERE id = 1").fetchone()[0]
            audit = conn.execute("SELECT reason, delta_units FROM inventory_movements ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(after, before + 11)
        self.assertEqual((audit["reason"], audit["delta_units"]), ("restock", 11))

    def test_invalid_restock_does_not_change_count(self):
        with self.assertRaises(ValueError):
            restock(1, 0, self.path)
        with self.assertRaises(ValueError):
            restock(999, 1, self.path)

    def test_foreign_keys_prevent_orphan_order_items(self):
        with connect(self.path) as conn:
            with self.assertRaises(Exception):
                conn.execute("INSERT INTO order_items(order_id,menu_item_id,quantity,unit_price_cents,unit_food_cost_cents) VALUES (999999,1,1,100,10)")


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls._previous_env = os.environ.get("COUNTERWISE_DB")
        os.environ["COUNTERWISE_DB"] = str(Path(cls.directory.name) / "http.db")
        initialize()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), CounterwiseHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        if cls._previous_env is None:
            del os.environ["COUNTERWISE_DB"]
        else:
            os.environ["COUNTERWISE_DB"] = cls._previous_env
        cls.directory.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_homepage_and_stylesheet(self):
        with urlopen(self.url("/")) as res:
            text = res.read().decode()
            self.assertIn("Counterwise", text)
            self.assertIn("Record an order", text)
            self.assertEqual(res.status, 200)
        with urlopen(self.url("/static/style.css")) as res:
            self.assertIn(".sidebar", res.read().decode())

    def test_submit_form_then_export_csv(self):
        before = dashboard()["totals"]["orders"]
        payload = urlencode({"menu_item_id": 1, "quantity": 1}).encode()
        with urlopen(Request(self.url("/orders"), data=payload, method="POST")) as res:
            self.assertIn("saved", res.read().decode())
        self.assertEqual(dashboard()["totals"]["orders"], before + 1)
        with urlopen(self.url("/export/orders.csv")) as res:
            rows = list(csv.DictReader(io.StringIO(res.read().decode("utf-8-sig"))))
            self.assertIn("Revenue ($)", rows[0])
            self.assertGreater(len(rows), before)

    def test_health_endpoint_returns_status(self):
        with urlopen(self.url("/health")) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('"status": "ok"', response.read().decode())

    def test_invalid_quantity_returns_error_without_recording_sale(self):
        before = dashboard()["totals"]["orders"]
        payload = urlencode({"menu_item_id": 1, "quantity": 0}).encode()
        with urlopen(Request(self.url("/orders"), data=payload, method="POST")) as response:
            self.assertIn("Quantity must be between", response.read().decode())
        self.assertEqual(dashboard()["totals"]["orders"], before)

    def test_unknown_path_returns_404(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url("/fake"))
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()