import csv, io
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from models import AuditLog, User
from routes.decorators import admin_required

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("/")
@login_required
@admin_required
def index():
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action", "").strip()
    query = AuditLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    logs = query.order_by(AuditLog.timestamp.desc()).limit(500).all()
    return render_template("audit.html", logs=logs,
                           users=User.query.all(), current_user_id=user_id,
                           current_action=action)


@audit_bp.route("/export.csv")
@login_required
@admin_required
def export_csv():
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["timestamp", "user", "action", "entity", "entity_id", "detail", "ip"])
    for l in AuditLog.query.order_by(AuditLog.timestamp.desc()).all():
        w.writerow([l.timestamp.isoformat(),
                    l.user_id, l.action, l.entity or "",
                    l.entity_id or "", l.detail or "", l.ip or ""])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=audit_log.csv"})
