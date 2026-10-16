from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="cashier")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_manager(self):
        return self.role in ("manager", "admin")

    @property
    def is_admin(self):
        return self.role == "admin"


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200))


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    sku = db.Column(db.String(40), unique=True, nullable=False)
    barcode = db.Column(db.String(64), unique=True, index=True)
    price = db.Column(db.Float, nullable=False, default=0.0)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=10)
    reorder_quantity = db.Column(db.Integer, default=20)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    taxable = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship("Category")
    supplier = db.relationship("Supplier")

    @property
    def low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def out_of_stock(self):
        return self.quantity <= 0

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "sku": self.sku,
            "barcode": self.barcode, "price": self.price, "cost": self.cost,
            "quantity": self.quantity, "reorder_level": self.reorder_level,
            "category": self.category.name if self.category else None,
            "supplier": self.supplier.name if self.supplier else None,
            "taxable": self.taxable, "low_stock": self.low_stock,
        }


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), index=True)
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    loyalty_points = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "phone": self.phone,
            "email": self.email, "loyalty_points": self.loyalty_points,
            "total_spent": self.total_spent,
        }


class Shift(db.Model):
    __tablename__ = "shifts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    opening_float = db.Column(db.Float, default=0.0)
    closing_cash = db.Column(db.Float)
    expected_cash = db.Column(db.Float)
    difference = db.Column(db.Float)
    notes = db.Column(db.Text)

    user = db.relationship("User")


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    subtotal = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), default="cash")
    amount_paid = db.Column(db.Float, default=0.0)
    change_given = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"))
    discount_code = db.Column(db.String(40))
    is_refund = db.Column(db.Boolean, default=False)
    refund_of_id = db.Column(db.Integer, db.ForeignKey("sales.id"))
    voided = db.Column(db.Boolean, default=False)
    voided_reason = db.Column(db.String(200))

    user = db.relationship("User", foreign_keys=[user_id])
    customer = db.relationship("Customer")
    items = db.relationship("SaleItem", backref="sale", cascade="all, delete-orphan",
                            foreign_keys="SaleItem.sale_id")

    def to_dict(self):
        return {
            "id": self.id, "timestamp": self.timestamp.isoformat(),
            "subtotal": self.subtotal, "discount": self.discount_amount,
            "tax": self.tax_amount, "total": self.total,
            "payment_method": self.payment_method,
            "cashier": self.user.username if self.user else None,
            "customer": self.customer.name if self.customer else None,
            "items": [i.to_dict() for i in self.items],
        }


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    product = db.relationship("Product")

    @property
    def subtotal(self):
        return self.quantity * self.unit_price - self.discount

    @property
    def profit(self):
        return self.subtotal - (self.quantity * (self.unit_cost or 0))

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.product.name if self.product else None,
            "sku": self.product.sku if self.product else None,
            "quantity": self.quantity, "unit_price": self.unit_price,
            "discount": self.discount, "subtotal": self.subtotal,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    change = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(60), nullable=False)
    reference = db.Column(db.String(80))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    note = db.Column(db.String(200))

    product = db.relationship("Product")
    user = db.relationship("User")


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    status = db.Column(db.String(20), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expected_at = db.Column(db.Date)
    received_at = db.Column(db.DateTime)
    total_cost = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    supplier = db.relationship("Supplier")
    items = db.relationship("PurchaseOrderItem", backref="po", cascade="all, delete-orphan")


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    product = db.relationship("Product")

    @property
    def subtotal(self):
        return self.quantity * self.unit_cost


class Discount(db.Model):
    __tablename__ = "discounts"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(120))
    kind = db.Column(db.String(10), default="percent")
    value = db.Column(db.Float, nullable=False)
    min_purchase = db.Column(db.Float, default=0.0)
    valid_from = db.Column(db.Date)
    valid_to = db.Column(db.Date)
    active = db.Column(db.Boolean, default=True)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    category = db.Column(db.String(60), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(60), nullable=False)
    entity = db.Column(db.String(60))
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    ip = db.Column(db.String(45))

    user = db.relationship("User")
