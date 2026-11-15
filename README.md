# WorldMapLive

WorldMapLive is a Flask and Leaflet community map. People can add a custom place even when no commercial map or online directory knows about it, set its position by clicking the map or entering latitude/longitude, and submit it for moderation. Approved locations can be found by custom name and address. Accounts use Flask-Login sessions; writes use CSRF protection.

## Capabilities

- Create custom-named places with description, category, house number, street, area/neighborhood, city, state/region, country, and postal code. A geocoder is optional: a place can be created from manual coordinates even when no lookup result exists.
- Search approved places by custom name, description, or address fields. Search results are paginated (100 per page).
- View, edit, delete, and upload photographs for your own submissions. Owner edits return a place to pending review. Supported images are JPEG, PNG, and WebP, at most 4 MB and 20 megapixels; images are decoded and re-encoded before storage.
- Admins and moderators can review/approve/reject locations and photos from the in-page moderation panel.

**Privacy:** approved submissions are public, including their coordinates and any address fields provided. Do not submit a private residence or personal information unless you are authorized and intend it to be public.

## Requirements and local setup

- Python 3.10 or newer
- pip

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python scripts/init_db.py
python app.py
```

Open <http://127.0.0.1:5000>. Keep `SECRET_KEY` private and stable between restarts. Set `DATABASE_URL` for the database. `UPLOAD_FOLDER` defaults to the private `instance/uploads` directory (not Flask's public static directory); set it to a private writable persistent path for your environment.

## Database migrations

`python scripts/init_db.py` applies committed Alembic migrations. The latest migration adds structured address fields and indexes without deleting or rewriting the legacy free-form `address` column. Existing rows are retained and remain searchable by their old address text.

For an existing database whose tables were created with `db.create_all()` and have no Alembic revision, back it up first and verify its tables match the initial schema. Then mark only the initial migration as applied and run the newer migrations:

```bash
flask --app app db stamp ea0a3061c61f
flask --app app db upgrade
```

Do **not** stamp `head` on a legacy schema; that would skip the structured-address migration. If the database already has an Alembic revision, use `flask --app app db upgrade`. Never stamp a database before verifying its schema and taking a backup.

## Photo storage and deployment

Uploaded files are private until their photo and location are approved, and are served through an authorization-checked route. `UPLOAD_FOLDER` must point to private, writable storage. Container filesystems can be ephemeral: configure a persistent mounted volume or object storage before relying on uploaded photos in production. The current Render Blueprint defines the web service and PostgreSQL database but does not provision a persistent media volume; without one, photos can be lost on redeploy/restart. No deployment has been run as part of this repository change.

For HTTPS deployments, set `SESSION_COOKIE_SECURE=true`. Set `SECRET_KEY`, `DATABASE_URL`, and (when available) a persistent `UPLOAD_FOLDER` through the hosting provider's environment configuration. The application sets response security headers and limits request size to 5 MB.

## Moderation and admin setup

Create an account through the site, then promote a trusted account from a shell connected to the same database:

```bash
python scripts/promote_admin.py admin@example.com
```

Staff see the moderation dashboard after signing in. The API routes are `GET /api/locations/pending`, `POST /api/locations/<id>/review`, `GET /api/locations/photos/pending`, and `POST /api/locations/photos/<id>/review`; these require an admin/moderator session and valid CSRF protection. Regular users cannot access review queues. Public list/search endpoints return only approved public locations and approved photos.

## Tests and CI

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q --cov=backend --cov-report=term-missing
```

GitHub Actions runs Flake8's syntax/undefined-name checks and pytest with coverage across Python 3.10, 3.11, and 3.12. Coverage XML is retained as a workflow artifact and uploaded to Codecov when the repository's `CODECOV_TOKEN` secret is configured. The suite includes API authorization/search/upload/moderation checks and verifies that the structured-address migration preserves legacy rows.
