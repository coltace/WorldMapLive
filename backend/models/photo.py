from datetime import datetime, timezone

from extensions import db


class Photo(db.Model):

    __tablename__ = "photos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("map_items.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    image_path = db.Column(
        db.String(500),
        nullable=False
    )

    caption = db.Column(
        db.String(500)
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    location = db.relationship(
        "MapItem",
        back_populates="photos"
    )
