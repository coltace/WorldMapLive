from datetime import datetime, timezone

from flask_login import UserMixin

from extensions import db


class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="user"
    )

    avatar_url = db.Column(
        db.String(500)
    )

    is_verified = db.Column(
        db.Boolean,
        default=False
    )

    is_active_account = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    locations = db.relationship(
        "MapItem",
        back_populates="owner",
        lazy=True
    )

    def is_active(self):
        return self.is_active_account
