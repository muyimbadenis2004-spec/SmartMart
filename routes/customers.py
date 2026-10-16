from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import db, Customer, Sale
from utils import log_action

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    query = Customer.query
    if q:
        query = query.filter(
            Customer.name.ilike(f"%{q}%") |
            Customer.phone.ilike(f"%{q}%") |
            Customer.email.ilike(f"%{q}%")
        )
    return render_template("customers.html", customers=query.order_by(Customer.name).all(), q=q)


@customers_bp.route("/add", methods=["POST"])
@login_required
def add():
    c = Customer(
        name=request.form["name"],
        phone=request.form.get("phone", ""),
        email=request.form.get("email", ""),
        address=request.form.get("address", ""),
    )
    db.session.add(c)
    db.session.flush()
    log_action("create_customer", "customer", c.id, detail=c.name)
    db.session.commit()
    flash("Customer added", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:cid>")
@login_required
def detail(cid):
    c = Customer.query.get_or_404(cid)
    sales = Sale.query.filter_by(customer_id=c.id).order_by(Sale.timestamp.desc()).limit(50).all()
    return render_template("customer_detail.html", customer=c, sales=sales)


@customers_bp.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").strip()
    query = Customer.query
    if q:
        query = query.filter(
            Customer.name.ilike(f"%{q}%") | Customer.phone.ilike(f"%{q}%")
        )
    return jsonify([c.to_dict() for c in query.limit(10).all()])
