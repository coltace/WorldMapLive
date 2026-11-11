import math

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from backend.models.location import MapItem
from backend.services.geocoding import geocoding_service
from extensions import db

locations_bp = Blueprint("locations", __name__)

ALLOWED_CATEGORIES = {"home", "business", "landmark", "park", "other"}
ALLOWED_TYPES = {"marker", "polygon", "rectangle"}


def _payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _is_position(value):
    if not isinstance(value, list) or len(value) < 2:
        return False
    if any(not isinstance(part, (int, float)) or isinstance(part, bool) for part in value):
        return False
    if not all(math.isfinite(part) for part in value):
        return False
    longitude, latitude = value[:2]
    return -180 <= longitude <= 180 and -90 <= latitude <= 90


def _is_polygon_coordinates(coordinates):
    if not isinstance(coordinates, list) or not coordinates:
        return False
    for ring in coordinates:
        if not isinstance(ring, list) or len(ring) < 4 or not all(_is_position(point) for point in ring):
            return False
        if ring[0][:2] != ring[-1][:2]:
            return False
    return True


def _geometry_is_valid(item_type, geometry):
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(geometry_type, str):
        return False
    if geometry_type == "Polygon":
        return _is_polygon_coordinates(coordinates)
    if item_type == "polygon" and geometry_type == "MultiPolygon":
        return (
            isinstance(coordinates, list)
            and bool(coordinates)
            and all(_is_polygon_coordinates(polygon) for polygon in coordinates)
        )
    return False


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
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@locations_bp.get("/geocode")
def geocode_address():
    address = request.args.get("q", "").strip()

    if not address or len(address) > 300:
        return jsonify({"error": "Enter a valid address"}), 400

    result = geocoding_service.get_coordinates(address)

    if not result:
        return jsonify({"error": "Address not found or geocoding unavailable"}), 404

    return jsonify(result)


@locations_bp.get("/reverse-geocode")
def reverse_geocode():
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid coordinates are required"}), 400

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates outside valid range"}), 400

    address = geocoding_service.get_address(lat, lng)

    if not address:
        return jsonify({"error": "Address lookup unavailable"}), 404

    return jsonify({"address": address})


@locations_bp.get("")
def get_locations():
    query = db.select(MapItem).where(
        MapItem.status == "approved",
        MapItem.is_public.is_(True),
    )
    category = request.args.get("category")
    if category in ALLOWED_CATEGORIES:
        query = query.where(MapItem.category == category)
    results = db.session.scalars(query.order_by(MapItem.created_at.desc()).limit(500)).all()
    return jsonify([serialize_location(item) for item in results])


@locations_bp.post("")
@login_required
def create_location():
    data = _payload()
    name = data.get("name")
    category = data.get("category", "other")
    item_type = data.get("type", "marker")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        return jsonify({"error": "Invalid location name"}), 400
    if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    if not isinstance(item_type, str) or item_type not in ALLOWED_TYPES:
        return jsonify({"error": "Invalid location type"}), 400
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates outside valid range"}), 400

    geometry = data.get("geometry")
    if item_type == "marker":
        geometry = None
    elif not _geometry_is_valid(item_type, geometry):
        return jsonify({"error": "Valid GeoJSON geometry is required"}), 400

    description = data.get("description", "")
    address = data.get("address", "")
    if not isinstance(description, str) or not isinstance(address, str):
        return jsonify({"error": "Description and address must be text"}), 400

    item = MapItem(
        user_id=current_user.id,
        name=name.strip(),
        description=description[:5000],
        address=address[:1000],
        category=category,
        item_type=item_type,
        latitude=lat,
        longitude=lng,
        geometry=geometry,
        status="pending",
        is_public=True,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({
        "message": "Location submitted for review",
        "location": serialize_location(item),
    }), 201


@locations_bp.get("/pending")
@login_required
def get_pending_locations():
    if current_user.role not in {"admin", "moderator"}:
        return jsonify({"error": "Forbidden"}), 403
    query = db.select(MapItem).where(MapItem.status == "pending")
    items = db.session.scalars(query.order_by(MapItem.created_at.asc()).limit(500)).all()
    return jsonify([serialize_location(item) for item in items])


@locations_bp.post("/<int:item_id>/review")
@login_required
def review_location(item_id):
    if current_user.role not in {"admin", "moderator"}:
        return jsonify({"error": "Forbidden"}), 403
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    status = _payload().get("status")
    if not isinstance(status, str) or status not in {"approved", "rejected"}:
        return jsonify({"error": "Status must be approved or rejected"}), 400
    item.status = status
    db.session.commit()
    return jsonify({"message": f"Location {status}", "location": serialize_location(item)})


@locations_bp.get("/<int:item_id>")
def get_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.status != "approved" or not item.is_public:
        if not current_user.is_authenticated:
            return jsonify({"error": "Not found"}), 404
        if item.user_id != current_user.id and current_user.role not in {"admin", "moderator"}:
            return jsonify({"error": "Not found"}), 404
    return jsonify(serialize_location(item))


@locations_bp.patch("/<int:item_id>")
@login_required
def update_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.user_id != current_user.id and current_user.role not in {"admin", "moderator"}:
        return jsonify({"error": "Forbidden"}), 403
    data = _payload()
    if not data:
        return jsonify({"error": "A JSON object is required"}), 400

    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            return jsonify({"error": "Invalid name"}), 400
        item.name = name.strip()
    if "description" in data:
        if not isinstance(data["description"], str):
            return jsonify({"error": "Description must be text"}), 400
        item.description = data["description"][:5000]
    if "address" in data:
        if not isinstance(data["address"], str):
            return jsonify({"error": "Address must be text"}), 400
        item.address = data["address"][:1000]
    if "category" in data:
        category = data["category"]
        if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
            return jsonify({"error": "Invalid category"}), 400
        item.category = category
    if "lat" in data or "lng" in data:
        try:
            lat = float(data.get("lat", item.latitude))
            lng = float(data.get("lng", item.longitude))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400
        item.latitude, item.longitude = lat, lng

    if current_user.role not in {"admin", "moderator"}:
        item.status = "pending"
    db.session.commit()
    return jsonify({"message": "Location updated", "location": serialize_location(item)})


@locations_bp.delete("/<int:item_id>")
@login_required
def delete_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.user_id != current_user.id and current_user.role not in {"admin", "moderator"}:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Location deleted"})
