import os

from alembic.script import ScriptDirectory
from flask import Flask, jsonify, render_template, request
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is missing; set it in the environment before starting the app")

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in first."

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Authentication required"}), 401

    from backend.models import User
    from backend.routes.assistant import assistant_bp
    from backend.routes.auth import auth_bp
    from backend.routes.locations import locations_bp

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(locations_bp, url_prefix="/api/locations")
    app.register_blueprint(assistant_bp, url_prefix="/api/assistant")

    @app.get("/api/health/live")
    def health_live():
        return jsonify({"status": "alive", "application": "AceMap Changer"})

    @app.get("/api/health/ready")
    @app.get("/api/health")
    def health_ready():
        try:
            table_names = set(inspect(db.engine).get_table_names())
            required_tables = {"users", "map_items", "photos", "alembic_version"}
            if not required_tables.issubset(table_names):
                return jsonify({"status": "unavailable"}), 503
            revisions = set(db.session.execute(text("SELECT version_num FROM alembic_version")).scalars())
            expected_heads = set(ScriptDirectory.from_config(migrate.get_config()).get_heads())
            if revisions != expected_heads:
                return jsonify({"status": "unavailable"}), 503
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"status": "ready", "database": "ready", "migration": "current", "application": "AceMap Changer"})

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify({"error": "Request exceeds the 5 MB upload limit"}), 413

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://unpkg.com; "
            "style-src 'self' https://unpkg.com 'unsafe-inline'; "
            "img-src 'self' data: blob: https://*.tile.openstreetmap.org; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
