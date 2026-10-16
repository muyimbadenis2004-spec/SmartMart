from datetime import date
from flask import current_app
from flask_login import current_user
from models import db, AuditLog, StockMovement, Shift


def fmt_money(v):
    cur = current_app.config.get("CURRENCY", "$")
    return f"{cur}{v or 0:,.2f}"


def log_action(action, entity=None, entity_id=None, detail=None, ip=None):
    db.session.add(AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action, entity=entity, entity_id=entity_id,
        detail=detail, ip=ip,
    ))


def apply_stock(product, change, reason, reference=None, note=None):
    product.quantity += change
    db.session.add(StockMovement(
        product_id=product.id, change=change, reason=reason,
        reference=reference, note=note,
        user_id=current_user.id if current_user.is_authenticated else None,
    ))


def get_open_shift(user_id):
    return Shift.query.filter_by(user_id=user_id, closed_at=None)\
                      .order_by(Shift.opened_at.desc()).first()


def calc_tax(subtotal, taxable_items):
    rate = current_app.config.get("STORE_TAX_RATE", 0.0)
    taxable_subtotal = sum(i["qty"] * i["price"] for i in taxable_items)
    return round(taxable_subtotal * rate, 2), rate


def apply_discount(discount, subtotal):
    if not discount or not discount.active:
        return 0.0
    today = date.today()
    if discount.valid_from and today < discount.valid_from:
        return 0.0
    if discount.valid_to and today > discount.valid_to:
        return 0.0
    if subtotal < (discount.min_purchase or 0):
        return 0.0
    if discount.kind == "percent":
        return round(subtotal * (discount.value / 100.0), 2)
    return min(discount.value, subtotal)


def earn_points(customer, total):
    if not customer:
        return 0
    per = current_app.config.get("POINT_VALUE", 100)
    points = int(total // per)
    customer.loyalty_points = (customer.loyalty_points or 0) + points
    customer.total_spent = (customer.total_spent or 0) + total
    return points
