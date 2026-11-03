import re

import pytest

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
        db.create_all()
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


def test_homepage_renders_map_and_csrf_token(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="map"' in response.data
    assert b'name="csrf-token"' in response.data
    assert b"js/markers.js" not in response.data


def test_local_frontend_assets_are_served(client):
    response = client.get("/static/js/auth.js")
    assert response.status_code == 200
    assert b"WorldMapAPI" in response.data


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "online"


def test_unauthenticated_api_requests_return_json_401(client):
    response = client.post("/api/locations", json={"name": "Somewhere"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}


def test_account_registration_login_and_logout(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "user@example.com"
    assert client.get("/api/auth/me").status_code == 200

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    response = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "correct-horse-battery",
    })
    assert response.status_code == 200
    assert response.get_json()["user"]["name"] == "Test User"


def test_registration_rejects_short_password(client):
    response = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "user@example.com",
        "password": "short",
    })
    assert response.status_code == 400
    assert "10 characters" in response.get_json()["error"]


def test_location_submission_is_pending_and_not_public(client):
    assert register(client).status_code == 201
    response = client.post("/api/locations", json={
        "name": "Test place",
        "category": "landmark",
        "lat": 51.5,
        "lng": -0.12,
        "type": "marker",
    })
    assert response.status_code == 201
    item_id = response.get_json()["location"]["id"]
    assert client.get("/api/locations").get_json() == []
    assert client.get(f"/api/locations/{item_id}").status_code == 200


def test_location_rejects_out_of_range_coordinates(client):
    assert register(client).status_code == 201
    response = client.post("/api/locations", json={
        "name": "Invalid place",
        "category": "other",
        "lat": 95,
        "lng": 0,
    })
    assert response.status_code == 400
    assert "Coordinates" in response.get_json()["error"]


def test_location_rejects_malformed_geojson_and_non_object_payload(client):
    assert register(client).status_code == 201
    response = client.post("/api/locations", json={
        "name": "Invalid shape",
        "lat": 0,
        "lng": 0,
        "type": "polygon",
        "geometry": {"type": [], "coordinates": [0, 0]},
    })
    assert response.status_code == 400
    assert response.get_json()["error"] == "Valid GeoJSON geometry is required"

    response = client.post("/api/locations", json=["not", "an", "object"])
    assert response.status_code == 400


def test_csrf_token_from_homepage_authorizes_registration(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.db'}",
        "WTF_CSRF_ENABLED": True,
        "RATELIMIT_ENABLED": False,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    with app.app_context():
        db.create_all()
    client = app.test_client()

    payload = {"name": "CSRF Test", "email": "csrf@example.com", "password": "correct-horse-battery"}
    assert client.post("/api/auth/register", json=payload).status_code == 400

    page = client.get("/")
    token_match = re.search(rb'<meta name="csrf-token" content="([^"]+)"', page.data)
    assert token_match
    response = client.post(
        "/api/auth/register",
        json=payload,
        headers={"X-CSRFToken": token_match.group(1).decode()},
    )
    assert response.status_code == 201


def test_staff_can_review_pending_location_and_regular_users_cannot(app, client):
    assert register(client).status_code == 201
    created = client.post("/api/locations", json={
        "name": "Review me",
        "lat": 10,
        "lng": 20,
    })
    assert created.status_code == 201
    item_id = created.get_json()["location"]["id"]

    assert client.get("/api/locations/pending").status_code == 403
    with app.app_context():
        from backend.models.user import User
        user = db.session.scalar(db.select(User).where(User.email == "user@example.com"))
        user.role = "moderator"
        db.session.commit()

    pending = client.get("/api/locations/pending")
    assert pending.status_code == 200
    assert [item["id"] for item in pending.get_json()] == [item_id]
    invalid = client.post(f"/api/locations/{item_id}/review", json={"status": []})
    assert invalid.status_code == 400
    approved = client.post(f"/api/locations/{item_id}/review", json={"status": "approved"})
    assert approved.status_code == 200
    assert approved.get_json()["location"]["id"] == item_id
    assert [item["id"] for item in client.get("/api/locations").get_json()] == [item_id]
