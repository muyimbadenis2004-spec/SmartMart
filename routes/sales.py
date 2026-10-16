import csv
import io
from datetime import datetime
from flask import (Blueprint, render_template, request, jsonify, flash,
                   redirect, url_for, Response)
from flask_login import login_required, current_user
from models import db, Sale, SaleItem, Product, Customer, Discount
from routes.decorators import manager_required
from utils import (apply_stock, log_action, get_open_shift, calc_tax,
                   apply_discount, earn_points)

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/")
@login_required
def pos():
    discount_codes = Discount.query.filter_by(active=True).all()
    return render_template("sales.html", discount_codes=discount_codes,
                           shift=get_open_shift(current_user.id))


@sales_bp.route("/api/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json() or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "Cart is empty"}), 400

    shift = get_open_shift(current_user.id)
    if not shift:
        return jsonify({"error": "No open shift. Please open a shift first."}), 400

    customer = None
    if data.get("customer_id"):
        customer = Customer.query.get(data["customer_id"])

    discount = None
    if data.get("discount_code"):
        discount = Discount.query.filter_by(code=data["discount_code"], active=True).first()

    sale = Sale(
        payment_method=data.get("payment_method", "cash"),
        user_id=current_user.id,
        customer_id=customer.id if customer else None,
        shift_id=shift.id,
        discount_code=discount.code if discount else None,
    )
    db.session.add(sale)

    subtotal = 0.0
    taxable_items = []
    for line in items:
        product = Product.query.get(line["product_id"])
        if not product or not product.active:
            db.session.rollback()
            return jsonify({"error": f"Product {line['product_id']} not found"}), 404
        qty = int(line["quantity"])
        if qty <= 0:
            db.session.rollback()
            return jsonify({"error": "Quantity must be positive"}), 400
        if product.quantity < qty:
            db.session.rollback()
            return jsonify({"error": f"Insufficient stock for {product.name}"}), 400

        line_discount = float(line.get("discount", 0) or 0)
        item = SaleItem(sale=sale, product_id=product.id, quantity=qty,
                        unit_price=product.price, unit_cost=product.cost,
                        discount=line_discount)
        db.session.add(item)

        apply_stock(product, -qty, "sale", reference="sale")
        subtotal += qty * product.price - line_discount
        if product.taxable:
            taxable_items.append({"qty": qty, "price": product.price})

    tax_amount, _rate = calc_tax(subtotal, taxable_items)
    discount_amount = apply_discount(discount, subtotal)
    total = round(subtotal - discount_amount + tax_amount, 2)

    sale.subtotal = round(subtotal, 2)
    sale.discount_amount = round(discount_amount, 2)
    sale.tax_amount = round(tax_amount, 2)
    sale.total = total

    paid = float(data.get("amount_paid", total) or total)
    sale.amount_paid = paid
    sale.change_given = round(paid - total, 2) if paid > total else 0.0

    if customer:
        earn_points(customer, total)

    log_action("sale", "sale", sale.id, detail=f"total={total}")
    db.session.commit()

    return jsonify({"sale_id": sale.id, "total": sale.total,
                    "subtotal": sale.subtotal, "tax": sale.tax_amount,
                    "discount": sale.discount_amount,
                    "change": sale.change_given,
                    "receipt_url": url_for("sales.receipt", sid=sale.id)})


@sales_bp.route("/history")
@login_required
def history():
    q = request.args.get("q", "").strip()
    query = Sale.query
    if q.isdigit():
        query = query.filter(Sale.id == int(q))
    sales = query.order_by(Sale.timestamp.desc()).limit(200).all()
    return render_template("sales.html", sales=sales, show_history=True, q=q)


@sales_bp.route("/<int:sid>/receipt")
@login_required
def receipt(sid):
    sale = Sale.query.get_or_404(sid)
    return render_template("receipt.html", sale=sale, now=datetime.utcnow())


@sales_bp.route("/<int:sid>/receipt.pdf")
@login_required
def receipt_pdf(sid):
    from reportlab.lib.pagesizes import A6
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from flask import current_app

    sale = Sale.query.get_or_404(sid)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A6)
    width, height = A6
    y = height - 30
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, current_app.config["STORE_NAME"])
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, current_app.config["STORE_ADDRESS"])
    y -= 12
    c.drawCentredString(width / 2, y, current_app.config["STORE_PHONE"])
    y -= 18
    c.drawString(20, y, f"Receipt #{sale.id}")
    c.drawRightString(width - 20, y, sale.timestamp.strftime("%Y-%m-%d %H:%M"))
    y -= 14
    c.drawString(20, y, f"Cashier: {sale.user.username if sale.user else '-'}")
    y -= 12
    c.drawString(20, y, f"Payment: {sale.payment_method}")
    if sale.customer:
        y -= 12
        c.drawString(20, y, f"Customer: {sale.customer.name}")
    y -= 16
    c.line(20, y, width - 20, y)
    y -= 12
    for it in sale.items:
        c.drawString(20, y, f"{it.product.name[:26]}")
        y -= 11
        c.drawString(26, y, f"{it.quantity} x {it.unit_price:.2f}")
        c.drawRightString(width - 20, y, f"{it.subtotal:.2f}")
        y -= 13
        if y < 60:
            c.showPage(); y = height - 30
    c.line(20, y, width - 20, y)
    y -= 12
    c.drawString(20, y, "Subtotal");       c.drawRightString(width - 20, y, f"{sale.subtotal:.2f}"); y -= 11
    if sale.discount_amount:
        c.drawString(20, y, "Discount");   c.drawRightString(width - 20, y, f"-{sale.discount_amount:.2f}"); y -= 11
    c.drawString(20, y, "Tax");            c.drawRightString(width - 20, y, f"{sale.tax_amount:.2f}"); y -= 11
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20, y, "TOTAL");          c.drawRightString(width - 20, y, f"{sale.total:.2f}"); y -= 16
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "Thank you!")
    c.showPage()
    c.save()
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=receipt_{sale.id}.pdf"})


@sales_bp.route("/<int:sid>/refund", methods=["POST"])
@login_required
@manager_required
def refund(sid):
    original = Sale.query.get_or_404(sid)
    if original.is_refund or original.voided:
        flash("This sale cannot be refunded", "error")
        return redirect(url_for("sales.history"))

    shift = get_open_shift(current_user.id)
    refund_sale = Sale(
        payment_method=original.payment_method,
        user_id=current_user.id,
        customer_id=original.customer_id,
        shift_id=shift.id if shift else None,
        is_refund=True,
        refund_of_id=original.id,
        subtotal=-original.subtotal,
        discount_amount=-original.discount_amount,
        tax_amount=-original.tax_amount,
        total=-original.total,
        amount_paid=-original.total,
    )
    db.session.add(refund_sale)
    for it in original.items:
        db.session.add(SaleItem(sale=refund_sale, product_id=it.product_id,
                                quantity=-it.quantity, unit_price=it.unit_price,
                                unit_cost=it.unit_cost, discount=-it.discount))
        apply_stock(it.product, it.quantity, "return", reference=f"sale:{original.id}")

    if original.customer:
        pts = int(original.total // 100)
        original.customer.loyalty_points = max(0, (original.customer.loyalty_points or 0) - pts)
        original.customer.total_spent = max(0, (original.customer.total_spent or 0) - original.total)

    log_action("refund", "sale", refund_sale.id, detail=f"of sale {original.id}")
    db.session.commit()
    flash("Refund processed", "success")
    return redirect(url_for("sales.receipt", sid=refund_sale.id))


@sales_bp.route("/<int:sid>/void", methods=["POST"])
@login_required
@manager_required
def void(sid):
    sale = Sale.query.get_or_404(sid)
    if sale.voided:
        flash("Already voided", "error")
        return redirect(url_for("sales.history"))
    for it in sale.items:
        apply_stock(it.product, it.quantity, "adjust",
                    reference=f"void:{sale.id}", note="Sale voided")
    sale.voided = True
    sale.voided_reason = request.form.get("reason", "")
    log_action("void_sale", "sale", sale.id)
    db.session.commit()
    flash("Sale voided", "success")
    return redirect(url_for("sales.history"))


@sales_bp.route("/export.csv")
@login_required
@manager_required
def export_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sale_id", "timestamp", "cashier", "customer", "payment",
                "product", "sku", "qty", "unit_price", "discount", "subtotal",
                "sale_subtotal", "tax", "sale_total", "refund", "voided"])
    for s in Sale.query.order_by(Sale.timestamp).all():
        for it in s.items:
            w.writerow([s.id, s.timestamp.isoformat(),
                        s.user.username if s.user else "",
                        s.customer.name if s.customer else "",
                        s.payment_method,
                        it.product.name, it.product.sku, it.quantity,
                        f"{it.unit_price:.2f}", f"{it.discount:.2f}",
                        f"{it.subtotal:.2f}",
                        f"{s.subtotal:.2f}", f"{s.tax_amount:.2f}", f"{s.total:.2f}",
                        s.is_refund, s.voided])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sales.csv"})
