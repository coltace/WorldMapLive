# Move AceMap Changer to Railway Hobby

This guide uses a Railway Hobby project, a fresh Railway PostgreSQL service, and a persistent upload volume capped at 5 GB. Keep the existing Render service and database until Railway is live and verified. Only then remove the two Render resources named in the migration approval.

## Current code and checks

The tested candidate is commit `83eedfb53635ebdc5f055693b6e4bc8fc9d83891` on `work/acemap-ai-recommendations`; PR [#12](https://github.com/coltace/WorldMapLive/pull/12) has passing Python 3.10, 3.11, and 3.12 checks and Codecov patch coverage. This repository includes a Railway Dockerfile. The Flask backend already supports PostgreSQL through `DATABASE_URL`, photo storage through `UPLOAD_FOLDER`, and Alembic migrations through `python scripts/init_db.py`.

## Easiest setup in a phone browser

1. Sign into Railway at <https://railway.com/new> with GitHub and choose the Hobby plan. Create a project from the `coltace/WorldMapLive` repository. Initially deploy branch `work/acemap-ai-recommendations` so you can verify the new code without changing the Render service.
2. Add a PostgreSQL service to the Railway project. In the app service's Variables, set `DATABASE_URL` to the Railway Postgres service's internal connection string (Railway documents it as `DATABASE_URL`). Set `SECRET_KEY` to a newly generated private random value and set `SESSION_COOKIE_SECURE=true`. Never commit these values or send them in chat.
3. Attach a Railway volume to the Flask app service at `/var/data`. Set `UPLOAD_FOLDER=/var/data/uploads`. Railway Hobby volume size is limited to 5 GB. Do not store uploads in the container's ordinary filesystem.
4. In the app service's Deploy settings, set the Pre-Deploy Command to `python scripts/init_db.py`. This creates or upgrades the Railway database before the web process starts. Set the health-check path to `/api/health/ready`; retain the Dockerfile's Gunicorn start command.
5. Generate a Railway public domain for the app. Wait for the deployment to finish, then open `/api/health/ready` and confirm `"status":"ready"` and `"migration":"current"`. Create a test user, submit a test place, upload a test photo, and confirm that the place and image remain accessible after a redeploy/restart. Do not use real personal data for the test.
6. If Railway verification passes, merge PR #12 if not already merged, point Railway at `main`, and verify again. Only after this succeeds should the Render `worldmaplive` web service (`srv-dbps7tbrjlhs73aubodg`) and `worldmaplive-db` (`dpg-dbps1415efls738se340-a`) be deleted. That database deletion is irreversible; export any data you wish to preserve first. A prior read-only query found no public-schema tables, but that is not a substitute for your own data-retention decision.

Railway Hobby is usage-based with a $5/month minimum that includes $5 of usage credits. Actual charges can exceed that based on compute, database, storage, and egress. The Hobby plan allows up to 5 GB volume storage. Check Railway's current dashboard billing estimate and configure a usage limit before deployment if you want to cap spending; a strict cap may suspend the app when reached. This plan does not include a custom domain.

## Optional Termux route

A phone browser is simpler for creating the Railway project and connecting GitHub. Termux can check the PR and use Railway CLI after the Railway project has been created and linked:

```sh
pkg update -y
pkg install -y git nodejs-lts gh
npm install -g @railway/cli

gh auth login --hostname github.com --git-protocol https --web
railway login
```

Complete each provider's browser/device authorization. Do not paste credentials into Termux commands or chat. After you created the Railway project in the Railway dashboard and selected the GitHub repo, open this local repository and run:

```sh
cd ~/WorldMapLive
railway link
railway status
railway logs
```

Use `railway up` only if you intentionally want a CLI-built deployment. GitHub-connected deploys are easier to maintain because pushes to the selected branch deploy automatically. Do not merge PR #12 or delete Render resources until the Railway pre-deploy migration and the app/photo verification above succeed.

## Local Termux testing only

This runs the app on your phone and does not create a public deployment:

```sh
pkg install -y git python
cd ~
git clone -b work/acemap-ai-recommendations https://github.com/coltace/WorldMapLive.git
cd WorldMapLive
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

For local startup, set a development-only `SECRET_KEY` and a local SQLite `DATABASE_URL`, run `python scripts/init_db.py`, then start with `gunicorn --bind 0.0.0.0:5000 wsgi:application`. Do not connect local tests or development runs to either production database.
