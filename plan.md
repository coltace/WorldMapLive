# WorldMapLive / AceMap Changer implementation plan

## Scope and assumptions

Use the canonical GitHub `main` branch at commit `51ec47f76c1a912ebe08b30b0dc968aff7e6ebd6` as the starting point. The previous sandbox's uncommitted changes are not present in this session; reapply the previously requested AceMap Changer rebrand and guest-only full-screen authentication flow rather than overwrite or assume those changes exist. Preserve the Flask, SQLAlchemy, Alembic, Flask-Login, CSRF, and Leaflet architecture.

The assistant is a map-discovery and app-help assistant, not an autonomous agent. It can use only approved public map entries and app documentation. It cannot create, edit, delete, approve, or publish locations. Do not send pending submissions, user-only records, private photo paths, or account data to an AI provider. Do not persist chat transcripts by default. Make the model provider configurable server-side; never expose a credential in frontend assets. The provider choice and its production credential remain user-controlled.

Recommendations use approved public locations and deterministic signals such as current map area, category, and distance. Duplicate detection compares normalized place name/address plus coordinate proximity and adds a private review hint for moderators; it does not reject submissions automatically or disclose another user's pending place to the submitter or public.

For initial production photo storage, configure a Render persistent disk mounted at `/var/data` and point uploads at `/var/data/uploads/photos`. This requires paid Render compute and constrains the service to one instance. If the app must scale across instances, use object storage instead. Do not change Render plans or incur charges without separate explicit approval.

Inspect the live PostgreSQL schema before migrating. The current read-only check found no `alembic_version`, `users`, `map_items`, or `photos` columns. Do not stamp or mutate the production database until its schema and backup/restore situation are confirmed. Keep test databases isolated from production.

The earlier TokenOS / wallet / crypto request is not implemented by this plan: the identified TokenOS product is a Web3 app-building platform, and the repository has no wallet or chain integration. Do not add wallet, payment, smart-contract, signing, or transaction behavior unless the user confirms the intended TokenOS API, chain, wallet use case, data, and safety policy. Never sign or submit real transactions.

## Implementation approach

1. Restore the AceMap Changer branded, account-first guest view and post-login workspace using the prior requested UI direction and existing Flask session/auth endpoints.
2. Add a small server-side assistant service and authenticated, rate-limited API route. Enforce bounded input/output, timeouts, safe failure behavior, and strict retrieval limited to approved public map data. Add a clear UI disclosure about the configured AI provider.
3. Add deterministic recommendations and duplicate-candidate detection as separate backend services. The moderator view receives duplicate hints without exposing pending records across users.
4. Set persistent upload-path defaults and directory checks. Update the Render Blueprint for the disk and upload variables, and align its service/database plan and migration command only after the user selects a paid hosting approach. Keep the disk single-instance limitation explicit.
5. Inspect migrations and production schema before any data-changing operation. Make the health check distinguish application liveness from database readiness so Render does not report an unusable database as healthy.
6. Harden configuration, upload boundaries, rate limits, CSP/security headers, query limits, and error handling; add automated dependency auditing and frontend/backend tests. Run pytest, frontend tests, lint, dependency audit, and a local Gunicorn/health smoke test on an isolated test database.
7. Because `main` is protected and Render auto-deploys commits to `main`, prepare changes on a feature branch and use CI/PR review. Do not merge or change live Render plans without explicit approval of the exact production action. After an approved release, verify the public site, database readiness, migration revision, and logs through Render.

## Project structure

- `backend/routes/`: Flask API routes for auth, locations, moderation, and the proposed assistant endpoint.
- `backend/services/`: geocoding plus proposed assistant, recommendation, and duplicate-detection services.
- `backend/models/`: existing user, map-item, and photo database models; add schema fields only through Alembic migrations.
- `static/js/`, `static/css/`, `templates/`: browser API client, map/auth behavior, and AceMap Changer interface.
- `migrations/versions/`: versioned schema migrations; production runs only after schema inspection and approval.
- `tests/`: isolated Flask API/model/migration tests and dependency-free Node frontend behavior tests.
- `render.yaml`, `.env.example`, `.github/workflows/`: deployment configuration, secret names only, and automated checks.

## Design direction

Reuse the previously requested premium AceMap Changer look rather than invent a second brand: a dark, full-screen account-first entry with an editorial community-atlas workspace after sign-in.

- **Design Movement:** Modern cartographic editorial, balancing premium map-tool clarity with community warmth.
- **Core Principles:** Privacy-first discovery; visible, explainable recommendations; quick mobile interactions; moderator decisions remain human-controlled.
- **Color Philosophy:** Deep ink/navy grounds the map workspace, warm paper-like surfaces improve form readability, and one saturated teal/blue accent marks map actions and the primary CTA.
- **Layout Paradigm:** Guests see only the full-viewport sign-in/sign-up surface. Authenticated users enter a map-led workspace with compact discovery tools and a responsive contribution rail.
- **Signature Elements:** A distinctive “A” atlas marker; coordinate-aware map-pin accents; compact provenance/review badges that distinguish approved places from staff-only signals.
- **Interaction Philosophy:** No surprise public data changes; recommendations explain why they appear; duplicates are warnings for humans, not hard blocks.
- **Animation:** Brief, reduced-motion-aware transitions for auth-to-workspace and result updates; no continuous decorative motion.
- **Typography System:** Use the existing system font stack for reliable small-screen rendering, with a high-contrast display scale for headings and compact readable labels.
- **Brand Essence:** A more complete community map for people adding places ordinary maps miss; precise, welcoming, trustworthy.
- **Brand Voice:** Direct and useful. Examples: “Add the place maps missed.” “A nearby match may already be on the atlas.”
- **Wordmark & Logo:** A custom atlas-pin “A” mark paired with the AceMap Changer wordmark.
- **Signature Brand Color:** Teal-blue, reserved for primary map actions and highlights.
