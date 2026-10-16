from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product, StockMovement
from routes.decorators import manager_required
from utils import apply_stock, log_action

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")


@stock_bp.route("/")
@login_required
def index():
    products = Product.query.filter_by(active=True).order_by(Product.quantity).all()
    low = [p for p in products if p.low_stock]
    return render_template("stock.html", products=products, low=low)


@stock_bp.route("/movements")
@login_required
@manager_required
def movements():
    product_id = request.args.get("product_id", type=int)
    query = StockMovement.query
    if product_id:
        query = query.filter_by(product_id=product_id)
    moves = query.order_by(StockMovement.timestamp.desc()).limit(300).all()
    return render_template("stock_movements.html", movements=moves,
                           products=Product.query.order_by(Product.name).all(),
                           current_product=product_id)


@stock_bp.route("/restock/<int:pid>", methods=["POST"])
@login_required
@manager_required
def restock(pid):
    p = Product.query.get_or_404(pid)
    amount = int(request.form["amount"])
    if amount <= 0:
        flash("Amount must be positive", "error")
    else:
        apply_stock(p, amount, "restock", note=request.form.get("note", ""))
        log_action("restock", "product", p.id, detail=f"+{amount}")
        db.session.commit()
        flash(f"Restocked {p.name} by {amount}", "success")
    return redirect(url_for("stock.index"))


@stock_bp.route("/adjust/<int:pid>", methods=["POST"])
@login_required
@manager_required
def adjust(pid):
    p = Product.query.get_or_404(pid)
    new_qty = int(request.form["quantity"])
    delta = new_qty - p.quantity
    if delta == 0:
        flash("No change", "error")
    else:
        apply_stock(p, delta, "adjust", note=request.form.get("note", ""))
        log_action("adjust_stock", "product", p.id, detail=f"{delta:+d}")
        db.session.commit()
        flash("Stock adjusted", "success")
    return redirect(url_for("stock.index"))
