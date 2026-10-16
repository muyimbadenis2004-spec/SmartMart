from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Supplier
from routes.decorators import manager_required
from utils import log_action

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@suppliers_bp.route("/")
@login_required
@manager_required
def index():
    return render_template("suppliers.html",
                           suppliers=Supplier.query.order_by(Supplier.name).all())


@suppliers_bp.route("/add", methods=["POST"])
@login_required
@manager_required
def add():
    s = Supplier(
        name=request.form["name"],
        contact_name=request.form.get("contact_name", ""),
        phone=request.form.get("phone", ""),
        email=request.form.get("email", ""),
        address=request.form.get("address", ""),
        notes=request.form.get("notes", ""),
    )
    db.session.add(s)
    db.session.flush()
    log_action("create_supplier", "supplier", s.id, detail=s.name)
    db.session.commit()
    flash("Supplier added", "success")
    return redirect(url_for("suppliers.index"))


@suppliers_bp.route("/<int:sid>/edit", methods=["POST"])
@login_required
@manager_required
def edit(sid):
    s = Supplier.query.get_or_404(sid)
    s.name = request.form["name"]
    s.contact_name = request.form.get("contact_name", "")
    s.phone = request.form.get("phone", "")
    s.email = request.form.get("email", "")
    s.address = request.form.get("address", "")
    s.notes = request.form.get("notes", "")
    db.session.commit()
    flash("Supplier updated", "success")
    return redirect(url_for("suppliers.index"))
