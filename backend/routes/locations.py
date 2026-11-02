from flask import (
    Blueprint,
    request,
    jsonify
)

from flask_login import (
    current_user,
    login_required
)

from sqlalchemy import and_

from extensions import db

from backend.models.location import MapItem

locations_bp = Blueprint(
    "locations",
    __name__
)


ALLOWED_CATEGORIES = {
    "home",
    "business",
    "landmark",
    "park",
    "other"
}


def serialize_location(item):

    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "address": item.address,
        "category": item.category,
        "type": item.item_type,
        "lat": item.latitude,
        "lng": item.longitude,
        "geometry": item.geometry,
        "created_at": item.created_at.isoformat()
    }


@locations_bp.get("")
def get_locations():

    query = db.select(MapItem).where(
        MapItem.status == "approved",
        MapItem.is_public.is_(True)
    )

    category = request.args.get("category")

    if category in ALLOWED_CATEGORIES:

        query = query.where(
            MapItem.category == category
        )

    results = db.session.scalars(
        query.order_by(MapItem.created_at.desc()).limit(500)
    ).all()

    return jsonify([
        serialize_location(item)
        for item in results
    ])


@locations_bp.post("")
@login_required
def create_location():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()

    category = data.get("category", "other")

    item_type = data.get("type", "marker")

    if not name or len(name) > 200:

        return jsonify({
            "error": "Invalid location name"
        }), 400

    if category not in ALLOWED_CATEGORIES:

        return jsonify({
            "error": "Invalid category"
        }), 400

    if item_type not in {"marker", "polygon", "rectangle"}:

        return jsonify({
            "error": "Invalid location type"
        }), 400

    try:

        lat = float(data.get("lat"))

        lng = float(data.get("lng"))

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid coordinates"
        }), 400

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):

        return jsonify({
            "error": "Coordinates outside valid range"
        }), 400

    geometry = data.get("geometry")

    if item_type == "marker":
        geometry = None

    elif not isinstance(geometry, dict):
        return jsonify({
            "error": "Valid GeoJSON geometry is required"
        }), 400

    item = MapItem(
        user_id=current_user.id,
        name=name,
        description=str(data.get("description", ""))[:5000],
        address=str(data.get("address", ""))[:1000],
        category=category,
        item_type=item_type,
        latitude=lat,
        longitude=lng,
        geometry=geometry,
        status="pending",
        is_public=True
    )

    db.session.add(item)

    db.session.commit()

    return jsonify({
        "message": "Location submitted for review",
        "location": serialize_location(item)
    }), 201


@locations_bp.get("/<int:item_id>")
def get_location(item_id):

    item = db.session.get(MapItem, item_id)

    if not item:
        return jsonify({"error": "Not found"}), 404

    if item.status != "approved" or not item.is_public:

        if not current_user.is_authenticated:
            return jsonify({"error": "Not found"}), 404

        if (
            item.user_id != current_user.id
            and current_user.role not in {"admin", "moderator"}
        ):
            return jsonify({"error": "Not found"}), 404

    return jsonify(serialize_location(item))


@locations_bp.patch("/<int:item_id>")
@login_required
def update_location(item_id):

    item = db.session.get(MapItem, item_id)

    if not item:
        return jsonify({"error": "Not found"}), 404

    if (
        item.user_id != current_user.id
        and current_user.role not in {"admin", "moderator"}
    ):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}

    if "name" in data:

        name = str(data["name"]).strip()

        if not name or len(name) > 200:
            return jsonify({"error": "Invalid name"}), 400

        item.name = name

    if "description" in data:
        item.description = str(data["description"])[:5000]

    if "address" in data:
        item.address = str(data["address"])[:1000]

    if "category" in data:

        if data["category"] not in ALLOWED_CATEGORIES:
            return jsonify({"error": "Invalid category"}), 400

        item.category = data["category"]

    if "lat" in data or "lng" in data:

        try:

            lat = float(data.get("lat", item.latitude))

            lng = float(data.get("lng", item.longitude))

        except (TypeError, ValueError):

            return jsonify({"error": "Invalid coordinates"}), 400

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400

        item.latitude = lat
        item.longitude = lng

    # Community edits return to moderation.
    if current_user.role not in {"admin", "moderator"}:
        item.status = "pending"

    db.session.commit()

    return jsonify({
        "message": "Location updated",
        "location": serialize_location(item)
    })


@locations_bp.delete("/<int:item_id>")
@login_required
def delete_location(item_id):

    item = db.session.get(MapItem, item_id)

    if not item:
        return jsonify({"error": "Not found"}), 404

    if (
        item.user_id != current_user.id
        and current_user.role not in {"admin", "moderator"}
    ):
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(item)

    db.session.commit()

    return jsonify({
        "message": "Location deleted"
    })
