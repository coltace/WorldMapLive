# AceMap Changer

AceMap Changer is a Flask and Leaflet community map. Guests see a full-screen sign-in/create-account entry first; after authentication, people can add a custom place even when no commercial map or online directory knows about it, set its position by clicking the map or entering latitude/longitude, and submit it for moderation. Approved locations can be found by custom name and address. Accounts use Flask-Login sessions; writes use CSRF protection.

## Capabilities

- Create custom-named places with description, category, house number, street, area/neighborhood, city, state/region, country, and postal code. A geocoder is optional: a place can be created from manual coordinates even when no lookup result exists.
- Search mapped addresses and named buildings through an explicit query, review up to six candidate matches, select one, and refine its draggable map pin. Search is initiated by the user; the interface does not request results as they type. The result list depends on OpenStreetMap data coverage and does not guarantee an exact entrance or building footprint.
- Search approved places by custom name, description, or address fields. Search results are paginated (100 per page).
- View, edit, delete, and upload photographs for your own submissions. Owner edits return a place to pending review. Supported images are JPEG, PNG, and WebP, at most 4 MB and 20 megapixels; images are decoded and re-encoded before storage.
- Admins and moderators can review/approve/reject locations and photos from the in-page moderation panel.
- Nearby recommendations rank approved public places by distance and optional category; duplicate checks are advisory. Regular users see only approved public matches, while staff can request pending-record hints.
- An authenticated map assistant can explain app workflows and answer place questions using only a small, approved-public context set. It cannot change records; chat is not saved by the app.
- `/api/health/live` reports process liveness. `/api/health/ready` (also `/api/health`) returns ready only when core tables exist and the database Alembic revision matches the migration head.

**Privacy:** approved submissions are public, including their coordinates and any address fields provided. Do not submit a private residence or personal information unless you are authorized and intend it to be public.

## Global address lookup

Address search defaults to the public OpenStreetMap Nominatim service. The browser sends a query only after the user presses **Find address**. Nominatim's public-service policy forbids client-side autocomplete and limits the whole application to at most one request per second; it also requires an identifying User-Agent and visible attribution. The app identifies itself, displays attribution, serializes outbound lookups and caches successful query responses in process memory for up to six hours. Reverse geocoding returns the nearest suitable mapped object, not a guaranteed address for the exact coordinate. [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) [Search API](https://nominatim.org/release-docs/latest/api/Search/) [Reverse API](https://nominatim.org/release-docs/latest/api/Reverse/)

Configure `NOMINATIM_BASE_URL` to point to a compatible Nominatim instance without changing the code. `NOMINATIM_MIN_REQUEST_INTERVAL` defaults to `1.1` seconds. The throttle and cache are per process, not shared across multiple application workers or instances. Do not lower the interval when using the public OpenStreetMap service. If the app needs higher or multi-instance traffic, use a provider whose terms support that volume or operate a compatible service with shared rate limiting and caching. Search queries leave this application and are sent to the configured geocoder; avoid sending confidential information. Manual address entry and map placement remain available when no search match exists.

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

`python scripts/init_db.py` applies committed Alembic migrations. The latest migrations add structured address fields and geographic discovery indexes without deleting or rewriting the legacy free-form `address` column. Existing rows are retained and remain searchable by their old address text. Tests use isolated SQLite databases and apply migrations; they do not connect to production.

For an existing database whose tables were created with `db.create_all()` and have no Alembic revision, back it up first and verify its tables match the initial schema. Then mark only the initial migration as applied and run the newer migrations:

```bash
flask --app app db stamp ea0a3061c61f
flask --app app db upgrade
```

Do **not** stamp `head` on a legacy schema; that would skip the structured-address migration. If the database already has an Alembic revision, use `flask --app app db upgrade`. Never stamp a database before verifying its schema and taking a backup.

## Photo storage and deployment

Uploaded files are private until their photo and location are approved, and are served through an authorization-checked route. `UPLOAD_FOLDER` must point to private, writable storage. **For durable photos on Render, a paid persistent disk must be mounted at `/var/data` and `UPLOAD_FOLDER=/var/data/uploads` set; files are saved under its `photos/` child.** Render Free web services do not support persistent disks, so their local filesystems are ephemeral and uploaded photos can be lost on restart, spin-down, or redeploy. A disk is attached to one instance and carries paid-plan and scaling/downtime implications. No disk or plan change is included here.

Read-only Render checks on 2026-11-20 found the active `worldmaplive` service and `worldmaplive-db` on Free resources, no persistent disk, and a Free PostgreSQL expiry date of 2026-12-11. The inspected live database did not contain an `alembic_version` table. These facts are deployment blockers to resolve deliberately: the new readiness handler will report the database unavailable until migrations are applied. This repository change does not upgrade resources, alter production data, run a production migration, merge, or deploy.

For HTTPS deployments, set `SESSION_COOKIE_SECURE=true`. Set `SECRET_KEY`, `DATABASE_URL`, and (when available) a persistent `UPLOAD_FOLDER` through the hosting provider's environment configuration. The application sets response security headers and limits request size to 5 MB.

The default Flask-Limiter store is in-memory and suitable for local/single-process use. For multiple workers or instances, configure `RATELIMIT_STORAGE_URI` to a private shared Redis-compatible store; do not expose its credentials publicly. No Redis resource is provisioned by this repository change.

The assistant is off by default. To enable it, set `ASSISTANT_ENABLED=true`, `ASSISTANT_BASE_URL` to a trusted OpenAI-compatible HTTPS API root (for example `https://api.openai.com/v1`), `ASSISTANT_MODEL` to a model supported by that provider, and `ASSISTANT_API_KEY` as a server-side secret. Never put the key in the browser, source control, or logs. If the settings are absent or the provider fails, the endpoint returns a safe unavailable response. The test suite mocks provider calls; no production/provider credential is needed for tests.

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
