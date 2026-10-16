import csv
import io
from flask import (Blueprint, render_template, request, redirect, url_for,
                   jsonify, flash, Response)
from flask_login import login_required
from models import db, Product, Category, Supplier
from routes.decorators import manager_required
from utils import log_action

products_bp = Blueprint("products", __name__, url_prefix="/products")


@products_bp.route("/")
@login_required
def list_products():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", type=int)
    query = Product.query.filter_by(active=True)
    if q:
        query = query.filter(
            Product.name.ilike(f"%{q}%") |
            Product.sku.ilike(f"%{q}%") |
            Product.barcode.ilike(f"%{q}%")
        )
    if cat:
        query = query.filter(Product.category_id == cat)
    return render_template("products.html",
                           products=query.order_by(Product.name).all(),
                           categories=Category.query.order_by(Category.name).all(),
                           suppliers=Supplier.query.filter_by(active=True).all(),
                           q=q, current_cat=cat)


@products_bp.route("/add", methods=["POST"])
@login_required
@manager_required
def add_product():
    p = Product(
        name=request.form["name"],
        sku=request.form["sku"],
        barcode=request.form.get("barcode") or None,
        price=float(request.form["price"]),
        cost=float(request.form.get("cost", 0)),
        quantity=int(request.form.get("quantity", 0)),
        reorder_level=int(request.form.get("reorder_level", 10)),
        reorder_quantity=int(request.form.get("reorder_quantity", 20)),
        category_id=request.form.get("category_id", type=int),
        supplier_id=request.form.get("supplier_id", type=int),
        taxable="taxable" in request.form,
    )
    db.session.add(p)
    try:
        db.session.flush()
        log_action("create_product", "product", p.id, detail=p.name)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("SKU or barcode already exists.", "error")
        return redirect(url_for("products.list_products"))
    flash("Product added", "success")
    return redirect(url_for("products.list_products"))


@products_bp.route("/<int:pid>/edit", methods=["POST"])
@login_required
@manager_required
def edit_product(pid):
    p = Product.query.get_or_404(pid)
    p.name = request.form["name"]
    p.sku = request.form["sku"]
    p.barcode = request.form.get("barcode") or None
    p.price = float(request.form["price"])
    p.cost = float(request.form.get("cost", 0))
    p.reorder_level = int(request.form.get("reorder_level", 10))
    p.reorder_quantity = int(request.form.get("reorder_quantity", 20))
    p.category_id = request.form.get("category_id", type=int)
    p.supplier_id = request.form.get("supplier_id", type=int)
    p.taxable = "taxable" in request.form
    log_action("edit_product", "product", p.id)
    db.session.commit()
    flash("Product updated", "success")
    return redirect(url_for("products.list_products"))


@products_bp.route("/<int:pid>/archive", methods=["POST"])
@login_required
@manager_required
def archive_product(pid):
    p = Product.query.get_or_404(pid)
    p.active = False
    log_action("archive_product", "product", p.id)
    db.session.commit()
    flash("Product archived", "success")
    return redirect(url_for("products.list_products"))


@products_bp.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").strip()
    query = Product.query.filter_by(active=True)
    if q:
        query = query.filter(
            Product.name.ilike(f"%{q}%") |
            Product.barcode.ilike(f"%{q}%") |
            Product.sku.ilike(f"%{q}%")
        )
    return jsonify([p.to_dict() for p in query.limit(10).all()])


@products_bp.route("/api/barcode/<code>")
@login_required
def api_barcode(code):
    p = Product.query.filter_by(barcode=code, active=True).first()
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify(p.to_dict())


@products_bp.route("/export.csv")
@login_required
@manager_required
def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "sku", "barcode", "category", "supplier",
                "price", "cost", "quantity", "reorder_level"])
    for p in Product.query.order_by(Product.name).all():
        w.writerow([p.id, p.name, p.sku, p.barcode or "",
                    p.category.name if p.category else "",
                    p.supplier.name if p.supplier else "",
                    p.price, p.cost, p.quantity, p.reorder_level])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=products.csv"})


@products_bp.route("/categories", methods=["GET", "POST"])
@login_required
@manager_required
def categories():
    if request.method == "POST":
        db.session.add(Category(name=request.form["name"],
                                description=request.form.get("description", "")))
        db.session.commit()
        flash("Category added", "success")
        return redirect(url_for("products.categories"))
    return render_template("categories.html",
                           categories=Category.query.order_by(Category.name).all())


@products_bp.route("/categories/<int:cid>/delete", methods=["POST"])
@login_required
@manager_required
def delete_category(cid):
    c = Category.query.get_or_404(cid)
    if Product.query.filter_by(category_id=c.id).count():
        flash("Cannot delete: category is in use", "error")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Category deleted", "success")
    return redirect(url_for("products.categories"))
