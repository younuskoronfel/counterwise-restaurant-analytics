"""Counterwise web app (Python standard library + SQLite; no pip install)."""

from __future__ import annotations

import csv
import html
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from db import InventoryError, dashboard, export_rows, initialize, place_order, restock

ROOT = Path(__file__).resolve().parent


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_dashboard(info: dict, message: str = "", error: str = "") -> str:
    totals = info["totals"]
    revenue = totals["revenue_cents"]
    food_cost = totals["food_cost_cents"]
    gross = revenue - food_cost
    margin_pct = round(100 * gross / revenue, 1) if revenue else 0

    highest = max((x["sales_cents"] for x in info["days"]), default=1)
    chart = "".join(
        f'<div class="bar-column" title="{escape(day["day"])}: {money(day["sales_cents"])}">'
        f'<div class="bar" style="height:{max(4, round(day["sales_cents"] / highest * 100))}%"></div>'
        f'<span>{escape(day["day"][5:])}</span></div>'
        for day in info["days"]
    )
    menu_options = "".join(
        f'<option value="{item["id"]}">{escape(item["name"])} — {money(item["price_cents"])}</option>'
        for item in info["menu"]
    )
    restock_options = "".join(
        f'<option value="{i["id"]}">{escape(i["name"])}</option>'
        for i in info["inventory"]
    )
    inventory_rows = "".join(
        '<tr><td><span class="item-name">{name}</span><span class="unit">{unit}</span></td>'
        '<td class="right">{qty}</td><td class="right"><span class="pill {status}">{label}</span></td></tr>'.format(
            name=escape(i["name"]), unit=escape(i["unit"]), qty=i["quantity_on_hand"],
            status="warning" if i["quantity_on_hand"] <= i["reorder_level"] else "healthy",
            label="Low stock" if i["quantity_on_hand"] <= i["reorder_level"] else "In stock",
        ) for i in info["inventory"]
    )
    popular_rows = "".join(
        f'<div class="ranked"><span>{n}</span><strong>{escape(p["name"])}</strong>'
        f'<small>{p["units"]} sold</small><b>{money(p["sales_cents"])}</b></div>'
        for n, p in enumerate(info["popular"], 1)
    )
    recent_rows = "".join(
        '<tr><td class="mono">#{id}</td><td>{name}</td><td class="right">{quantity}</td>'
        '<td class="right">{total}</td></tr>'.format(
            id=r["id"], name=escape(r["name"]), quantity=r["quantity"], total=money(r["total_cents"]),
        ) for r in info["recent"]
    )
    alert = f'<div class="notice good">{escape(message)}</div>' if message else (
        f'<div class="notice bad">{escape(error)}</div>' if error else ""
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Counterwise | Restaurant Analytics</title><link rel="stylesheet" href="/static/style.css"></head>
<body><div class="app-shell">
<aside class="sidebar">
  <div class="brand"><div class="brand-symbol">C<span>●</span></div><div>counterwise<small>Restaurant analytics</small></div></div>
  <div class="nav-label">WORKSPACE</div>
  <a class="nav-link selected" href="/">▦ &nbsp; Overview</a>
  <a class="nav-link" href="#orders">＋ &nbsp; New order</a>
  <a class="nav-link" href="#inventory">◫ &nbsp; Inventory</a>
  <a class="nav-link" href="/export/orders.csv">↧ &nbsp; Export CSV</a>
  <div class="sidebar-footer"><div class="tiny-dot"></div>Local demo mode<br><small>Synthetic data · No real customers</small></div>
</aside>
<main class="main">
  <header class="topbar"><div class="crumb">Workspace <span>/</span> Overview</div><div class="topbar-side"><span class="small-circle">●</span> Demo Pizzeria <span class="avatar">DP</span></div></header>
  <div class="content">
    <div class="page-intro"><div><div class="eyebrow">BUSINESS INTELLIGENCE <span>•</span> LIVE DEMO</div><h1>Good morning, operator <span class="wave">✳</span></h1><p>Everything you need to understand sales, costs, and ingredients—all in one place.</p></div><a class="action-button" href="#orders">＋ Record a sale</a></div>
    {alert}
    <section class="metrics">
      <article class="metric"><div class="metric-title">Total revenue <span>↗</span></div><strong>{money(revenue)}</strong><div class="metric-foot">From {totals["orders"]} recorded orders</div></article>
      <article class="metric"><div class="metric-title">Estimated food cost <span>◉</span></div><strong>{money(food_cost)}</strong><div class="metric-foot">Based on recipe quantities</div></article>
      <article class="metric"><div class="metric-title">Est. gross margin <span>✧</span></div><strong>{margin_pct}%</strong><div class="metric-foot">{money(gross)} before other expenses</div></article>
      <article class="metric"><div class="metric-title">Inventory alerts <span>⚑</span></div><strong>{sum(i["quantity_on_hand"] <= i["reorder_level"] for i in info["inventory"])}</strong><div class="metric-foot">Ingredients at or below threshold</div></article>
    </section>
    <section class="two-col main-panels">
      <article class="panel"><div class="panel-head"><div><h2>Sales performance</h2><p>Recorded revenue over the last ten demo days</p></div><span class="subtle-label">USD</span></div><div class="chart">{chart}</div><div class="chart-foot">Demo sales use generated transactions, not live restaurant data.</div></article>
      <article class="panel"><div class="panel-head"><div><h2>Best-selling items</h2><p>Ranked by quantity sold</p></div><span class="subtle-label">ALL TIME</span></div><div class="ranked-list">{popular_rows}</div></article>
    </section>
    <section class="two-col next-panels">
      <article class="panel" id="orders"><div class="panel-head"><div><h2>Record an order</h2><p>Inventory updates automatically after each sale</p></div></div>
        <form action="/orders" method="post" class="form-grid">
          <label>Menu item<select required name="menu_item_id">{menu_options}</select></label>
          <label>Quantity<input name="quantity" type="number" value="1" min="1" max="20" required></label>
          <button class="full-button" type="submit">Save order &amp; update inventory →</button>
        </form><div class="form-foot">All database changes are saved in one transaction.</div>
      </article>
      <article class="panel" id="inventory"><div class="panel-head"><div><h2>Ingredient inventory</h2><p>Stock remaining after fulfilled orders</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>INGREDIENT</th><th class="right">QTY</th><th class="right">STATUS</th></tr></thead><tbody>{inventory_rows}</tbody></table></div>
        <form action="/restock" method="post" class="restock"><label>Restock <select name="ingredient_id">{restock_options}</select></label><label>Units <input type="number" name="quantity" min="1" max="10000" value="20" required></label><button type="submit">Add stock</button></form>
      </article>
    </section>
    <section class="panel recent-panel"><div class="panel-head"><div><h2>Recent orders</h2><p>Newest transactions in your local database</p></div><a class="text-link" href="/export/orders.csv">Download CSV ↗</a></div>
      <div class="table-wrap"><table><thead><tr><th>ORDER</th><th>PRODUCT</th><th class="right">QTY</th><th class="right">REVENUE</th></tr></thead><tbody>{recent_rows}</tbody></table></div>
    </section>
    <footer>Counterwise · Built with Python, SQLite, and the standard library · Demo data only</footer>
  </div>
</main></div></body></html>'''


class CounterwiseHandler(BaseHTTPRequestHandler):
    def send_content(self, body: bytes, content_type: str, status: int = 200,
                     extra_headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/":
            query = parse_qs(url.query)
            page = render_dashboard(dashboard(),
                                    message=query.get("message", [""])[0],
                                    error=query.get("error", [""])[0])
            self.send_content(page.encode("utf-8"), "text/html; charset=utf-8")
        elif url.path == "/static/style.css":
            stylesheet = (ROOT / "static" / "style.css").read_bytes()
            self.send_content(stylesheet, "text/css; charset=utf-8")
        elif url.path == "/health":
            self.send_content(json.dumps({"status": "ok"}).encode(), "application/json")
        elif url.path == "/export/orders.csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["Order ID", "Date (UTC)", "Menu Item", "Quantity", "Revenue ($)",
                             "Ingredient Cost ($)", "Estimated Gross Margin ($)"])
            for row in export_rows():
                writer.writerow([row["order_id"], row["created_at"], row["menu_item"], row["quantity"],
                                 f'{row["revenue_cents"]/100:.2f}', f'{row["food_cost_cents"]/100:.2f}',
                                 f'{row["estimated_gross_margin_cents"]/100:.2f}'])
            self.send_content(buffer.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8",
                              extra_headers={"Content-Disposition": 'attachment; filename="counterwise-orders.csv"'})
        else:
            self.send_content(b"Not found", "text/plain", 404)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path not in ("/orders", "/restock"):
            self.send_content(b"Not found", "text/plain", 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                self.send_content(b"Invalid request length", "text/plain", 400)
                return
            if length > 10_000:
                self.send_content(b"Request too large", "text/plain", 413)
                return
            data = parse_qs(self.rfile.read(length).decode("utf-8"))
            if url.path == "/orders":
                order_id = place_order(int(data["menu_item_id"][0]), int(data["quantity"][0]))
                message = f"Order #{order_id} saved. Inventory and sales totals updated."
            else:
                restock(int(data["ingredient_id"][0]), int(data["quantity"][0]))
                message = "Ingredient stock updated and recorded in the audit history."
            location = "/?message=" + quote(message)
        except (KeyError, ValueError, InventoryError) as exc:
            location = "/?error=" + quote(str(exc))
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        # Keep server output readable but preserve HTTP logs for troubleshooting.
        super().log_message(format, *args)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run the Counterwise local dashboard")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    initialize()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), CounterwiseHandler)
    print(f"Counterwise is running at http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop. This demo is local-only and has no user authentication.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()