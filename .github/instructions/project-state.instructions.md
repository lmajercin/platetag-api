---
name: "PlateTag API — Project State & Conventions"
description: "Current project state, production server facts, migration conventions, sync script, and key API routes. Read this when starting any backend feature or deployment."
applyTo: "**"
---

# PlateTag API — Project State & Conventions

## Project Identity

- **platetag-api** — Laravel 11 backend API + Filament admin panel
- **platetag-app** — React Native / Expo mobile app (sibling project at `C:\wamp64\www\platetag-app\`)
- `plates_react` is a retired legacy project. **OFF LIMITS.** Do not read from, write to, or reference it.
- `plates_react/tools/prod_sync.py` — **BANNED.** Wiped production database on May 9, 2026.

## Current State (as of 2026-06-16)

- Production DB: plates=10,170 | series=256 | regions=99 | categories=16
- Last synced: 2026-06-13
- Mobile app: v1.2.0 — iOS build 69 / Android build 69 — SUBMITTED 2026-06-16. iOS EAS: `6c07cb77`, Android EAS: `175e8188`. Fixes: cap banner tap zone, stale counter, 30s network timeout. Next build = 70 (both platforms).
- **Build 68 registration fixed (2026-06-16):** Two production fixes deployed:
  1. **Migration:** `discovery_sessions.ended_at` column was missing from production DB. Migration deployed via A2 cPanel Terminal. Without this column, session creation failed during registration.
  2. **`.env` SMTP typo:** Single character typo in production `.env` — letter `i` used instead of lowercase `l` in a Brevo SMTP field (likely `MAIL_FROM_ADDRESS` or `MAIL_HOST`). Silently broke all outbound email (verification + password reset). Fixed by direct `.env` edit on A2 Hosting. No code deploy required.
  - All auth flows verified working post-fix: register → email verify → login → forgot password → reset password.
- **Build 65/66 note:** Superseded by Build 67.
- **Web app: ✅ V1 COMPLETE at https://platetag.app (2026-06-04).** PWA + cookie auth live. DNS cutover done.
- **Web app: ✅ LIVE at https://platetag.app (2026-06-03). ~99% V1 complete. DNS cutover done. `APP_URL` on production `.env` = `https://api.platetag.app`. Delete Discovery, Pin Correction, ToS/Privacy, OG image, Search Console all done. PWA manifest is the only remaining V1 item.**
- Local WAMP DB (`platetag_db1`) is **source of truth** for all content
- **Android auto-submit:** `google-play-service-account.json` in project root. `eas submit --platform all` now automated.
- **Filament 2FA:** ✅ ENABLED on production 2026-05-25 — `jeffgreco13/filament-breezy v2.6.4`, TOTP via Google Authenticator. `breezy_sessions` table migrated on production.
- **Local-only migrations applied (not yet on production):**
  - `add_premium_fields_to_users_table` (2026-05-24) — `is_premium`, `is_founding_member` (repurposed: set true for 14-day launch window accounts), `premium_granted_at` on users
  - `create_purchases_table` (2026-05-24) — IAP receipt storage with encrypted `raw_receipt`
  - `create_promo_codes_table` (2026-05-25) — code, discount_type (enum: free), starts_at, expires_at, max_uses, uses_count, is_active, notes
  - `create_promo_code_redemptions_table` (2026-05-25) — promo_code_id, user_id, redeemed_at; unique on (promo_code_id, user_id)
  - `add_promo_expires_at_to_users_table` (2026-05-25) — nullable timestamp on users
- **A2 Hosting cron job:** live 2026-05-25 — `schedule:run` every minute. `ExpirePromoAccess` fires nightly at 02:00.
- **Password reset abuse hardening:** Deployed on production 2026-05-28.
  - `mobile_otp_resets.attempts` migration applied (`2026_05_28_000004`, batch 14).
  - Reset OTP TTL reduced to 30 minutes.
  - Runtime verification (clean account path) confirmed lockout threshold behavior (`422, 422, 422, 422, 429, 422`).
- **Production `.env` — web session vars added 2026-05-30:**
  - `SESSION_DOMAIN=.platetag.app`, `SESSION_SECURE_COOKIE=true`, `SANCTUM_STATEFUL_DOMAINS=platetag.app,localhost,localhost:3000`
- **Production `.env` additions still pending (add before promo/payment deploy):**
  - `FREE_PLATE_CAP`, `REVENUECAT_SECRET_KEY`, `REVENUECAT_ENTITLEMENT_ID`, `LAUNCH_DATE` (set on launch day for 14-day free window)

---

## Library Selection Rule (enacted after Build 30 — 2026-05-23)

**Always prefer an already-installed Expo or React Native library before building anything custom. Check `package.json` first.**

This rule exists because `@react-native-google-signin/google-signin` was debugged for 36 hours across 10 builds when `expo-auth-session` (which handles Google and Facebook OAuth without SHA-1 registration) was already installed the entire time.

---

## Production Server

- **Host:** A2 Hosting (shared) — domain: `platetag.app`
- **SSH alias:** `platetag-prod` (ED25519 key, `BatchMode=yes`)
- **cPanel account:** `platetag`
- **Web root:** `~/public_html/` (alias: `~/www` symlink)
- **Laravel app root:** `~/platetag-api/`
- **SCP public web files:** `platetag-prod:~/public_html/filename`
- **SCP Laravel app files:** `platetag-prod:~/platetag-api/path/to/file`
- `public_html/index.php` bootstraps Laravel from `~/platetag-api/` — **do NOT deploy over it**
- `APP_DEBUG=false` must be set in production `.env` at all times

## Production API Smoke Tests
```
GET https://platetag.app/api/v1/plates?per_page=1       → HTTP 200 JSON
GET https://platetag.app/api/v1/regions?country_code=US → HTTP 200 JSON
```
Note: `/api/v1/health` returns 404 by design — no health route exists.

---

## Content Sync Script

- **Path:** `C:\wamp64\tools\sync_to_prod.ps1`
- **Purpose:** One-way local→production content sync (plates, series, regions, categories + new images)
- **Tables synced:** `plates`, `series`, `regions`, `categories`
- **Tables NEVER touched by sync:** `users`, `user_discovered_plates`, `discovery_sessions`, `sessions`, `personal_access_tokens`, `mobile_email_changes`
- **Run:** `& C:\wamp64\tools\sync_to_prod.ps1`
- Status: Verified working 2026-05-12

### Mandatory Pre-Sync Rule (enacted 2026-05-13)

Before any agent makes a direct change to the **production database** (rows, schema, or migrations), the DB sync script **must be run successfully first**.

- If the sync fails, the agent stops. No production DB change proceeds until the sync is clean.
- This rule does **not** apply to code-only deploys (SCP of PHP/controller files) — the sync script never touches code files.
- This rule does **not** apply to EAS builds — EAS never connects to the database.
- Purpose: guarantees local and production content tables are identical at the moment of any agent-driven change, preventing silent overwrites in either direction.

### Tool Dependency Documentation Rule (enacted 2026-06-09)

**Any tool, script, or automation that requires non-default software dependencies must explicitly document those dependencies in THREE places:**

1. **PROJECT_BIBLE.md** — Add to the relevant Tech Stack section (Section 19) with version number and purpose
2. **The relevant instruction file** — Add prerequisite section with download links and installation steps
3. **The tool's file header** — Use `#Requires -Version X.Y` (for PowerShell) or equivalent version check comment

**Applies to:** Any `.ps1`, `.php`, `.js`, or other script that won't run on the default Windows/server environment.

**Why this rule exists (2026-06-09):** PowerShell 7.4.1 was required to execute `sync_to_prod.ps1` due to ampersand parsing limitations in PS 5.1, but this requirement was never documented in PROJECT_BIBLE.md or LARRYS_SETUP_AND_DB_SYNC.md until after the script had been deployed and modified. This rule prevents that gap from recurring.

---

## Rate Limiting

Three tiers defined (AppServiceProvider or RouteServiceProvider):
- `auth` — 10 requests/min
- `submissions` — 5 requests/min
- `api` — 60 requests/min

Do not add ad-hoc rate limiting outside these named limiters. Do not increase limits without security review.

---

## Filament Admin Panel — Content Editing Rule (HARD — enacted 2026-06-05)

**Plate, series, region, and category edits must NEVER be made on production Filament.** The local WAMP Filament is the sole editing environment for content.

- **Production Filament** uses a **light/daytime color scheme** — intentional visual cue, do not change it.
- **Local (WAMP) Filament** uses a **dark color scheme** — intentional visual cue, do not change it.
- Production Filament is for: promo code management, user admin, and viewing content. Not editing content.
- Violating this rule creates silent production drift — the next sync will overwrite accidental production edits with local data, potentially corrupting both.
- **If content must be edited on production (emergency only):** document it in `APP_STATUS.md` immediately with what was changed and why. Then sync local ← production before doing anything else.

---

## Database Rules

- **Never hard-delete plates.** Use `is_active = 0` via Filament.
- `is_active = false` plates must never be returned by any public API endpoint.
- Never truncate `user_discovered_plates` without an explicit, documented backup completed first.
- Never run a migration or sync script against production without a verified backup on hand.
- Ownership check required before any mutation: users may only modify their own collection entries, sessions, bug reports, plate requests.

### Pre-Sync Verification (HARD — enacted 2026-06-05)

Before running `sync_to_prod.ps1`, the agent must run a count comparison of all 4 content tables (plates, series, regions, categories) between local and production. If counts differ, the agent must:

1. **Report the differences immediately.** "Production has 10,118 plates. Local has 10,120 plates. 2 plates differ."
2. **Investigate the cause.** Check if production Filament was edited directly, if plates were added/removed locally without sync awareness, or if a sync failed mid-run.
3. **Do NOT proceed with sync** until the discrepancy is understood and Larry approves.
4. **If counts match,** proceed with sync normally.

**Why this exists:** A May 2026 scenario walkthrough revealed that Larry could accidentally edit production Filament, forget, then sync local over it — silently corrupting data. The count diff catches this before any data moves.

---

## Migration Conventions

- Standard migration command (local WAMP):
  ```powershell
  cd C:\wamp64\www\platetag-api
  php artisan migrate
  ```
- On A2 production: use cPanel Terminal → `cd ~/platetag-api && php artisan migrate`
- Never run `migrate:fresh` or `migrate:reset` on production — destructive
- Always backup production DB before running migrations on production

---

## Data Restore Discipline (lesson from 2026-05-10 incident)

When a restore method fails:
1. Identify WHY — don't just move on
2. Try the next extraction/import method for the **same source**
3. Only fall back to a different data source when primary is **confirmed unrecoverable**

**Backuply tar.gz on Windows:** 7-Zip → Extract Here (twice) → `databases/` folder → `platetag_db1.sql` → import via phpMyAdmin

**`C:\Users\lmaje\backups\platetag\` = LAST RESORT.** Local dev state — missing series, user data, discoveries.

---

## Key Routes & Endpoints

- `GET /api/v1/plates` — paginated plate list (public)
- `GET /api/v1/regions` — region list (public)
- `POST /api/v1/auth/purchase/verify` — server-to-server IAP receipt validation via RevenueCat. Behind `auth:sanctum` + `throttle:auth`. Grants `is_premium` on success.
- Auth routes: `auth:sanctum` middleware — never bypass
- Filament admin panel: built-in Filament auth — do not add parallel admin endpoints outside Filament

---

## Preview-APK-First Rule (HARD — enacted 2026-05-23, re-hardened 2026-06-08)\n\n**No production build may be submitted to either store until a `preview` build has been installed on both physical devices and all changed features have been manually verified.**\n\nPreview → verify on Pixel 6 Pro + iPhone 15 Plus → fix any failures → re-audit → production build.\n\nBuild 66 shipped an iOS-specific cap UI bug caught only after submission. A preview pass would have caught it first. This rule existed since Build 40 and was not enforced. It is now a hard gate.\n\n**Exemptions:** Pure asset-only changes with no code changes, or a critical crash hotfix where Larry explicitly approves skipping preview in writing.\n\n---\n\n## Build Review Gate (applies to API changes too)

API changes that add new public endpoints or touch auth/user data require **Audit** agent review before implementation. See `platetag-app/.github/instructions/project-state.instructions.md` for full gate rules.
