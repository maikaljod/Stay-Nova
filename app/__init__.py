"""StayNova application factory."""
import os

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import get_config
from app import db as db_module

csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"])


def create_app(config_object=None):
    # The app package lives in app/, but templates/ and static/ sit at the
    # project root, so point Flask at them explicitly.
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_object or get_config())

    # Allow an optional instance/config.py to override secrets locally
    app.config.from_pyfile("config.py", silent=True)

    os.makedirs(app.instance_path, exist_ok=True)

    # --- extensions -----------------------------------------------------
    db_module.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import get_user_by_id
        return get_user_by_id(user_id)

    # --- blueprints -------------------------------------------------------
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.booking.routes import booking_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # --- security headers -------------------------------------------------
    @app.after_request
    def set_secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' https: data:; "
            "style-src 'self' https: 'unsafe-inline'; "
            "script-src 'self' https:; "
            "font-src 'self' https: data:;"
        )
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # --- error handlers -----------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        # Most often caused by a form sitting open long enough for its CSRF
        # token to expire, or a duplicate/replayed submission.
        flash("Your form session expired or was already submitted. Please try again.", "error")
        target = request.referrer if request.referrer else url_for("main.index")
        return redirect(target)

    return app
