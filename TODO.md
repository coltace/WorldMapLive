# WorldMapLive / AceMap Changer TODO

Implementation is approved for code and isolated tests only. Production infrastructure, database writes/migrations, merge, deployment, or paid-plan changes remain unapproved and must not be performed in this phase.

## 1. Restore AceMap Changer account-first experience
- [x] Guests first see only a full-screen sign-in/sign-up experience; they must not see the map or dashboard until authenticated.
- [x] After successful account creation or sign-in, take the user to the next home/dashboard page.
- [x] Reapply the previously requested AceMap Changer brand and mobile-friendly interface without replacing the existing Flask authentication or authorization rules.
- [x] Keep the map workspace after authentication, including the location map, search, contribution, management, and staff moderation controls.

## 2. Preserve custom community-place workflow
- [x] Create entries even when a house, address, or place does not exist on Google Maps or elsewhere online.
- [x] Allow a pin at any valid location using manual latitude/longitude or a map placement.
- [x] Support a custom place name and address details: house number, street, area, city, state, country, postal code, and description.
- [x] Find approved new places globally by custom name and address.
- [x] Upload house/building photos, manage one's own entries (edit/delete), and retain human moderation for submissions and photos.
- [x] Keep approved addresses, coordinates, and photos public only as disclosed in the application; do not reveal other users' pending submissions.

## 3. Add a privacy-bounded AI assistant
- [x] Provide an in-app assistant for map discovery and app help, using a server-side configurable OpenAI-compatible provider; no provider key is embedded in frontend code or committed.
- [x] Ground place-related answers only in approved public locations; pending submissions are excluded in isolated tests.
- [x] The assistant cannot create, edit, delete, approve, or publish locations; chat history is not persisted by the app.
- [x] Enforce authentication, per-user rate limits, bounded input/output, provider timeouts, safe error responses, and textContent-based plain-text rendering.
- [x] When provider configuration is absent or fails, return a safe unavailable response.

## 4. Add recommendations and duplicate warnings
- [x] Recommend approved public locations using bounded distance/category signals and show the recommendation reasons.
- [x] Detect likely duplicates using normalized place-name/address information and geographic proximity.
- [x] Warnings are advisory, not automatic rejection. Users see only approved public candidate matches; staff-only hints may include pending submissions.
- [x] Bound candidate queries and result counts.

## 5. Improve production photo durability and migration readiness
- [x] Store uploaded photos outside the application code/static tree and honor a configurable private upload directory; retain image validation, re-encoding, owner/staff access, and moderation protections.
- [x] Document the Render disk mount path `/var/data` and `UPLOAD_FOLDER=/var/data/uploads`, plus the paid-plan/single-instance constraint. No production resource was changed.
- [x] Use Alembic migrations; test fresh and legacy database migration paths in isolated SQLite databases.
- [x] Make health/readiness disclose core database and migration status.
- [x] Verify production state read-only and record blockers; no production schema or settings were changed.

## 6. Complete security, performance, and regression checks
- [x] Preserve authorization, CSRF, upload validation, privacy boundaries, secure cookies, and security headers; add bounded assistant/discovery checks.
- [x] Bound map/assistant result sizes and retain responsive mobile layout.
- [x] Run the full pytest suite, JavaScript syntax checks, and configured Flake8 CI checks against isolated data; see final report for exact results.
- [x] Verify a locally started application process and readiness behavior using a temporary SQLite database.

## Deferred pending separate scope confirmation
- TokenOS, wallet connectivity, blockchain data, transactions, and smart contracts are outside this approved code/test pass. Do not add wallet signing or transaction behavior without the exact provider/API, chain, use case, data policy, and a separately approved scope.

## Verification notes
- Local `pytest`: 23 passed; migration-backed fixtures and migration-preservation/index assertions use isolated SQLite files.
- Local coverage run: 79% total backend coverage; XML saved to `/tmp/acemap-coverage.xml` (not part of the repository).
- The CI Flake8 policy (`E9,F63,F7,F82`), JavaScript syntax checks, `git diff --check`, and a local HTTP smoke test on a temporary migrated SQLite database passed.
- Assistant provider requests were mocked; no provider key was configured. The frontend was syntax-checked but not exercised in a real browser automation suite.
- Production was inspected read-only only. No production database writes/migrations, paid resource changes, merge, push, or deploy occurred.
