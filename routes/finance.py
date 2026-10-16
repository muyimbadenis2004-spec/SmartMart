from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from sqlalchemy import func
from models import db, Expense, Sale, SaleItem
from routes.decorators import manager_required
from utils import log_action
import csv, io

finance_bp = Blueprint("finance", __name__, url_prefix="/finance")


@finance_bp.route("/", methods=["GET", "POST"])
@login_required
@manager_required
def index():
    if request.method == "POST":
        e = Expense(
            date=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
            category=request.form["category"],
            amount=float(request.form["amount"]),
            note=request.form.get("note", ""),
        )
        db.session.add(e)
        log_action("add_expense", "expense", detail=f"{e.category} {e.amount}")
        db.session.commit()
        flash("Expense recorded", "success")
        return redirect(url_for("finance.index"))

    today = date.today()
    month_start = today.replace(day=1)

    revenue = db.session.query(func.coalesce(func.sum(Sale.total), 0.0))\
        .filter(Sale.timestamp >= month_start,
                Sale.voided == False, Sale.is_refund == False).scalar()
    refunds = db.session.query(func.coalesce(func.sum(Sale.total), 0.0))\
        .filter(Sale.timestamp >= month_start, Sale.is_refund == True).scalar()
    cogs = db.session.query(
        func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_cost), 0.0)
    ).join(Sale, Sale.id == SaleItem.sale_id)\
     .filter(Sale.timestamp >= month_start,
             Sale.voided == False, Sale.is_refund == False).scalar()

    expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0))\
        .filter(Expense.date >= month_start).scalar()
    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses

    recent = Expense.query.order_by(Expense.date.desc()).limit(20).all()
    return render_template("finance.html",
                           revenue=revenue, refunds=refunds, cogs=cogs,
                           gross_profit=gross_profit, expenses=expenses,
                           net_profit=net_profit, recent=recent, today=today)


@finance_bp.route("/expenses.csv")
@login_required
@manager_required
def expenses_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "category", "amount", "note"])
    for e in Expense.query.order_by(Expense.date).all():
        w.writerow([e.date, e.category, f"{e.amount:.2f}", e.note])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})
