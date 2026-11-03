import os

from flask import Flask, jsonify, render_template

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

    @app.get("/api/health")
    def health():
        return jsonify({"status": "online", "application": "WorldMap Live"})

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
