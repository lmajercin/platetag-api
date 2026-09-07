---
name: "PlateTag API — Project State & Conventions"
description: "Current project state, production server facts, migration conventions, sync script, and key API routes. Read this when starting any backend feature or deployment."
applyTo: "app/**/*.php, routes/**/*.php, database/**/*.php, config/**/*.php"
---

# PlateTag API — Project State & Conventions

## Project Identity

- **platetag-api** — Laravel 12 backend API + Filament admin panel
- **platetag-app** — React Native / Expo mobile app (sibling project at `C:\wamp64\www\platetag-app\`)
- `plates_react` is a retired legacy project. **OFF LIMITS.** Do not read from, write to, or reference it.
- `plates_react/tools/prod_sync.py` — **BANNED.** Wiped production database on May 9, 2026.

## Current State (as of 2026-09-06)

- Production DB: plates=10,349 | series=260 | regions=99 | categories=17
- Last content sync: 2026-09-06 19:26 EDT — all 4 tables MATCH (+1 plate ID 10866 RI - Antique - v1; +1 plate image)
- **Vision tagging backfill:** ✅ **CONCLUDED 2026-07-22**
- Mobile app: **Build 85 LIVE** — iOS/Android v1.4.0 (85). Live iOS 2026-09-05, Android 2026-09-04. **Build 86 PLANNED** — submit ~2026-10-05 (ALPCA badges, contact form fix, Road Trip UI revamp, B-24 explore icon, B-26 login route fix). @Design session ~2026-09-22.
- **Filament Analytics:** ✅ **LIVE on production** 2026-08-21 — Discovery Insights, Discovery Map, Usage Reports; `geo_usage_snapshots` migrated + 147-day backfill; schedule `analytics:snapshot-geo` 02:15.
- **Backuply:** ✅ Automated Google Drive backups restored 2026-07-14.
- **Web app:** ✅ V1 LIVE at https://platetag.app. Full session (W-1+W-2+W-3) of web updates deployed 2026-09-07: Road Trips rename, OSM tiles, Summer theme (default), full-page map, global counter, share buttons on Road Trips + Collection, web claim flow on both share pages. See `platetag-web/docs/WEB_STATUS.md` for full detail.
- **Share controllers hotfix (2026-09-07):** `PlateShareController` + `SessionShareController` — null default-session guard added inside `claim()` DB transaction (B-2 from @Audit review). `PlateShareController` also got sort-before-compare fix for plate_ids token-reuse check (R-1). Deployed via SCP directly.
- Local WAMP DB (`platetag_db1`) is **source of truth** for plate content.
- **A2 Hosting cron:** live — `schedule:run` every minute; `ExpirePromoAccess` 02:00; `analytics:snapshot-geo` 02:15.
- **Filament 2FA:** ✅ ENABLED — `jeffgreco13/filament-breezy v2.6.4`.

---

## Admin Backlog (low priority — future builds)

| ID | Area | Description | Notes |
|----|------|-------------|-------|
| A-1 | Discovery Map | CARTO tile API key missing — map shows "API KEY REQUIRED" watermark. Register free account at carto.com, get API key, insert into tile URL in `discovery-map.blade.php` line ~87 (`cartocdn.com/dark_all/...`). **Not a purchase** — CARTO free tier covers this usage level. | ✅ Resolved 2026-09-07. Switched to OpenStreetMap tiles (`tile.openstreetmap.org`). CARTO CDN watermarked on both `dark_all` and `light_all` — no free tier available. OSM is 100% free, no account or key required. |
| A-2 | Discovery Map | Switch basemap from `dark_all` to `light_all` (or `voyager`) for a lighter-colored theme. One-line change same file, same line as A-1. Do A-1 and A-2 together. | ✅ Resolved 2026-09-07. `light_all` deployed. Shell background also lightened to `#f8fafc` to match. |
| A-3 | Usage Analytics | New report: users who registered **after 2026-08-15** (end of grand opening premium grants) — columns: user, registration date, unique plates in collection, premium/free status. Surfaces post-launch organic user behavior. Add as a new table/tab in `UsageAnalytics.php` or a separate Filament page. | ✅ Resolved 2026-09-07. "Post-Launch Users" section added at top of Usage Reports page. Shows all users registered after 2026-08-15 with email, name, date, unique plate count, and Premium/Free plan. |

---

## Filament Analytics upgrade — LIVE on production 2026-08-21

> **Status:** ✅ Deployed to `https://api.platetag.app/admin`. Uses live `user_discovered_plates`.

### What is live

| Item | Detail |
|---|---|
| Nav group | **Analytics** |
| Discovery Insights | `/admin/discovery-insights` |
| Discovery Map | `/admin/discovery-map` |
| Usage Reports | `/admin/usage-analytics` (renamed nav label) |
| Table | `geo_usage_snapshots` — migrated + **147** daily rows backfilled |
| Command | `php artisan analytics:snapshot-geo` (`--backfill`) |
| Schedule | `analytics:snapshot-geo` daily 02:15 |

### Deploy notes (2026-08-21)

- Pre-sync verification: plates/series/regions/categories **MATCH** (no truncate needed).
- SCP of analytics PHP/blade + migration + `bootstrap/app.php` via `platetag-prod`.
- `php artisan migrate --force --path=...geo_usage_snapshots...` → DONE.
- `php artisan analytics:snapshot-geo --backfill` → 147 snapshots.
- Caches cleared (view/cache/route/config).

**Note:** Geo “allow/deny” is inferred from discoveries with coords — OS permission is not stored.


## Vision LLM Plate Tagger (local admin tool — enacted 2026-06-23)

- **Command (review queue):** `php artisan tagger:run` — local WAMP only. Never runs on production.
- **Command (bulk auto-approve by series):** `php artisan tagger:bulk-series {series_id}` — writes `ai_detail`, `detail`, `ai_tags`, `tags`, sets `ai_reviewed=1`. Options: `--limit=N`, `--dry-run`, `--plate=ID`. Local WAMP only.
- **Purpose:** Batch-generates AI descriptions (`ai_detail`) and tags (`ai_tags`) for plates with empty `detail` + `tags`. Uses GPT-4o Vision API.
- **Files:** `app/Console/Commands/TagPlatesWithVision.php`, `app/Console/Commands/TagPlatesWithVisionBulk.php`, `tools/run_tagger_bulk_series_721.bat`, `tools/run_tagger_bulk_series_848.bat`, desktop shortcut `C:\Users\lmaje\Desktop\Run-PlateTagger.bat`
- **Bulk SQL (series 721):** `database/sql/maryland_vision_bulk_series_721_PREVIEW.sql` (before), `maryland_vision_bulk_series_721_VERIFY.sql` (after).
- **Bulk SQL (series 848):** `database/sql/virginia_vision_bulk_series_848_PREVIEW.sql` (before), `virginia_vision_bulk_series_848_VERIFY.sql` (after).
- **API key:** `OPENAI_API_KEY` in local `.env` only. Never commit, never put on production.
- **Eligibility:** Only plates where BOTH `detail` and `tags` are null/empty. Lowest `id` first. Skips plates with an unapproved AI draft (`ai_detail` set, `ai_reviewed=false`). Plates cleared back into the queue (`detail`/`tags` empty, `ai_reviewed=true`) are eligible again. Writes to `ai_detail` + `ai_tags` staging columns only — never touches `detail`, `tags`, `header_override`, `footer_override`.
- **Bulk tagger eligibility:** Only plates where ALL of `detail`, `ai_detail`, `tags`, `ai_tags` are empty AND `ai_reviewed=0`. Any existing content or approved plate is skipped — no overwrite option.
- **Review workflow:** Filament → Plates → Filter: AI Review → Needs review. Edit draft, click Approve → copies to live `detail`/`tags`. Approve button blocked on production (Content Editing Gate + production environment check). Bulk tagger bypasses manual approve for trusted batch runs.
- **Failure log:** `storage/logs/tagger-failures.log` (review queue), `storage/logs/tagger-bulk-failures.log` (bulk)
- **Status:** ✅ **CONCLUDED 2026-07-22** — one-time backfill complete; synced to production. Commands retained for edge-case re-runs on new empty plates only. New plate workflow: enter `detail`/`tags` at upload.

## Header/Footer Vision Tagger (local admin tool — enacted 2026-07-22)

- **Command:** `php artisan tagger:header-footer-series {series_id}` — writes `header_override`, `footer_override`, sets `updates_complete=1`. Options: `--limit=N`, `--dry-run`, `--plate=ID`. Local WAMP only.
- **Purpose:** Reads header (top-center) and footer (bottom-center, including crowded text below serial) from plate images via GPT-4o Vision. **Never copies plate catalog `name` into overrides** — footer is image text (e.g. title `GA - Cobb County Humane Society` vs footer `Spay * Neuter * Adopt`).
- **Eligibility:** Both `header_override` and `footer_override` NULL/empty AND `updates_complete=0` AND has image. Partial-NULL rows excluded. Failures leave `updates_complete=0` for redo.
- **NULL semantics:** NULL header or footer = reviewed, no text in that zone. `updates_complete=1` marks review done even when NULL.
- **Multi-line:** Join lines within one field with `|` (pipe), top-to-bottom (e.g. `Pearl Harbor Survivor|New Mexico USA`).
- **Prompt hints:** Region name + plate catalog name as geography context only — not copied into overrides. Pitfalls: SC state name often in footer; ignore middle-left/right/center serial zones; crowded plates include designation text below serial in footer.
- **Wrapper:** `tools/run_tagger_header_footer_series.bat` — prompts for series ID, dry-run, YES confirm, optional limit.
- **Test SQL:** `database/sql/header_footer_vision_test_plates_PREVIEW.sql`, `header_footer_vision_test_plates_VERIFY.sql`
- **Failure log:** `storage/logs/tagger-header-footer-failures.log`
- **File:** `app/Console/Commands/TagPlatesWithVisionHeaderFooter.php`
- **Vision detail level:** `high` (small header/footer text).
- **Status:** ✅ **CONCLUDED 2026-07-22** — all eligible plates processed locally; production synced same day. Commands retained for edge-case re-runs. New plate workflow: enter `header_override`/`footer_override` at upload; set `updates_complete=1`.

### Vision backfill timeline (2026-07-22)

| Phase | Result |
|---|---|
| Header/footer tool built + tested | 5 test plates PASS; series 783 first batch (9/9) |
| Remaining series (lowest → highest ID) | Larry completed all batches locally |
| Final production sync | 2026-07-22 14:46 MDT — plates=10269 MATCH; images current |
| **Project status** | **CLOSED** — no further bulk Vision runs planned |

**CLI (retained for edge cases only):**
```powershell
cd C:\wamp64\www\platetag-api
C:\wamp64\bin\php\php8.3.14\php.exe -d memory_limit=512M artisan tagger:header-footer-series {series_id} --dry-run
C:\wamp64\bin\php\php8.3.14\php.exe -d memory_limit=512M artisan tagger:header-footer-series {series_id}
```
Or double-click `tools/run_tagger_header_footer_series.bat`.

**Going forward:** New plate imports enter header, footer, detail, and tags at upload. Sync to production via `sync_to_prod.ps1` when new content is ready.

## Filament Discoveries Admin (deployed 2026-07-02)

- **Discoveries resource:** `UserDiscoveredPlateResource` — view-only list + detail for `user_discovered_plates`. Shows user email, plate name, session, geo fields, notes. No create/edit/delete on local or production.
- **Usage Analytics page:** `UsageAnalytics` — reports from existing DB only (most discovered plates, discoveries per user, plates per session, discoveries over time 30/90 days). No mobile app instrumentation required.
- **Models:** `UserDiscoveredPlate`, `DiscoverySession` (Eloquent relationships for Filament display).
- **Key files:** `app/Filament/Resources/UserDiscoveredPlateResource.php`, `app/Filament/Pages/UsageAnalytics.php`, `resources/views/filament/pages/usage-analytics.blade.php`.
- **Deployed:** SCP to production 2026-07-02. Routes: `/admin/user-discovered-plates`, `/admin/usage-analytics`. Larry verified PASS same day.
- **Deferred post-launch:** `app_opens` / `time_in_app` tracking would require mobile app changes + App Store privacy label updates. Not in scope until after store approval.

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
