# Engineering decisions: Counterwise

This document explains **why** the application works this way. Read through the related files and confirm you understand each decision before discussing the project in an interview.

## 1. Why a relational database?

A menu item can require multiple ingredients, and one ingredient can appear in many menu items. The `recipes` table models this **many-to-many** relationship. Using separate `menu_items`, `recipes`, and `ingredients` tables avoids repeating ingredient names and stock in every order. A relational model also makes SQL joins and reporting easier.

## 2. Why a transaction when recording a sale?

A sale changes several tables: it creates an order, creates an order item, reduces ingredient quantities, and records inventory movements. If a later operation fails after an earlier one succeeds, the database could become inconsistent. `BEGIN IMMEDIATE` reserves the SQLite write transaction, and `COMMIT` saves all changes together. `ROLLBACK` cancels all changes if an error occurs.

**Try it:** In a temporary database, reduce mozzarella to zero, then try to order a pizza. Verify that an error is shown and the order count does not increase. The test `test_unavailable_stock_rolls_back_entire_order` covers this behavior.

## 3. Why store prices and costs as integers?

Floating-point calculations can have rounding surprises. Example: in some programming languages, `0.1 + 0.2 != 0.3`. Instead, Counterwise stores `$14.50` as integer `1450` cents and formats it as dollars at the interface.

## 4. Why save the price and estimated food cost on each sale?

If a menu price or ingredient cost changes tomorrow, yesterday's sales should keep yesterday's values. `order_items` stores price and food-cost snapshots at checkout. This allows historical reporting without recalculating past orders from updated recipes.

## 5. Why record inventory movements separately?

Quantity-on-hand shows current stock, while the `inventory_movements` table explains *why* stock changed: a sale or a restock. This makes mistakes easier to trace and supports future reporting.

## 6. Why test the database and the HTTP interface?

Unit tests verify business logic and database constraints, including low stock and invalid quantities. A small HTTP integration test checks that the website is accessible, that a submitted sale changes data, and that a CSV export can be downloaded.

## 7. What is intentionally missing?

Authentication, authorization, payment integration, credit cards, real customer data, encrypted sessions, CSRF protection, production deployment, order cancellations, fractions of ingredient portions, and supply purchasing. This is an educational app, **not a payment processor** or public production service.

## Questions you should be able to answer

1. What is a SQL `JOIN`, and where do you use it here?
2. How do the `recipes` records connect ingredients to products?
3. Why does a sale need a transaction instead of several unrelated updates?
4. What happens if two users attempt to buy the last ingredient at once?
5. What does estimated gross margin mean, and what costs are missing?
6. What did you change yourself? Why did you make that change?