from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from routes.decorators import admin_required
from utils import log_action

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"]).first()
        if u and u.active and u.check_password(request.form["password"]):
            login_user(u)
            log_action("login", "user", u.id, ip=request.remote_addr)
            db.session.commit()
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("logout", "user", current_user.id)
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/users")
@login_required
@admin_required
def users():
    return render_template("users.html", users=User.query.order_by(User.username).all())


@auth_bp.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    if User.query.filter_by(username=request.form["username"]).first():
        flash("Username already exists", "error")
        return redirect(url_for("auth.users"))
    u = User(username=request.form["username"],
             full_name=request.form.get("full_name", ""),
             role=request.form.get("role", "cashier"))
    u.set_password(request.form["password"])
    db.session.add(u)
    log_action("create_user", "user", detail=u.username)
    db.session.commit()
    flash("User created", "success")
    return redirect(url_for("auth.users"))


@auth_bp.route("/users/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        flash("Cannot deactivate yourself", "error")
    else:
        u.active = not u.active
        log_action("toggle_user", "user", u.id, detail=f"active={u.active}")
        db.session.commit()
        flash("User updated", "success")
    return redirect(url_for("auth.users"))


@auth_bp.route("/users/<int:uid>/password", methods=["POST"])
@login_required
@admin_required
def reset_password(uid):
    u = User.query.get_or_404(uid)
    u.set_password(request.form["password"])
    log_action("reset_password", "user", u.id)
    db.session.commit()
    flash("Password reset", "success")
    return redirect(url_for("auth.users"))
