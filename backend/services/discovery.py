from difflib import SequenceMatcher
import math
import unicodedata

from sqlalchemy import and_, or_

from backend.models.location import MapItem
from extensions import db

MAX_GEO_CANDIDATES = 300
MAX_DUPLICATE_RESULTS = 5
DUPLICATE_SEARCH_RADIUS_KM = 1.0


def normalize_text(value):
    """Normalize user-entered text for comparison without changing stored values."""
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value.casefold())
    characters = []
    for character in value:
        if unicodedata.category(character) == "Mn":
            continue
        characters.append(character if character.isalnum() else " ")
    return " ".join("".join(characters).split())


def address_text(item):
    parts = [
        " ".join(value for value in (item.house_number, item.street) if value),
        item.area,
        item.city,
        item.state,
        item.postal_code,
        item.country,
        item.address,
    ]
    return ", ".join(value.strip() for value in parts if isinstance(value, str) and value.strip())


def distance_km(lat1, lng1, lat2, lng2):
    """Return great-circle distance between two coordinate pairs."""
    earth_radius_km = 6371.0088
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _longitude_filter(lat, lng, radius_km):
    cosine = abs(math.cos(math.radians(lat)))
    if cosine < 1e-6:
        return None
    delta = min(180.0, radius_km / (111.320 * cosine))
    if delta >= 180:
        return None
    minimum, maximum = lng - delta, lng + delta
    if minimum < -180:
        return or_(MapItem.longitude >= minimum + 360, MapItem.longitude <= maximum)
    if maximum > 180:
        return or_(MapItem.longitude >= minimum, MapItem.longitude <= maximum - 360)
    return MapItem.longitude.between(minimum, maximum)


def _nearby_query(lat, lng, radius_km, include_pending=False, category=None, limit=MAX_GEO_CANDIDATES):
    latitude_delta = radius_km / 110.574
    minimum_lat = max(-90.0, lat - latitude_delta)
    maximum_lat = min(90.0, lat + latitude_delta)
    filters = [MapItem.latitude.between(minimum_lat, maximum_lat)]
    longitude_filter = _longitude_filter(lat, lng, radius_km)
    if longitude_filter is not None:
        filters.append(longitude_filter)
    if include_pending:
        visibility = or_(
            and_(MapItem.status == "approved", MapItem.is_public.is_(True)),
            MapItem.status == "pending",
        )
        filters.append(visibility)
    else:
        filters.extend((MapItem.status == "approved", MapItem.is_public.is_(True)))
    if category:
        filters.append(MapItem.category == category)

    cosine = math.cos(math.radians(lat))
    lat_delta = MapItem.latitude - lat
    wrapped_lng_delta = ((MapItem.longitude - lng + 540.0) % 360.0) - 180.0
    lng_delta = wrapped_lng_delta * cosine
    approximate_distance = lat_delta * lat_delta + lng_delta * lng_delta
    return db.select(MapItem).where(*filters).order_by(approximate_distance, MapItem.id).limit(limit)


def nearby_candidates(lat, lng, radius_km, include_pending=False, category=None, limit=MAX_GEO_CANDIDATES):
    statement = _nearby_query(lat, lng, radius_km, include_pending, category, limit)
    return db.session.scalars(statement).all()


def recommend_locations(lat, lng, radius_km=10.0, category=None, limit=10):
    candidates = nearby_candidates(lat, lng, radius_km, category=category)
    results = []
    for item in candidates:
        distance = distance_km(lat, lng, item.latitude, item.longitude)
        if distance > radius_km:
            continue
        proximity = max(0.0, 1.0 - distance / radius_km)
        score = min(1.0, proximity * 0.8 + (0.2 if category and item.category == category else 0.0))
        reasons = ["nearby"]
        if category and item.category == category:
            reasons.append("matches_selected_category")
        results.append({"location": item, "distance_km": distance, "score": round(score, 4), "reasons": reasons})
    results.sort(key=lambda result: (-result["score"], result["distance_km"], result["location"].id))
    return results[:limit]


def _match_candidate(name_key, address_key, item, lat, lng):
    candidate_name = normalize_text(item.name)
    candidate_address = normalize_text(address_text(item))
    name_ratio = SequenceMatcher(None, name_key, candidate_name).ratio() if name_key and candidate_name else 0.0
    address_ratio = SequenceMatcher(None, address_key, candidate_address).ratio() if address_key and candidate_address else 0.0
    distance_m = distance_km(lat, lng, item.latitude, item.longitude) * 1000
    same_name = name_key == candidate_name or name_ratio >= 0.86
    same_address = bool(address_key and candidate_address) and (
        address_key == candidate_address or address_ratio >= 0.92
    )
    if not ((distance_m <= 250 and (same_name or same_address)) or (distance_m <= 1000 and same_address and address_ratio >= 0.98)):
        return None
    reasons = []
    if same_name:
        reasons.append("similar_name")
    if same_address:
        reasons.append("similar_address")
    reasons.append("nearby")
    return {
        "id": item.id,
        "name": item.name,
        "address": address_text(item),
        "category": item.category,
        "lat": item.latitude,
        "lng": item.longitude,
        "distance_m": round(distance_m),
        "match_reasons": reasons,
        "status": item.status,
    }


def find_duplicate_candidates(name, address, lat, lng, include_pending=False, exclude_id=None):
    name_key = normalize_text(name)
    address_key = normalize_text(address)
    candidates = nearby_candidates(
        lat,
        lng,
        DUPLICATE_SEARCH_RADIUS_KM,
        include_pending=include_pending,
    )
    matches = []
    for item in candidates:
        if exclude_id is not None and item.id == exclude_id:
            continue
        match = _match_candidate(name_key, address_key, item, lat, lng)
        if match:
            matches.append(match)
    matches.sort(key=lambda result: (result["distance_m"], result["id"]))
    limited = matches[:MAX_DUPLICATE_RESULTS]
    if include_pending:
        grouped = {"approved_public": [], "pending_review": []}
        for result in limited:
            group = "pending_review" if result["status"] == "pending" else "approved_public"
            result.pop("status")
            grouped[group].append(result)
        return grouped, len(matches) > len(limited)
    for result in limited:
        result.pop("status")
    return limited, len(matches) > len(limited)
