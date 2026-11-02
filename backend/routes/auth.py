from flask import (
    Blueprint,
    request,
    jsonify
)

from flask_login import (
    login_user,
    logout_user,
    current_user,
    login_required
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from extensions import db, limiter

from backend.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
@limiter.limit("5 per hour")
def register():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()

    email = str(data.get("email", "")).strip().lower()

    password = data.get("password", "")

    if not name or len(name) > 100:
        return jsonify({
            "error": "Invalid name"
        }), 400

    if len(email) > 255 or "@" not in email:
        return jsonify({
            "error": "Invalid email"
        }), 400

    if not isinstance(password, str) or len(password) < 10:
        return jsonify({
            "error": "Password must contain at least 10 characters"
        }), 400

    existing = db.session.scalar(
        db.select(User).where(User.email == email)
    )

    if existing:
        return jsonify({
            "error": "Email already registered"
        }), 409

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role="user"
    )

    db.session.add(user)
    db.session.commit()

    login_user(user)

    return jsonify({
        "message": "Account created",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }), 201


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():

    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()

    password = data.get("password", "")

    if not isinstance(password, str):
        return jsonify({"error": "Invalid credentials"}), 401

    user = db.session.scalar(
        db.select(User).where(User.email == email)
    )

    if (
        not user
        or not user.is_active_account
        or not check_password_hash(
            user.password_hash,
            password
        )
    ):

        return jsonify({
            "error": "Invalid credentials"
        }), 401

    login_user(user)

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    })


@auth_bp.post("/logout")
@login_required
def logout():

    logout_user()

    return jsonify({
        "message": "Logged out"
    })


@auth_bp.get("/me")
@login_required
def me():

    return jsonify({
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    })
