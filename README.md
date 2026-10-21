# Counterwise — Restaurant Sales & Inventory Analytics

**A small but real full-stack-style Python project:** record a sale, automatically deduct recipe ingredients, see revenue and estimated gross margin, and download orders as CSV. Built with **Python, SQLite, HTML, and CSS**. No third-party packages needed.

> **Portfolio transparency:** This is an educational demonstration using **synthetic restaurant data**. It is not connected to Red Pepper Pizzeria, Habibi Tacos, Stripe, or any real business. It is a starting project created with AI assistance and intended for learning, modification, and personal explanation. Do not claim sole authorship of code you did not write or understand.

## What you can do

- **Record sales:** Choose a menu item and quantity. The app saves the sale with its current price and estimated food cost.
- **Track inventory:** A pizza automatically consumes the ingredients defined in its recipe.
- **Block overselling:** If there isn't enough inventory, the order is rejected without partial changes.
- **Review performance:** See revenue, estimated food cost, margin percentage, recent sales, and popular products.
- **Restock ingredients:** Add stock and keep a history of inventory movements.
- **Export CSV:** Open order data in Excel, Google Sheets, or a Python notebook.
- **Run tests:** Built-in `unittest` checks sales, inventory, rollback, restocking, and the web interface.

## Run it in 3 steps

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) if it isn't installed.
2. Open a terminal in this project folder.
3. Run:

   ```bash
   python3 app.py
   ```

   On Windows, use `python app.py` if `python3` is unavailable.

Open **http://127.0.0.1:8000** in your browser. The database and fictional sample orders will be created automatically in `data/counterwise.db`.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![SQLite](https://img.shields.io/badge/Database-SQLite-0f766e) ![Tests](https://img.shields.io/badge/Tests-unittest-6d28d9)

### Test it

```bash
python3 -m unittest discover -s tests -v
```

### Try the demo

1. Record two Pepperoni Pizzas; check that dough, tomato sauce, mozzarella, and pepperoni each decrease by two.
2. Restock one ingredient by twenty portions; check that its stock increases.
3. Download the CSV; inspect the sales and estimated margin columns.
4. Open `schema.sql` to see how tables connect.
5. Run the tests, then experiment by changing a recipe or adding a menu item.

## Tech stack

| Part | Technology | Why |
| --- | --- | --- |
| Web server | Python `http.server` | Standard library; learn HTTP GET/POST without a framework |
| Database | SQLite (`sqlite3`) | SQL joins, relational data, foreign keys, and transactions |
| User interface | HTML + CSS | Clear forms, responsive layout, no JavaScript build step |
| Tests | `unittest` | Check important behavior with repeatable tests |
| CSV export | Python `csv` | Make reports easy to inspect and share |

## Project structure

```text
counterwise-restaurant-analytics/
├── app.py                  # HTTP requests and dashboard HTML
├── db.py                   # SQLite queries and business rules
├── schema.sql              # Tables, relationships, constraints
├── static/
│   └── style.css           # Responsive dashboard styling
├── tests/
│   └── test_app.py         # Unit and HTTP-level integration tests
├── docs/
│   ├── DESIGN_DECISIONS.md # Explain the engineering tradeoffs
│   └── LEARNING_PATH.md    # Beginner-friendly exercises
├── .gitignore
├── LICENSE
└── README.md
```

## How the database works

```text
menu_items ─────< recipes >───── ingredients
    |                                |
    |                                └────< inventory_movements
    |
    └────< order_items >──── orders ───────┘
```

- `menu_items`: item names and prices
- `recipes`: ingredients required for one menu item
- `ingredients`: inventory and per-portion cost
- `orders` and `order_items`: completed transactions, price and cost snapshots
- `inventory_movements`: auditable sales deductions and restocks

**Order creation is atomic:** validate inventory, create the order, save line item, subtract ingredients, and create audit records inside one SQLite transaction. If something fails, roll back everything. See `db.py` (`place_order`).

**Money is stored as whole cents**, not floating point. Gross margin is a rough **food-only estimate**, not net profit: it excludes wages, rent, utilities, taxes, refunds, delivery fees, and other expenses.

## Design limitations

This app intentionally prioritizes beginner-readable code. It is a **local-only teaching demo**, not production-ready payment or point-of-sale software. It has no sign-in, authorization, HTTPS, CSRF protection, or real payment processing. **Do not host it publicly with a real database or customer data.** It records one menu item per order and assumes portions are whole numbers, not fractions.

For a fuller explanation of technical decisions and improvements, see [DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md).

## How to reset demo data

Stop the app first, delete `data/counterwise.db`, and run it again. The app will rebuild the schema and synthetic sales data. **Deleting the file deletes your locally recorded orders.**

## A good next step

Write one new feature yourself (a search filter for recent orders is a good first choice), add a test, and explain the tradeoff in a GitHub commit. Employers care more about a project you truly understand than a polished repository you cannot explain.

**License:** MIT. See [LICENSE](LICENSE).