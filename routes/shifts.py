from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Shift, Sale
from utils import get_open_shift, log_action

shifts_bp = Blueprint("shifts", __name__, url_prefix="/shifts")


@shifts_bp.route("/")
@login_required
def index():
    open_shift = get_open_shift(current_user.id)
    history = Shift.query.filter_by(user_id=current_user.id)\
                         .order_by(Shift.opened_at.desc()).limit(30).all()
    return render_template("shifts.html", open_shift=open_shift, history=history)


@shifts_bp.route("/open", methods=["POST"])
@login_required
def open_shift():
    if get_open_shift(current_user.id):
        flash("A shift is already open", "error")
        return redirect(url_for("shifts.index"))
    s = Shift(user_id=current_user.id,
              opening_float=float(request.form.get("opening_float", 0)))
    db.session.add(s)
    log_action("open_shift", "shift", detail=f"float={s.opening_float}")
    db.session.commit()
    flash("Shift opened", "success")
    return redirect(url_for("sales.pos"))


@shifts_bp.route("/close", methods=["POST"])
@login_required
def close_shift():
    s = get_open_shift(current_user.id)
    if not s:
        flash("No open shift", "error")
        return redirect(url_for("shifts.index"))

    cash_sales = db.session.query(func.coalesce(func.sum(Sale.total), 0.0))\
        .filter(Sale.shift_id == s.id, Sale.payment_method == "cash",
                Sale.voided == False, Sale.is_refund == False).scalar()

    expected = s.opening_float + cash_sales
    closing = float(request.form.get("closing_cash", 0))

    s.closed_at = datetime.utcnow()
    s.closing_cash = closing
    s.expected_cash = round(expected, 2)
    s.difference = round(closing - expected, 2)
    s.notes = request.form.get("notes", "")

    log_action("close_shift", "shift", s.id,
               detail=f"expected={expected:.2f} counted={closing:.2f}")
    db.session.commit()
    flash(f"Shift closed. Difference: {s.difference:+.2f}", "success")
    return redirect(url_for("shifts.index"))
