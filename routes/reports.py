import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required
from sqlalchemy import func
from models import db, Sale, SaleItem, Product, Customer
from routes.decorators import manager_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _date_range(days):
    return datetime.utcnow() - timedelta(days=days)


@reports_bp.route("/")
@login_required
@manager_required
def index():
    days = int(request.args.get("days", 7))
    since = _date_range(days)

    daily = db.session.query(
        func.date(Sale.timestamp).label("day"),
        func.sum(Sale.total).label("total"),
        func.count(Sale.id).label("count")
    ).filter(Sale.timestamp >= since, Sale.voided == False)\
     .group_by("day").order_by("day").all()

    top = db.session.query(
        Product.name, func.sum(SaleItem.quantity).label("qty"),
        func.sum(SaleItem.quantity * SaleItem.unit_price).label("revenue")
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale, Sale.id == SaleItem.sale_id)\
     .filter(Sale.timestamp >= since, Sale.voided == False,
             Sale.is_refund == False)\
     .group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc())\
     .limit(10).all()

    by_payment = db.session.query(
        Sale.payment_method,
        func.sum(Sale.total).label("total"),
        func.count(Sale.id).label("count")
    ).filter(Sale.timestamp >= since, Sale.voided == False)\
     .group_by(Sale.payment_method).all()

    low_stock = Product.query.filter(Product.active == True,
                                     Product.quantity <= Product.reorder_level).all()
    stock_value = db.session.query(
        func.coalesce(func.sum(Product.quantity * Product.cost), 0.0)
    ).filter(Product.active == True).scalar()

    top_customers = db.session.query(
        Customer.name, Customer.total_spent, Customer.loyalty_points
    ).order_by(Customer.total_spent.desc()).limit(10).all()

    return render_template("reports.html",
                           daily=[{"day": str(d.day), "total": d.total, "count": d.count} for d in daily],
                           top=top, by_payment=by_payment,
                           low_stock=low_stock, stock_value=stock_value,
                           top_customers=top_customers, days=days)


@reports_bp.route("/api/daily")
@login_required
@manager_required
def api_daily():
    days = int(request.args.get("days", 7))
    rows = db.session.query(
        func.date(Sale.timestamp).label("day"),
        func.sum(Sale.total).label("total"),
        func.count(Sale.id).label("count")
    ).filter(Sale.timestamp >= _date_range(days)).group_by("day").order_by("day").all()
    return jsonify([{"day": str(r.day), "total": r.total, "count": r.count} for r in rows])


@reports_bp.route("/sales.csv")
@login_required
@manager_required
def sales_csv():
    days = int(request.args.get("days", 7))
    rows = db.session.query(
        func.date(Sale.timestamp).label("day"),
        func.sum(Sale.total).label("total"),
        func.count(Sale.id).label("count")
    ).filter(Sale.timestamp >= _date_range(days)).group_by("day").order_by("day").all()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["day", "orders", "total"])
    for r in rows:
        w.writerow([str(r.day), r.count, f"{r.total:.2f}"])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=daily_sales_{days}d.csv"})


@reports_bp.route("/low_stock.csv")
@login_required
@manager_required
def low_stock_csv():
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["name", "sku", "quantity", "reorder_level"])
    for p in Product.query.filter(Product.active == True,
                                  Product.quantity <= Product.reorder_level).all():
        w.writerow([p.name, p.sku, p.quantity, p.reorder_level])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=low_stock.csv"})
