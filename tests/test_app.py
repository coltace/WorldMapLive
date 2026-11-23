import io
import re

import pytest
from PIL import Image
from flask_migrate import upgrade

from backend import create_app
from extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    with app.app_context():
        upgrade()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="user@example.com"):
    return client.post("/api/auth/register", json={
        "name": "Test User",
        "email": email,
        "password": "correct-horse-battery",
    })


def create_place(client, **overrides):
    payload = {
        "name": "Test place", "category": "home", "lat": 51.5, "lng": -0.12,
        "type": "marker", "house_number": "22B", "street": "Willow Lane",
        "area": "Old Town", "city": "Example City", "state": "Example State",
        "country": "Example Country", "postal_code": "AB12 3CD",
        "description": "A community-added home, not dependent on any map provider.",
    }
    payload.update(overrides)
    return client.post("/api/locations", json=payload)


def make_png():
    data = io.BytesIO()
    Image.new("RGB", (12, 8), color="blue").save(data, format="PNG")
    data.seek(0)
    return data


def test_homepage_renders_map_and_feature_controls(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="map"' in response.data
    assert b'name="csrf-token"' in response.data
    assert b'id="place-search"' in response.data
    assert b'name="house_number"' in response.data
    assert b'id="moderation-panel"' in response.data
    assert b'id="assistant-form"' in response.data
    assert b'id="recommendation-button"' in response.data
    assert b'id="auth-screen"' in response.data
    assert b'id="app-shell"' in response.data
    assert b"js/markers.js" not in response.data


def test_local_frontend_assets_are_served(client):
    response = client.get("/static/js/auth.js")
    assert response.status_code == 200
    assert b"WorldMapAPI" in response.data


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
    live = client.get("/api/health/live")
    assert live.status_code == 200
    assert live.get_json()["status"] == "alive"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_unauthenticated_api_requests_return_json_401(client):
    response = client.post("/api/locations", json={"name": "Somewhere"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}


def test_account_registration_login_and_logout(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "user@example.com"
    assert response.get_json()["user"]["role"] == "user"
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    response = client.post("/api/auth/login", json={"email": "user@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 200
    assert response.get_json()["user"]["name"] == "Test User"


def test_registration_rejects_short_password(client):
    response = client.post("/api/auth/register", json={"name": "Test User", "email": "user@example.com", "password": "short"})
    assert response.status_code == 400
    assert "10 characters" in response.get_json()["error"]


def test_create_place_with_full_custom_address_without_geocoder(app, client):
    assert register(client).status_code == 201
    response = create_place(client)
    assert response.status_code == 201
    location = response.get_json()["location"]
    assert location["house_number"] == "22B"
    assert location["street"] == "Willow Lane"
    assert location["city"] == "Example City"
    assert location["lat"] == 51.5
    assert location["status"] == "pending"
    assert "Willow Lane" in location["address"]
    public = client.get("/api/locations").get_json()
    assert public == {"items": [], "page": 1, "has_more": False}
    assert client.get(f"/api/locations/{location['id']}").status_code == 200


def test_location_rejects_out_of_range_coordinates_and_bad_address(client):
    assert register(client).status_code == 201
    assert create_place(client, lat=95).status_code == 400
    invalid = create_place(client, street={"unsafe": "object"})
    assert invalid.status_code == 400
    assert "address fields" in invalid.get_json()["error"]


def test_location_rejects_malformed_geojson_and_non_object_payload(client):
    assert register(client).status_code == 201
    response = client.post("/api/locations", json={"name": "Invalid shape", "lat": 0, "lng": 0, "type": "polygon", "geometry": {"type": [], "coordinates": [0, 0]}})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Valid GeoJSON geometry is required"
    assert client.post("/api/locations", json=["not", "an", "object"]).status_code == 400


def test_global_search_matches_custom_name_and_structured_address(client):
    register(client)
    created = create_place(client, name="Blue Cedar House")
    item_id = created.get_json()["location"]["id"]
    with client.application.app_context():
        from backend.models.location import MapItem
        item = db.session.get(MapItem, item_id)
        item.status = "approved"
        db.session.commit()
    by_name = client.get("/api/locations?q=cedar").get_json()
    by_address = client.get("/api/locations?q=AB12%203CD").get_json()
    assert [x["id"] for x in by_name["items"]] == [item_id]
    assert [x["id"] for x in by_address["items"]] == [item_id]
    assert client.get("/api/locations?q=" + "x" * 101).status_code == 400


def test_owner_can_edit_and_delete_but_other_user_cannot(app, client):
    register(client)
    item_id = create_place(client).get_json()["location"]["id"]
    assert client.patch(f"/api/locations/{item_id}", json={"name": "Updated House", "city": "New City"}).status_code == 200
    assert client.get("/api/locations/mine").get_json()[0]["status"] == "pending"

    other = app.test_client()
    assert register(other, "other@example.com").status_code == 201
    assert other.patch(f"/api/locations/{item_id}", json={"name": "Takeover"}).status_code == 403
    assert other.delete(f"/api/locations/{item_id}").status_code == 403
    assert client.delete(f"/api/locations/{item_id}").status_code == 200
    assert client.get(f"/api/locations/{item_id}").status_code == 404


def test_photo_upload_is_reencoded_private_then_moderated(app, client):
    register(client)
    item_id = create_place(client).get_json()["location"]["id"]
    invalid = client.post(f"/api/locations/{item_id}/photos", data={"photo": (io.BytesIO(b"not an image"), "evil.jpg")}, content_type="multipart/form-data")
    assert invalid.status_code == 400
    uploaded = client.post(f"/api/locations/{item_id}/photos", data={"photo": (make_png(), "../../house.png"), "caption": "Front of house"}, content_type="multipart/form-data")
    assert uploaded.status_code == 201
    photo = uploaded.get_json()["photo"]
    assert photo["url"].startswith("/api/locations/")
    assert client.get(photo["url"]).status_code == 200  # owner can preview their pending submission

    staffify(app, "user@example.com", "admin")
    queue = client.get("/api/locations/photos/pending")
    assert queue.status_code == 200
    assert queue.get_json()[0]["id"] == photo["id"]
    assert client.post(f"/api/locations/photos/{photo['id']}/review", json={"status": "approved"}).status_code == 200
    with app.app_context():
        from backend.models.location import MapItem
        db.session.get(MapItem, item_id).status = "approved"
        db.session.commit()
    assert client.get(photo["url"]).status_code == 200


def test_photo_upload_rejects_oversize_and_non_owner(app, client):
    register(client)
    item_id = create_place(client).get_json()["location"]["id"]
    other = app.test_client()
    assert register(other, "photo-other@example.com").status_code == 201
    denied = other.post(f"/api/locations/{item_id}/photos", data={"photo": (make_png(), "house.png")}, content_type="multipart/form-data")
    assert denied.status_code == 403
    too_large = client.post(
        f"/api/locations/{item_id}/photos",
        data={"photo": (io.BytesIO(b"x" * (4 * 1024 * 1024 + 1)), "large.png")},
        content_type="multipart/form-data",
    )
    assert too_large.status_code == 413


def test_photo_review_rejects_non_string_status(client, app):
    register(client)
    item_id = create_place(client).get_json()["location"]["id"]
    photo_response = client.post(f"/api/locations/{item_id}/photos", data={"photo": (make_png(), "house.png")}, content_type="multipart/form-data")
    photo_id = photo_response.get_json()["photo"]["id"]
    staffify(app, "user@example.com", "moderator")
    response = client.post(f"/api/locations/photos/{photo_id}/review", json={"status": []})
    assert response.status_code == 400


def staffify(app, email, role):
    with app.app_context():
        from backend.models.user import User
        user = db.session.scalar(db.select(User).where(User.email == email))
        user.role = role
        db.session.commit()


def test_moderation_roles_and_approval(client, app):
    register(client)
    created = create_place(client, name="Review me")
    item_id = created.get_json()["location"]["id"]
    assert client.get("/api/locations/pending").status_code == 403
    staffify(app, "user@example.com", "moderator")
    pending = client.get("/api/locations/pending").get_json()
    assert [item["id"] for item in pending] == [item_id]
    assert client.post(f"/api/locations/{item_id}/review", json={"status": []}).status_code == 400
    approved = client.post(f"/api/locations/{item_id}/review", json={"status": "approved"})
    assert approved.status_code == 200
    assert [item["id"] for item in client.get("/api/locations").get_json()["items"]] == [item_id]


def test_csrf_token_from_homepage_authorizes_registration(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-only-secret", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.db'}", "WTF_CSRF_ENABLED": True, "RATELIMIT_ENABLED": False, "UPLOAD_FOLDER": str(tmp_path / "uploads")})
    with app.app_context(): upgrade()
    client = app.test_client()
    payload = {"name": "CSRF Test", "email": "csrf@example.com", "password": "correct-horse-battery"}
    assert client.post("/api/auth/register", json=payload).status_code == 400
    page = client.get("/")
    token_match = re.search(rb'<meta name="csrf-token" content="([^"]+)"', page.data)
    assert token_match
    response = client.post("/api/auth/register", json=payload, headers={"X-CSRFToken": token_match.group(1).decode()})
    assert response.status_code == 201


def test_upload_root_is_created_for_durable_storage_mount(app):
    from pathlib import Path
    assert Path(app.config["UPLOAD_FOLDER"]).is_dir()


def test_recommendations_are_bounded_and_only_return_approved_public_places(client, app):
    register(client)
    pending = create_place(client, name="Pending nearby")
    pending_id = pending.get_json()["location"]["id"]
    assert client.get("/api/locations/recommendations?lat=51.5&lng=-0.12&radius_km=10").get_json()["items"] == []
    with app.app_context():
        from backend.models.location import MapItem
        item = db.session.get(MapItem, pending_id)
        item.status = "approved"
        db.session.commit()
    response = client.get("/api/locations/recommendations?lat=51.5&lng=-0.12&radius_km=10")
    assert response.status_code == 200
    results = response.get_json()["items"]
    assert len(results) == 1
    assert results[0]["location"]["name"] == "Pending nearby"
    assert results[0]["distance_km"] == 0
    assert client.get("/api/locations/recommendations?lat=91&lng=0").status_code == 400
    assert client.get("/api/locations/recommendations?lat=0&lng=0&radius_km=51").status_code == 400


def test_recommendations_rank_nearby_places_across_antimeridian(client, app):
    register(client)
    far_id = create_place(client, name="Same-side farther", lat=0, lng=179.5).get_json()["location"]["id"]
    near_id = create_place(client, name="Across date line", lat=0, lng=-179.99).get_json()["location"]["id"]
    with app.app_context():
        from backend.models.location import MapItem
        for item_id in (far_id, near_id):
            db.session.get(MapItem, item_id).status = "approved"
        db.session.commit()
    response = client.get(
        "/api/locations/recommendations?lat=0&lng=179.9&radius_km=50&limit=1"
    )
    assert response.status_code == 200
    assert response.get_json()["items"][0]["location"]["id"] == near_id


def test_duplicate_check_is_private_advisory_and_never_blocks_submission(client, app):
    register(client)
    original = create_place(client, name="Cedar House")
    original_id = original.get_json()["location"]["id"]
    payload = {"name": "Cedar House", "street": "Willow Lane", "lat": 51.5, "lng": -0.12}
    pending_result = client.post("/api/locations/duplicate-check", json=payload)
    assert pending_result.status_code == 200
    assert pending_result.get_json()["candidates"] == []
    with app.app_context():
        from backend.models.location import MapItem
        db.session.get(MapItem, original_id).status = "approved"
        db.session.commit()
    response = client.post("/api/locations/duplicate-check", json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body["advisory"] is True
    assert body["candidates"][0]["id"] == original_id
    assert "user_id" not in body["candidates"][0]
    assert create_place(client, name="Cedar House").status_code == 201


def test_duplicate_hints_are_staff_only_and_group_pending_and_public_records(client, app):
    register(client)
    first = create_place(client, name="Cedar House").get_json()["location"]["id"]
    second = create_place(client, name="Cedar House").get_json()["location"]["id"]
    assert client.get(f"/api/locations/pending/{first}/duplicate-hints").status_code == 403
    staffify(app, "user@example.com", "moderator")
    response = client.get(f"/api/locations/pending/{first}/duplicate-hints")
    assert response.status_code == 200
    groups = response.get_json()["groups"]
    assert second in [item["id"] for item in groups["pending_review"]]


def test_assistant_requires_auth_valid_message_and_configuration(client, app, monkeypatch):
    assert client.post("/api/assistant/chat", json={"message": "Where is Cedar House?"}).status_code == 401
    register(client)
    assert client.post("/api/assistant/chat", json={"message": " "}).status_code == 400
    assert client.post("/api/assistant/chat", json={"message": "x" * 2001}).status_code == 400
    unavailable = client.post("/api/assistant/chat", json={"message": "Where is Cedar House?"})
    assert unavailable.status_code == 503
    app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_API_KEY="test-only", ASSISTANT_MODEL="test-model", ASSISTANT_BASE_URL="https://provider.example/v1")
    monkeypatch.setattr("backend.routes.assistant.generate_reply", lambda message, context: "Try the approved Cedar House.")
    reply = client.post("/api/assistant/chat", json={"message": "Where is Cedar House?"})
    assert reply.status_code == 200
    assert reply.get_json()["reply"] == "Try the approved Cedar House."


def test_assistant_provider_request_uses_only_approved_public_context(client, app, monkeypatch):
    register(client)
    approved_id = create_place(client, name="Cedar House").get_json()["location"]["id"]
    create_place(client, name="Cedar House Pending")
    with app.app_context():
        from backend.models.location import MapItem
        approved = db.session.get(MapItem, approved_id)
        approved.status = "approved"
        db.session.commit()
    app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_API_KEY="test-only", ASSISTANT_MODEL="test-model", ASSISTANT_BASE_URL="https://provider.example/v1")
    observed = {}

    class FakeResponse:
        status_code = 200
        def iter_content(self, chunk_size):
            import json
            yield json.dumps({"choices": [{"message": {"content": "No approved matches yet."}}]}).encode()
        def close(self): pass

    def fake_post(url, **kwargs):
        observed["request"] = {"url": url, "kwargs": kwargs}
        return FakeResponse()

    monkeypatch.setattr("backend.services.assistant.requests.post", fake_post)
    response = client.post("/api/assistant/chat", json={"message": "Tell me about Cedar House"})
    assert response.status_code == 200
    sent = observed["request"]["kwargs"]["json"]["messages"][1]["content"]
    import json
    provider_content = json.loads(sent)
    assert provider_content["question"] == "Tell me about Cedar House"
    assert [item["name"] for item in provider_content["approved_public_locations"]] == ["Cedar House"]
