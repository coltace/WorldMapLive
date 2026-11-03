import re

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.models.user import User
from extensions import db, limiter

auth_bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _public_user(user):
    return {"id": user.id, "name": user.name, "email": user.email}


@auth_bp.post("/register")
@limiter.limit("5 per hour")
def register():
    data = _payload()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return jsonify({"error": "Invalid name"}), 400
    if not isinstance(email, str) or len(email.strip()) > 255 or not EMAIL_RE.fullmatch(email.strip()):
        return jsonify({"error": "Invalid email"}), 400
    email = email.strip().lower()
    if not isinstance(password, str) or len(password) < 10:
        return jsonify({"error": "Password must contain at least 10 characters"}), 400

    if db.session.scalar(db.select(User).where(User.email == email)):
        return jsonify({"error": "Email already registered"}), 409

    user = User(name=name.strip(), email=email, password_hash=generate_password_hash(password), role="user")
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email already registered"}), 409
    login_user(user)
    return jsonify({"message": "Account created", "user": _public_user(user)}), 201


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = _payload()
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid credentials"}), 401
    user = db.session.scalar(db.select(User).where(User.email == email.strip().lower()))
    if not user or not user.is_active_account or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401
    login_user(user)
    return jsonify({"message": "Login successful", "user": _public_user(user)})


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({**_public_user(current_user), "role": current_user.role})
