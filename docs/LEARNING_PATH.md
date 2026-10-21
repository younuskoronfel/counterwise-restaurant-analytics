# Learn this project in five short sessions

You don't need to know every detail on day one. Your goal is to make a few real changes, prove they work, and explain your decisions.

## Session 1 — Explore (30 minutes)
Run `python3 app.py`. Click through the dashboard. Record an order and export CSV. Identify the order ID in the CSV.

## Session 2 — SQL basics (45 minutes)
Open `schema.sql`. Find `menu_items`, `ingredients`, and `recipes`. Explain primary keys, foreign keys, and why `recipes` uses two key columns.

Try this query in a SQLite tool:

```sql
SELECT m.name AS product, i.name AS ingredient, r.units_required
FROM recipes r
JOIN menu_items m ON m.id = r.menu_item_id
JOIN ingredients i ON i.id = r.ingredient_id
ORDER BY m.name, i.name;
```

## Session 3 — Python functions (45 minutes)
Read `place_order` in `db.py` and trace its path from user input to the database. Try quantity `0`, then try a valid quantity. Find out why the results are different.

## Session 4 — Tests (45 minutes)
Run `python3 -m unittest discover -s tests -v`. Read `test_sale_adds_revenue_and_deducts_recipe_inventory`. Change a menu price in the demo setup, update an expectation, and test again.

## Session 5 — Build your own feature (60–90 minutes)
Choose ONE:
- Add a fifth menu item and recipe to the demo setup in `db.py`.
- Add a discount field and calculate discounted revenue safely in integer cents.
- Add a report showing which ingredient was consumed most often.

Write a test for the feature. Save your changes with a Git commit and explain what you learned in your own words.

## Portfolio honesty

This starter project was created with AI assistance. Don't present generated code as independently authored work. It's fine to say you **built on a starter, implemented your own features, wrote tests, and learned about SQL transactions**—once you actually have.