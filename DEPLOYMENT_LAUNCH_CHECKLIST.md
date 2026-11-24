# Deployment & launch checklist

This repository includes a Render blueprint at `render.yaml` that defines a Python web service, a PostgreSQL database, a pre-deploy command (`python scripts/init_db.py`), and `/api/health` as the health-check path. Repository files do not create provider accounts, configure DNS or Cloudflare, or populate provider-side secret values. Verify the actual service, database, and plan settings in the provider dashboard before launch.

## Required before launch

1. **Database and migrations.** Use a paid, non-expiring PostgreSQL plan for production and take a verified backup. Confirm the deployed database's Alembic revision matches the repository migration head. The blueprint declares `python scripts/init_db.py` as its pre-deploy command; verify that the selected Render plan executes this command successfully before relying on it.
2. **Secrets and application mode.** Use a stable, randomly generated `SECRET_KEY`, set `SESSION_COOKIE_SECURE=true` for HTTPS, and keep `FLASK_DEBUG=false`. The current blueprint generates a secret and declares the secure-cookie and debug settings; verify their effective values in the service dashboard. Never commit production secrets.
3. **Durable private photo storage.** The photo route stores files under `UPLOAD_FOLDER`. For persistent Render uploads, mount a disk at `/var/data` and set `UPLOAD_FOLDER=/var/data/uploads`. The current `render.yaml` does **not** declare a persistent disk, so durable photo storage is not provisioned by that blueprint as written. Do not treat the web service's ordinary filesystem as durable storage.
4. **Health and uptime.** After deployment, check `/api/health/live` and `/api/health/ready`; the readiness endpoint verifies the database and migration state. The blueprint currently uses `/api/health` for its provider health check. Configure an external uptime monitor for both liveness and readiness.
5. **Scaling and rate limits.** Flask-Limiter uses an in-memory store by default. For multiple workers or instances, configure `RATELIMIT_STORAGE_URI` to a private shared Redis-compatible store. Do not expose storage credentials.

## External provider configuration

Application code changes cannot create hosting accounts, set DNS, configure Cloudflare, or populate production secret values. Configure those directly with the relevant providers, then verify the effective settings and deployment health.

## API v1 status

The proposed read-only routes `/api/v1/places`, `/api/v1/search`, `/api/v1/nearby`, `/api/v1/countries`, `/api/v1/trending`, and `/api/v1/users/<id>` are **not implemented in the current repository**. Do not advertise or depend on these endpoints until they have been added, tested, and documented. Any public API must avoid exposing private user fields; if API-key protection is introduced, document and test its authentication behavior.

## Socket.IO and real-time updates status

Socket.IO is **not currently installed or configured**. The repository has no Socket.IO endpoint, authenticated public/moderator rooms, client event listeners, or post-commit location/photo event emissions. Installing a Socket.IO package or setting a queue variable alone would not make map updates live. A future implementation needs server-side role checks, event emissions after successful database commits, client listeners, and a WebSocket-capable deployment configuration; verify provider sticky-session requirements before scaling beyond one web instance.

## Optional monitoring and shared services

`SENTRY_DSN` is not currently consumed by the application, so setting it alone does not enable error reporting. The application reads `RATELIMIT_STORAGE_URI`; it does not currently use a `REDIS_URL` alias. `SOCKETIO_MESSAGE_QUEUE` is not consumed because Socket.IO is not implemented. Add and test each integration before documenting it as active.

## Local verification

```sh
python -m pip install -r requirements-dev.txt
python scripts/init_db.py
python -m pytest -q --cov=backend --cov-report=term-missing
```

The test suite uses isolated test databases; it does not validate production credentials, provider-side configuration, persistent volumes, DNS, or a deployed service. Perform the post-deploy checks above against the actual environment before declaring launch readiness.
