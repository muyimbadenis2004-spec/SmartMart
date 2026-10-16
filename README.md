# SmartMart Manager

A complete single-store retail management system built with Flask + SQLite.

## Features

- POS with barcode scanning, cart, discounts, tax, and change calculation
- Products, categories, suppliers, purchase orders
- Customers with loyalty points and purchase history
- Refunds, voids, shift / cash-drawer tracking
- Finance: revenue, COGS, expenses, gross/net profit
- Reports: daily sales, top products, top customers, low stock
- CSV exports for products, sales, expenses, audit, reports
- PDF receipts (ReportLab)
- Role-based access (cashier / manager / admin) + audit log
- CSRF protection, migrations, pytest suite

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
