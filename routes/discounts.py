from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Discount
from routes.decorators import manager_required
from utils import log_action

discounts_bp = Blueprint("discounts", __name__, url_prefix="/discounts")


@discounts_bp.route("/", methods=["GET", "POST"])
@login_required
@manager_required
def index():
    if request.method == "POST":
        try:
            d = Discount(
                code=request.form["code"].upper(),
                description=request.form.get("description", ""),
                kind=request.form.get("kind", "percent"),
                value=float(request.form["value"]),
                min_purchase=float(request.form.get("min_purchase", 0) or 0),
                valid_from=datetime.strptime(request.form["valid_from"], "%Y-%m-%d").date()
                           if request.form.get("valid_from") else None,
                valid_to=datetime.strptime(request.form["valid_to"], "%Y-%m-%d").date()
                         if request.form.get("valid_to") else None,
            )
            db.session.add(d)
            log_action("create_discount", "discount", detail=d.code)
            db.session.commit()
            flash("Discount created", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "error")
        return redirect(url_for("discounts.index"))
    return render_template("discounts.html",
                           discounts=Discount.query.order_by(Discount.code).all())


@discounts_bp.route("/<int:did>/toggle", methods=["POST"])
@login_required
@manager_required
def toggle(did):
    d = Discount.query.get_or_404(did)
    d.active = not d.active
    db.session.commit()
    return redirect(url_for("discounts.index"))
