---
name: "Security Guardrails — PlateTag Mobile & API"
description: "Use when writing or editing TypeScript/React Native code in platetag-app, or PHP/Laravel code in platetag-api. Covers API security, auth flows, data handling, rate limiting, and safe deployment practices for the PlateTag project."
applyTo: "src/**/*.ts, src/**/*.tsx, app/**/*.php, routes/**/*.php, config/**/*.php"
---

# Security Guardrails — PlateTag Project

## Project Scope

These guardrails apply to the **active PlateTag project only**:
- `platetag-app` — React Native / Expo (TypeScript)
- `platetag-api` — Laravel 11 / PHP 8.2

`plates_react` is retired and off-limits. Do not reference or port patterns from it.

---

## API Security (platetag-api — Laravel)

### Authorization
- All authenticated routes must use `auth:sanctum` middleware — never bypass it.
- Filament admin panel routes are protected by Filament's built-in auth. Do not add parallel admin endpoints outside this system.
- Ownership checks are required before any mutation. A user may only modify their own collection entries, sessions, bug reports, and plate requests.
- `is_active = false` plates must never be discoverable or returned by any public API endpoint. Soft-delete via `is_active` flag only — never hard-delete plates from the database.

### Rate Limiting
- Three tiers are defined in `RouteServiceProvider` (or `AppServiceProvider`): `auth` (10/min), `submissions` (5/min), `api` (60/min).
- Do not add ad-hoc rate limiting outside these named limiters.
- Do not increase limits without security review.

### Input Validation
- All user input must be validated via Laravel Form Requests or `$request->validate()`.
- Notes fields: maximum 500 characters, nullable.
- Location fields: latitude/longitude must be validated as numeric within valid geographic ranges (-90 to 90, -180 to 180).
- Integer IDs must be validated as positive integers before any query.

### Error Handling
- Do not leak stack traces, SQL queries, internal paths, or table names in API responses.
- Return generic error messages to the client. Log details server-side only.
- `APP_DEBUG=false` must be set in production `.env` at all times.

### Database
- Never hard-delete plates. Set `is_active = 0` in Filament.
- Never truncate `user_discovered_plates` without an explicit, documented backup step completed first.
- Never run a sync or migration script against production without a verified backup on hand.
- The script `prod_sync.py` (in the retired `plates_react/tools/` folder) is permanently banned from execution. It wiped the production database on May 9, 2026.

---

## Mobile App Security (platetag-app — React Native)

### Auth Tokens
- Bearer tokens are stored in `AuthContext` in memory and in `SecureStore` (expo-secure-store). Do not store tokens in `AsyncStorage` — it is not encrypted.
- On logout, clear the token from both memory and `SecureStore`.

### API Communication
- All API calls must go through `src/api/client.ts`. Do not make raw `fetch()` calls to the API from screen components.
- The base URL is set via `EXPO_PUBLIC_API_BASE_URL` environment variable. Never hardcode `platetag.app` or `10.0.2.2` in component files.
- Production builds use `https://platetag.app/api/v1`. Development builds use the local WAMP host.

### Local SQLite Storage
- `discovered_plates` table stores local-first discovery records. User ID must always be written when the user is logged in.
- The sync queue (`sync_queue` table) dequeues permanently on HTTP 404 — this prevents zombie retries for deleted or deactivated resources.
- Do not expose raw SQLite data in user-facing error messages.

### Build Artifacts
- `.aab` (Android App Bundle) and `.ipa` (iOS Archive) files must never be committed to any Git repository.
- `.env` files containing API keys or secrets must never be committed.
- Review `app.json` and `eas.json` before each build to confirm no sensitive values are embedded.

---

## Deployment Safety

- Images are deployed to A2 Hosting via FileZilla (SFTP) — not via any automated script.
- Database updates follow the documented sync procedure: generate SQL locally → backup production → truncate → import → verify.
- SSH keys live in `C:\Users\lmaje\.ssh\` only. They must never be placed inside any project folder.
- cPanel credentials must be changed after any accidental exposure (e.g., typed into a terminal window).
