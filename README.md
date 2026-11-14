# WorldMapLive

WorldMapLive is a Flask application with a Leaflet map for exploring public, approved places and submitting new places for moderation. Accounts use Flask-Login sessions; writes are protected by Flask-WTF CSRF tokens. Locations are stored through SQLAlchemy.

## Requirements

- Python 3.10 or newer
- pip

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python scripts/init_db.py
python app.py
```

`flask --app app db upgrade` (or `python scripts/init_db.py`) applies the committed migrations and creates or updates the schema. You only need to run one of these commands. Open <http://127.0.0.1:5000>. Keep the generated `SECRET_KEY` private and stable between restarts. For deployments, provide `SECRET_KEY` and `DATABASE_URL` through the hosting platform's secret/environment settings, serve over HTTPS, and set `SESSION_COOKIE_SECURE=true`. The default database URI is SQLite; `UPLOAD_FOLDER` can be set to a writable persistent directory.

For an existing database whose tables were created with `db.create_all()`, do not run the initial migration upgrade directly: it will attempt to create tables that already exist. After backing up the database and verifying that its schema matches the initial migration, mark that migration as applied with `flask --app app db stamp head`. Run `db upgrade` normally after that to apply future migrations. Do not stamp a database whose schema has not been checked.

## Tests

```bash
python -m pip install -r requirements-dev.txt
pytest
```

The public listing endpoint exposes only approved public locations. New submissions remain pending until a moderation workflow approves them. Authentication and location endpoints are under `/api/auth` and `/api/locations`; `/api/health` is a basic liveness check.


## Moderation

Create an account through the site, then promote it from a trusted shell:

```bash
python scripts/promote_admin.py admin@example.com
```

The helper requires the same `SECRET_KEY` and database settings as the app. Staff can review up to 500 oldest pending submissions with `GET /api/locations/pending` and approve or reject one with `POST /api/locations/<id>/review` using `{"status":"approved"}` or `{"status":"rejected"}`. These requests require a signed-in admin/moderator session and a valid CSRF token. Regular users cannot access the queue or review endpoint.
