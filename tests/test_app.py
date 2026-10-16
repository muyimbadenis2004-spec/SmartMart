import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from config import TestConfig
from models import db, User, Product, Sale, SaleItem, Shift


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(username="admin", role="admin"); admin.set_password("admin123")
        cashier = User(username="cashier", role="cashier"); cashier.set_password("cash123")
        db.session.add_all([admin, cashier])
        db.session.add(Product(name="Widget", sku="W1", barcode="1111",
                               price=10.0, cost=4.0, quantity=5, reorder_level=2))
        db.session.commit()
    with app.test_client() as c:
        yield c


def login(c, username, password):
    return c.post("/login", data={"username": username, "password": password},
                  follow_redirects=True)


def open_shift_and_login(c, username, password):
    login(c, username, password)
    return c.post("/shifts/open", data={"opening_float": "100"}, follow_redirects=True)


def test_login_and_dashboard(client):
    r = login(client, "admin", "admin123")
    assert r.status_code == 200
    assert b"Dashboard" in r.data


def test_checkout_requires_open_shift(client):
    login(client, "cashier", "cash123")
    r = client.post("/sales/api/checkout", json={
        "payment_method": "cash",
        "items": [{"product_id": 1, "quantity": 2}]
    })
    assert r.status_code == 400
    assert b"shift" in r.data.lower()


def test_checkout_decrements_stock(client):
    open_shift_and_login(client, "cashier", "cash123")
    r = client.post("/sales/api/checkout", json={
        "payment_method": "cash",
        "items": [{"product_id": 1, "quantity": 2}]
    })
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert data["subtotal"] == 20.0
    assert data["total"] >= data["subtotal"]

    with client.application.app_context():
        p = Product.query.get(1)
        assert p.quantity == 3
        assert Sale.query.count() == 1
        assert SaleItem.query.count() == 1


def test_checkout_rejects_insufficient_stock(client):
    open_shift_and_login(client, "cashier", "cash123")
    r = client.post("/sales/api/checkout", json={
        "items": [{"product_id": 1, "quantity": 999}]
    })
    assert r.status_code == 400
    assert b"stock" in r.data.lower()


def test_role_gate_manager_vs_cashier(client):
    login(client, "cashier", "cash123")
    r = client.post("/products/1/archive")
    assert r.status_code == 403

    client.get("/logout")
    login(client, "admin", "admin123")
    r = client.post("/products/1/archive", follow_redirects=True)
    assert r.status_code == 200


def test_csv_export_products(client):
    login(client, "admin", "admin123")
    r = client.get("/products/export.csv")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("text/csv")
    assert b"Widget" in r.data


def test_receipt_view(client):
    open_shift_and_login(client, "cashier", "cash123")
    client.post("/sales/api/checkout", json={
        "items": [{"product_id": 1, "quantity": 1}]
    })
    r = client.get("/sales/1/receipt")
    assert r.status_code == 200
    assert b"Widget" in r.data
