from datetime import datetime, timezone

from extensions import db


class MapItem(db.Model):

    __tablename__ = "map_items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    address = db.Column(
        db.Text
    )

    category = db.Column(
        db.String(40),
        nullable=False,
        default="other"
    )

    item_type = db.Column(
        db.String(20),
        nullable=False,
        default="marker"
    )

    latitude = db.Column(
        db.Float,
        nullable=False
    )

    longitude = db.Column(
        db.Float,
        nullable=False
    )

    geometry = db.Column(
        db.JSON,
        nullable=True
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    is_public = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    owner = db.relationship(
        "User",
        back_populates="locations"
    )

    photos = db.relationship(
        "Photo",
        back_populates="location",
        cascade="all, delete-orphan"
    )
