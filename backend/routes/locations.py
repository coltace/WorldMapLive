import math
import uuid
from io import BytesIO
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory, url_for
from flask_login import current_user, login_required
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from backend.models.location import MapItem
from backend.models.photo import Photo
from backend.services.discovery import address_text, find_duplicate_candidates, recommend_locations
from backend.services.geocoding import geocoding_service
from extensions import db, limiter

locations_bp = Blueprint("locations", __name__)
ALLOWED_CATEGORIES = {"home", "business", "landmark", "park", "other"}
ALLOWED_TYPES = {"marker", "polygon", "rectangle"}
STAFF_ROLES = {"admin", "moderator"}
ADDRESS_FIELDS = {
    "house_number": 40,
    "street": 200,
    "area": 150,
    "city": 150,
    "state": 150,
    "country": 150,
    "postal_code": 40,
}
MAX_PHOTO_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


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
        return isinstance(coordinates, list) and bool(coordinates) and all(
            _is_polygon_coordinates(polygon) for polygon in coordinates
        )
    return False


def _approved_photos(item):
    return [photo for photo in item.photos if photo.status == "approved"]


def serialize_location(item, include_private=False):
    photos = _approved_photos(item)
    result = {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "address": item.address,
        "house_number": item.house_number,
        "street": item.street,
        "area": item.area,
        "city": item.city,
        "state": item.state,
        "country": item.country,
        "postal_code": item.postal_code,
        "category": item.category,
        "type": item.item_type,
        "lat": item.latitude,
        "lng": item.longitude,
        "geometry": item.geometry,
        "photos": [serialize_photo(photo) for photo in photos],
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
    if include_private:
        result.update({
            "status": item.status,
            "owner_id": item.user_id,
            "photos_pending": sum(photo.status == "pending" for photo in item.photos),
        })
    return result


def serialize_photo(photo):
    return {
        "id": photo.id,
        "caption": photo.caption,
        "url": url_for("locations.photo_image", item_id=photo.location_id, photo_id=photo.id),
    }


def _staff():
    return current_user.is_authenticated and current_user.role in STAFF_ROLES


def _user_rate_key():
    user_id = current_user.get_id()
    return f"user:{user_id}" if user_id else request.remote_addr or "anonymous"


def _validated_address(data):
    values = {}
    for field, limit in ADDRESS_FIELDS.items():
        value = data.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str) or len(value.strip()) > limit:
            return None
        values[field] = value.strip() or None
    return values


def _make_address(data, fields):
    address = data.get("address", "")
    if not isinstance(address, str) or len(address) > 1000:
        return None
    return address.strip() or ", ".join(
        part for part in [
            " ".join(filter(None, [fields["house_number"], fields["street"]])),
            fields["area"], fields["city"], fields["state"], fields["postal_code"], fields["country"],
        ] if part
    )


def _duplicate_input(data):
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        return None
    category = data.get("category")
    if category is not None and (not isinstance(category, str) or category not in ALLOWED_CATEGORIES):
        return None
    try:
        lat, lng = float(data.get("lat")), float(data.get("lng"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    fields = _validated_address(data)
    if fields is None:
        return None
    address = _make_address(data, fields)
    if address is None:
        return None
    return {"name": name.strip(), "address": address, "lat": lat, "lng": lng}


@locations_bp.get("/geocode")
@limiter.limit("20 per minute")
def geocode_address():
    address = request.args.get("q", "").strip()
    if not address or len(address) > 300:
        return jsonify({"error": "Enter a valid address"}), 400
    result = geocoding_service.get_coordinates(address)
    if not result:
        return jsonify({"error": "Address not found or geocoding unavailable"}), 404
    return jsonify(result)


@locations_bp.get("/reverse-geocode")
@limiter.limit("20 per minute")
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
@limiter.limit("60 per minute")
def get_locations():
    query = db.select(MapItem).where(MapItem.status == "approved", MapItem.is_public.is_(True))
    category = request.args.get("category")
    if category in ALLOWED_CATEGORIES:
        query = query.where(MapItem.category == category)
    term = request.args.get("q", "").strip()
    if term:
        if len(term) > 100:
            return jsonify({"error": "Search text is too long"}), 400
        pattern = f"%{term.lower()}%"
        searchable = [MapItem.name, MapItem.description, MapItem.address] + [
            getattr(MapItem, field) for field in ADDRESS_FIELDS
        ]
        query = query.where(or_(*(db.func.lower(field).like(pattern) for field in searchable)))
    try:
        page = max(1, min(int(request.args.get("page", "1")), 100000))
    except ValueError:
        return jsonify({"error": "Invalid page"}), 400
    per_page = 100
    results = db.session.scalars(
        query.order_by(MapItem.created_at.desc(), MapItem.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return jsonify({"items": [serialize_location(item) for item in results], "page": page, "has_more": len(results) == per_page})


@locations_bp.get("/recommendations")
@limiter.limit("60 per minute")
def get_recommendations():
    try:
        lat, lng = float(request.args.get("lat")), float(request.args.get("lng"))
        radius_km = float(request.args.get("radius_km", "10"))
        limit = int(request.args.get("limit", "10"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid coordinates, radius, and limit are required"}), 400
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates outside valid range"}), 400
    if not math.isfinite(radius_km) or not (0.1 <= radius_km <= 50):
        return jsonify({"error": "Radius must be between 0.1 and 50 km"}), 400
    if not (1 <= limit <= 20):
        return jsonify({"error": "Limit must be between 1 and 20"}), 400
    category = request.args.get("category")
    if category and category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    results = recommend_locations(lat, lng, radius_km, category, limit)
    return jsonify({
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "items": [{
            "location": serialize_location(result["location"]),
            "distance_km": round(result["distance_km"], 2),
            "score": result["score"],
            "reasons": result["reasons"],
        } for result in results],
    })


@locations_bp.post("/duplicate-check")
@login_required
@limiter.limit("10 per minute", key_func=_user_rate_key)
def duplicate_check():
    payload = _duplicate_input(_payload())
    if payload is None:
        return jsonify({"error": "Provide a valid place name, address, and coordinates"}), 400
    candidates, truncated = find_duplicate_candidates(**payload)
    return jsonify({"candidates": candidates, "truncated": truncated, "advisory": True})


@locations_bp.post("")
@login_required
@limiter.limit("20 per hour")
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
        lat, lng = float(data.get("lat")), float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"error": "Coordinates outside valid range"}), 400
    geometry = data.get("geometry")
    if item_type == "marker":
        geometry = None
    elif not _geometry_is_valid(item_type, geometry) or len(str(geometry)) > 500_000:
        return jsonify({"error": "Valid GeoJSON geometry is required"}), 400
    description = data.get("description", "")
    if not isinstance(description, str):
        return jsonify({"error": "Description must be text"}), 400
    address_fields = _validated_address(data)
    if address_fields is None:
        return jsonify({"error": "One or more address fields are invalid"}), 400
    address = _make_address(data, address_fields)
    if address is None:
        return jsonify({"error": "Address must be text"}), 400
    item = MapItem(
        user_id=current_user.id, name=name.strip(), description=description[:5000], address=address[:1000],
        category=category, item_type=item_type, latitude=lat, longitude=lng, geometry=geometry,
        status="pending", is_public=True, **address_fields,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Location submitted for review", "location": serialize_location(item, True)}), 201


@locations_bp.get("/mine")
@login_required
def my_locations():
    items = db.session.scalars(
        db.select(MapItem).where(MapItem.user_id == current_user.id).order_by(MapItem.updated_at.desc()).limit(200)
    ).all()
    return jsonify([serialize_location(item, True) for item in items])


@locations_bp.get("/pending")
@login_required
def get_pending_locations():
    if not _staff():
        return jsonify({"error": "Forbidden"}), 403
    items = db.session.scalars(
        db.select(MapItem).where(MapItem.status == "pending").order_by(MapItem.created_at.asc()).limit(500)
    ).all()
    return jsonify([serialize_location(item, True) for item in items])


@locations_bp.get("/pending/<int:item_id>/duplicate-hints")
@login_required
def pending_duplicate_hints(item_id):
    if not _staff():
        return jsonify({"error": "Forbidden"}), 403
    item = db.session.get(MapItem, item_id)
    if not item or item.status != "pending":
        return jsonify({"error": "Not found"}), 404
    candidates, truncated = find_duplicate_candidates(
        item.name,
        address_text(item),
        item.latitude,
        item.longitude,
        include_pending=True,
        exclude_id=item.id,
    )
    return jsonify({"groups": candidates, "truncated": truncated})


@locations_bp.post("/<int:item_id>/review")
@login_required
def review_location(item_id):
    if not _staff():
        return jsonify({"error": "Forbidden"}), 403
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    status = _payload().get("status")
    if not isinstance(status, str) or status not in {"approved", "rejected"}:
        return jsonify({"error": "Status must be approved or rejected"}), 400
    item.status = status
    db.session.commit()
    return jsonify({"message": f"Location {status}", "location": serialize_location(item, True)})


@locations_bp.get("/photos/pending")
@login_required
def pending_photos():
    if not _staff():
        return jsonify({"error": "Forbidden"}), 403
    photos = db.session.scalars(db.select(Photo).where(Photo.status == "pending").order_by(Photo.created_at.asc()).limit(500)).all()
    return jsonify([{
        **serialize_photo(photo), "location_name": photo.location.name, "location_id": photo.location_id,
        "caption": photo.caption,
    } for photo in photos])


@locations_bp.post("/photos/<int:photo_id>/review")
@login_required
def review_photo(photo_id):
    if not _staff():
        return jsonify({"error": "Forbidden"}), 403
    photo = db.session.get(Photo, photo_id)
    if not photo:
        return jsonify({"error": "Not found"}), 404
    status = _payload().get("status")
    if not isinstance(status, str) or status not in {"approved", "rejected"}:
        return jsonify({"error": "Status must be approved or rejected"}), 400
    photo.status = status
    db.session.commit()
    if status == "rejected":
        _remove_photo_file(photo.image_path)
    return jsonify({"message": f"Photo {status}"})


def _photo_root():
    return Path(current_app.config["UPLOAD_FOLDER"]).resolve() / "photos"


def _remove_photo_file(filename):
    if filename and Path(filename).name == filename:
        try:
            (_photo_root() / filename).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("Unable to remove rejected/deleted photo")


@locations_bp.post("/<int:item_id>/photos")
@login_required
@limiter.limit("20 per hour")
def upload_photo(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.user_id != current_user.id and not _staff():
        return jsonify({"error": "Forbidden"}), 403
    if len(item.photos) >= 10:
        return jsonify({"error": "A place can have at most 10 photos"}), 400
    if "photo" not in request.files:
        return jsonify({"error": "Choose an image to upload"}), 400
    upload = request.files["photo"]
    if not upload.filename or len(upload.filename) > 255:
        return jsonify({"error": "Invalid image filename"}), 400
    if request.content_length and request.content_length > MAX_PHOTO_BYTES + 32_000:
        return jsonify({"error": "Image exceeds the 4 MB limit"}), 413
    image_bytes = upload.stream.read(MAX_PHOTO_BYTES + 1)
    if len(image_bytes) > MAX_PHOTO_BYTES:
        return jsonify({"error": "Image exceeds the 4 MB limit"}), 413
    caption = request.form.get("caption", "").strip()
    if len(caption) > 500:
        return jsonify({"error": "Caption is too long"}), 400
    # Decode and re-encode images: no user-controlled paths, metadata, or executable content is stored.
    try:
        image = Image.open(BytesIO(image_bytes))
        image_format = image.format
        if image_format not in ALLOWED_FORMATS or image.width * image.height > MAX_IMAGE_PIXELS:
            return jsonify({"error": "Use a JPEG, PNG, or WebP image under 20 megapixels"}), 400
        image = ImageOps.exif_transpose(image)
        image.load()
        image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return jsonify({"error": "The uploaded file is not a valid supported image"}), 400
    extension = ALLOWED_FORMATS[image_format]
    filename = f"{uuid.uuid4().hex}.{extension}"
    photo_root = _photo_root()
    photo_root.mkdir(parents=True, exist_ok=True)
    path = photo_root / filename
    try:
        if image_format == "JPEG":
            image.convert("RGB").save(path, format="JPEG", quality=88, optimize=True)
        elif image_format == "PNG":
            image.save(path, format="PNG", optimize=True)
        else:
            image.save(path, format="WEBP", quality=88, method=4)
    except OSError:
        current_app.logger.exception("Image save failed")
        return jsonify({"error": "Unable to save image"}), 500
    photo = Photo(
        location_id=item.id,
        user_id=current_user.id,
        image_path=filename,
        caption=caption or None,
        status="pending",
    )
    db.session.add(photo)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        _remove_photo_file(filename)
        return jsonify({"error": "Unable to save photo metadata"}), 500
    return jsonify({"message": "Photo submitted for moderation", "photo": serialize_photo(photo)}), 201


@locations_bp.get("/<int:item_id>/photos/<int:photo_id>/image")
def photo_image(item_id, photo_id):
    photo = db.session.get(Photo, photo_id)
    if not photo or photo.location_id != item_id:
        return jsonify({"error": "Not found"}), 404
    item = photo.location
    allowed_private = current_user.is_authenticated and (
        current_user.id == item.user_id or _staff()
    )
    if photo.status != "approved" and not allowed_private:
        return jsonify({"error": "Not found"}), 404
    if item.status != "approved" and not allowed_private:
        return jsonify({"error": "Not found"}), 404
    if Path(photo.image_path).name != photo.image_path:
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(_photo_root(), secure_filename(photo.image_path), max_age=3600)


@locations_bp.get("/<int:item_id>")
def get_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.status != "approved" or not item.is_public:
        if not current_user.is_authenticated or (item.user_id != current_user.id and not _staff()):
            return jsonify({"error": "Not found"}), 404
    return jsonify(serialize_location(item, current_user.is_authenticated and (item.user_id == current_user.id or _staff())))


@locations_bp.patch("/<int:item_id>")
@login_required
def update_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.user_id != current_user.id and not _staff():
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
    if "category" in data:
        if not isinstance(data["category"], str) or data["category"] not in ALLOWED_CATEGORIES:
            return jsonify({"error": "Invalid category"}), 400
        item.category = data["category"]
    if any(field in data for field in ADDRESS_FIELDS) or "address" in data:
        address_fields = {field: getattr(item, field) for field in ADDRESS_FIELDS}
        structured_changed = any(field in data for field in ADDRESS_FIELDS)
        if structured_changed:
            validated = _validated_address({**address_fields, **data})
            if validated is None:
                return jsonify({"error": "One or more address fields are invalid"}), 400
            for field, value in validated.items():
                setattr(item, field, value)
        address_input = data if "address" in data else {"address": "" if structured_changed else item.address}
        address = _make_address(address_input, {field: getattr(item, field) for field in ADDRESS_FIELDS})
        if address is None:
            return jsonify({"error": "Address must be text"}), 400
        item.address = address[:1000]
    if "lat" in data or "lng" in data:
        try:
            lat, lng = float(data.get("lat", item.latitude)), float(data.get("lng", item.longitude))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400
        item.latitude, item.longitude = lat, lng
    if not _staff():
        item.status = "pending"
    db.session.commit()
    return jsonify({"message": "Location updated; submitted for review" if not _staff() else "Location updated", "location": serialize_location(item, True)})


@locations_bp.delete("/<int:item_id>")
@login_required
def delete_location(item_id):
    item = db.session.get(MapItem, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.user_id != current_user.id and not _staff():
        return jsonify({"error": "Forbidden"}), 403
    filenames = [photo.image_path for photo in item.photos]
    db.session.delete(item)
    db.session.commit()
    for filename in filenames:
        _remove_photo_file(filename)
    return jsonify({"message": "Location deleted"})
