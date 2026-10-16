from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_migrate import Migrate
from config import Config
from models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"

    from routes.auth import auth_bp
    from routes.products import products_bp
    from routes.suppliers import suppliers_bp
    from routes.purchases import purchases_bp
    from routes.customers import customers_bp
    from routes.sales import sales_bp
    from routes.stock import stock_bp
    from routes.finance import finance_bp
    from routes.shifts import shifts_bp
    from routes.discounts import discounts_bp
    from routes.reports import reports_bp
    from routes.audit import audit_bp

    for bp in (auth_bp, products_bp, suppliers_bp, purchases_bp, customers_bp,
               sales_bp, stock_bp, finance_bp, shifts_bp, discounts_bp,
               reports_bp, audit_bp):
        app.register_blueprint(bp)

    @app.route("/")
    @login_required
    def dashboard():
        from utils import get_open_shift
        from models import Sale, Product, Customer
        from sqlalchemy import func
        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(days=1)
        today_rev = db.session.query(func.coalesce(func.sum(Sale.total), 0.0))\
            .filter(Sale.timestamp >= since, Sale.voided == False,
                    Sale.is_refund == False).scalar()
        low_count = Product.query.filter(Product.active == True,
                                         Product.quantity <= Product.reorder_level).count()
        cust_count = Customer.query.count()
        return render_template("dashboard.html", user=current_user,
                               today_rev=today_rev, low_count=low_count,
                               cust_count=cust_count,
                               open_shift=get_open_shift(current_user.id))

    @app.errorhandler(401)
    def unauth(e): return render_template("error.html", code=401, message="Please sign in."), 401

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You do not have permission for this action."), 403

    @app.errorhandler(404)
    def notfound(e): return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(CSRFError)
    def csrf_err(e):
        return render_template("error.html", code=400,
                               message="Session expired. Please try again."), 400

    @app.context_processor
    def inject_globals():
        from flask_wtf.csrf import generate_csrf
        from utils import fmt_money
        return {
            "csrf_token": generate_csrf,
            "fmt_money": fmt_money,
            "STORE_NAME": app.config["STORE_NAME"],
            "CURRENCY": app.config["CURRENCY"],
        }

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin = User(username=os.environ.get("ADMIN_USERNAME", "admin"),
                         full_name="Administrator", role="admin")
            admin.set_password(os.environ.get("ADMIN_PASSWORD", "admin123"))
            db.session.add(admin)
            db.session.commit()

    return app


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
