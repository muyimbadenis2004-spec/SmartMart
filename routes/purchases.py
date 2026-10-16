from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, PurchaseOrder, PurchaseOrderItem, Product, Supplier
from routes.decorators import manager_required
from utils import apply_stock, log_action

purchases_bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@purchases_bp.route("/")
@login_required
@manager_required
def index():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template("purchases.html", pos=pos,
                           suppliers=Supplier.query.filter_by(active=True).all())


@purchases_bp.route("/new", methods=["POST"])
@login_required
@manager_required
def new():
    po = PurchaseOrder(
        supplier_id=request.form.get("supplier_id", type=int),
        status="draft",
        expected_at=datetime.strptime(request.form["expected_at"], "%Y-%m-%d").date()
                    if request.form.get("expected_at") else None,
        notes=request.form.get("notes", ""),
        user_id=current_user.id,
    )
    db.session.add(po)
    db.session.flush()
    log_action("create_po", "po", po.id)
    db.session.commit()
    return redirect(url_for("purchases.detail", po_id=po.id))


@purchases_bp.route("/<int:po_id>")
@login_required
@manager_required
def detail(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    return render_template("purchase_detail.html", po=po, products=products)


@purchases_bp.route("/<int:po_id>/add_item", methods=["POST"])
@login_required
@manager_required
def add_item(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status != "draft":
        flash("Cannot modify a submitted PO", "error")
        return redirect(url_for("purchases.detail", po_id=po.id))
    pid = request.form.get("product_id", type=int)
    qty = int(request.form["quantity"])
    cost = float(request.form["unit_cost"])
    db.session.add(PurchaseOrderItem(po_id=po.id, product_id=pid,
                                     quantity=qty, unit_cost=cost))
    db.session.commit()
    _recalc_total(po)
    return redirect(url_for("purchases.detail", po_id=po.id))


@purchases_bp.route("/<int:po_id>/remove_item/<int:item_id>", methods=["POST"])
@login_required
@manager_required
def remove_item(po_id, item_id):
    item = PurchaseOrderItem.query.get_or_404(item_id)
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status != "draft":
        flash("Cannot modify a submitted PO", "error")
    else:
        db.session.delete(item)
        db.session.commit()
        _recalc_total(po)
    return redirect(url_for("purchases.detail", po_id=po.id))


@purchases_bp.route("/<int:po_id>/submit", methods=["POST"])
@login_required
@manager_required
def submit(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if not po.items:
        flash("Add items first", "error")
    else:
        po.status = "ordered"
        log_action("submit_po", "po", po.id)
        db.session.commit()
        flash("PO submitted to supplier", "success")
    return redirect(url_for("purchases.detail", po_id=po.id))


@purchases_bp.route("/<int:po_id>/receive", methods=["POST"])
@login_required
@manager_required
def receive(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status != "ordered":
        flash("Only ordered POs can be received", "error")
        return redirect(url_for("purchases.detail", po_id=po.id))

    for item in po.items:
        product = item.product
        product.cost = item.unit_cost
        apply_stock(product, item.quantity, "po", reference=f"po:{po.id}")
    po.status = "received"
    po.received_at = datetime.utcnow()
    log_action("receive_po", "po", po.id)
    db.session.commit()
    flash("PO received, stock updated", "success")
    return redirect(url_for("purchases.detail", po_id=po.id))


@purchases_bp.route("/<int:po_id>/cancel", methods=["POST"])
@login_required
@manager_required
def cancel(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status == "received":
        flash("Cannot cancel a received PO", "error")
    else:
        po.status = "cancelled"
        log_action("cancel_po", "po", po.id)
        db.session.commit()
        flash("PO cancelled", "success")
    return redirect(url_for("purchases.detail", po_id=po.id))


def _recalc_total(po):
    po.total_cost = sum(i.quantity * i.unit_cost for i in po.items)
    db.session.commit()
