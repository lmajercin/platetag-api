# PlateTag Security Audit — May 10, 2026

**Scope:** `platetag-api` (Laravel 11 / PHP 8.2) · `platetag-app` (React Native / Expo SDK 54)  
**Pass 1 performed by:** GitHub Copilot — @Audit agent  
**Pass 1 date:** 2026-05-10  
**Re-audit (Pass 2) date:** 2026-05-10 (same session, post-fix)  
**Status:** All HIGH and MEDIUM findings remediated. LOW items documented with disposition.

---

## Supplemental Review — Mobile App Security (User-Requested)

These five areas were specifically requested for review in addition to the standard audit checklist.

| Topic | Finding |
|---|---|
| **API Keys** | One key embedded in JS bundle: Geoapify (`EXPO_PUBLIC_GEOAPIFY_KEY`). All other keys (`google-play-service-account.json`) are gitignored. See L-3. |
| **Log info leakage** | Zero `console.*` calls in `src/`. `AsyncStorage` used for non-sensitive UX state only (session ID, theme pref, seen-reply IDs). Auth tokens go to `expo-secure-store` only. PASS. |
| **Debug builds** | EAS `development` profile correctly scoped to `developmentClient: true` / `distribution: internal`. Production profile uses `.aab`. No debug config leaks. PASS. |
| **Code obfuscation** | React Native 0.81.5 with Hermes compiles JS to bytecode. Not true obfuscation, but adequate for a public hobbyist app. ProGuard/R8 applied to Android Java layer by EAS in production. No action required. |
| **ATS (iOS App Transport Security)** | Not disabled. Only `infoPlist` entry is `ITSAppUsesNonExemptEncryption: false` (export compliance, unrelated to ATS). No `NSAllowsArbitraryLoads`. API base URL is `https://`. PASS. |

---

## @Audit Oversight — Stray Binary Files

The initial @Audit pass reported: *"no hardcoded credentials in frontend"* and did not flag any build artifacts.

**This was incomplete.** Three files were present in the `platetag-app` project root that @Audit did not examine or report:

| File | Risk |
|---|---|
| `bugreport-sdk_gphone16k_x86_64-CP21.260306.017.A1-2026-04-05-09-27-05.zip` | Android device bug report. Likely contains system logs, app state, and potentially sensitive user data from a connected device. Must never enter source control. |
| `platetag-ownership-verify.apk` | Debug APK build. Compiled app binary containing all source code, API endpoint URLs, and `EXPO_PUBLIC_` env values. Should not live in the project directory. |
| `platetag-v1.1.0.aab` | Release bundle (AAB). The production-quality binary. If committed to git history, it is retrievable indefinitely regardless of later `.gitignore` rules. |

**None of these file types were in `.gitignore` at the time of the audit.** One `git add .` would have committed all three permanently into git history.

**Remediation applied (this session):**
- `*.apk`, `*.aab`, `*.zip` added to `.gitignore`
- All three files moved to `platetag-app/build-artifacts/` (also covered by gitignore)
- `build-artifacts/` directory should not be committed

**This is a process gap, not just a file gap.** Build artifacts must never be stored in the source tree. The correct location for build outputs is `C:\Users\lmaje\backups\platetag\` or a dedicated external folder.

---

## CRITICAL

None identified.

---

## HIGH — Both Remediated

### H-1 — Wildcard Proxy Trust Nullified All IP-Based Rate Limiting
**File:** `bootstrap/app.php`  
**Status:** ✅ FIXED

**Before:**
```php
$middleware->trustProxies(at: '*');
```

**After:**
```php
$middleware->trustProxies(
    at: ['127.0.0.1', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'],
    headers: Request::HEADER_X_FORWARDED_FOR | ...
);
```

**Impact:** All three rate-limit tiers (`throttle:auth` 10/min, `throttle:submissions` 5/min, `throttle:api` 60/min) are now resistant to IP spoofing via `X-Forwarded-For`. Only requests proxied from private-network addresses can influence the IP Laravel derives.

**Production note:** If A2 Hosting LiteSpeed uses a specific public proxy IP (check A2's documentation or inspect `$_SERVER['REMOTE_ADDR']` on first deploy), add that IP to the trusted list in production `.env` via a config value.

---

### H-2 — OTP Brute-Force Window (Contingent on H-1)
**File:** `app/Http/Controllers/Api/AuthController.php`  
**Status:** ✅ MITIGATED (H-1 fixed; per-email lockout added as defense-in-depth)

With H-1 fixed, the 10/min IP throttle applies correctly. Additionally, M-5 added a per-email lockout as a second independent brake.

OTP validity window remains 60 minutes. If the account population grows significantly, consider reducing to 15 minutes. Not blocking for current user count.

---

## MEDIUM — All Remediated

### M-1 — Shell Arguments Not Fully Escaped in DatabaseTools
**File:** `app/Filament/Pages/DatabaseTools.php`  
**Status:** ✅ FIXED

`$host`, `$port`, `$user`, and `$db` are now wrapped in `escapeshellarg()` in both `backupDatabase()` and `optimizeDatabase()`. Previously only `$password` was escaped.

---

### M-2 — Hardcoded WAMP Path for mysqldump/mysql Binaries
**File:** `app/Filament/Pages/DatabaseTools.php`  
**Status:** ✅ FIXED

Hardcoded `C:\wamp64\bin\mysql\...` paths replaced with `env('MYSQLDUMP_PATH', 'mysqldump')` and `env('MYSQL_PATH', 'mysql')`.

Local `.env` provides the WAMP paths. Production `.env` must set:
```
MYSQLDUMP_PATH=/usr/bin/mysqldump
MYSQL_PATH=/usr/bin/mysql
```

Without this, the Filament DB backup button will silently fail on A2 Hosting.

---

### M-3 — `BCRYPT_ROUNDS=10` Below Recommended Minimum
**File:** `.env`  
**Status:** ✅ FIXED

Changed to `BCRYPT_ROUNDS=12`. Production `.env` must match. This affects only new passwords created after the change; existing hashes are unaffected and remain valid.

---

### M-4 — `LOG_LEVEL=debug` Risks Request Body Leakage in Admin Log Viewer
**File:** `.env`  
**Status:** ✅ FIXED

Changed to `LOG_LEVEL=warning`. Debug-level logs write full request payloads to `storage/logs/laravel.log`, which the Filament DatabaseTools page surfaces to all admin users. Production `.env` must also be `warning` or `error`.

---

### M-5 — No Per-Email Lockout on Failed Login Attempts
**File:** `app/Http/Controllers/Api/AuthController.php`  
**Status:** ✅ FIXED

Added Laravel `RateLimiter` per-email lockout keyed on `login_fail:{email}`. Max 5 failed attempts per 5-minute window, enforced independently of the IP-based `throttle:auth` middleware. Returns `HTTP 429` on lockout with seconds-remaining in the message. Counter clears on successful login.

---

### M-6 — `PlatesController::show()` Did Not Filter Inactive Plates
**File:** `app/Http/Controllers/Api/PlatesController.php`  
**Status:** ✅ FIXED

`GET /api/v1/plates/{id}` now applies `->where('is_active', true)` before `findOrFail()`. Previously, any authenticated user who knew or guessed a plate ID could retrieve soft-disabled or draft plates. Now returns 404 for inactive plates, consistent with the `index` and `discover` endpoints.

---

## LOW / INFO — Dispositions

### L-1 — No `config/cors.php`
**Status:** ACCEPTED — Not applicable. Pure mobile API; browsers don't consume it. CORS provides no protection against non-browser clients regardless of configuration. If a web frontend is added in the future, create `config/cors.php` before that release.

### L-2 — Sanctum Token Expiry 7 Days, No Rotation
**Status:** ACCEPTED — Within acceptable range for a mobile app where re-auth friction is a real UX cost. Logout deletes the token. Password change revokes all tokens. Document: users should logout on shared devices.

### L-3 — Geoapify API Key Baked into App Bundle
**Status:** OPEN — Action required outside the codebase. Log into [app.geoapify.com](https://app.geoapify.com), find the key `bdf13805f53643739a50ba6eae18cbb0`, and add an HTTP referrer restriction or usage quota. Without this, anyone who unpacks the APK can extract the key.

### L-4 — `client.ts` Error Message Includes Raw Response Body
**Status:** ACCEPTED — Only a risk if `APP_DEBUG=true` in production, which is confirmed false. The defensive posture relies on the server never leaking debug output. `APP_DEBUG=false` must be enforced in production `.env`.

### L-5 — Local `.env` Contains Active Mailtrap SMTP Credentials
**Status:** INFORMATIONAL — File is gitignored. Confirm production uses a separate SMTP credential set. Rotate Mailtrap credentials if unsure.

---

## PASS — Verified Clean

| Area | Result |
|---|---|
| Token storage (React Native) | `expo-secure-store` exclusively. No auth tokens in `AsyncStorage`. |
| API base URL | HTTPS enforced (`https://platetag.app/api/v1`). |
| Filament access gate | `canAccessPanel()` checks `is_admin === true`. `Authenticate` middleware on all `/admin/*` routes. |
| Admin panel login | Unauthenticated access redirects to login. No public bypass. |
| Password hashing | `Hash::make()` throughout. Never stored plain. |
| OTP storage | OTP hashed in DB with `Hash::make()`. Plaintext never persisted. |
| OTP single-use | Deleted on successful use; replaced on re-request. |
| User enumeration (forgot password) | Always returns success regardless of whether email exists. |
| Ownership checks | All `PATCH`/`DELETE` scope to `user_id = $request->user()->id`. |
| SQL injection | All queries use Eloquent ORM or bound parameters. No raw string interpolation. |
| Input validation | All controller methods validate before use. |
| Logout | Deletes current Sanctum token. |
| Password change | Revokes all other tokens. Requires current password. |
| Account deletion | DB transaction. Deletes discoveries and tokens before user record. |
| `APP_DEBUG=false` | Confirmed in local `.env`. Must be confirmed in production. |
| `.env` gitignored | Confirmed in both `platetag-api` and `platetag-app`. |
| No `dd()`/`dump()` calls | None found in application code. |
| ATS (iOS) | Not disabled. HTTPS enforced. |
| Debug build separation | EAS profiles correctly scoped. |

---

## A2 Production Server Audit — Results (2026-05-10)

### URL Exposure Tests

| URL | Expected | Actual | Status |
|---|---|---|---|
| `https://platetag.app/.env` | Not accessible | **403 Forbidden** (LiteSpeed blocking dot-files) | ✅ PASS |
| `https://platetag.app/composer.json` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/composer.lock` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/artisan` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/storage/logs/laravel.log` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/phpinfo.php` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/info.php` | Not accessible | 404 | ✅ PASS |
| `https://platetag.app/storage/` | Directory listing blocked | **403 Forbidden** | ✅ PASS |

The 404s for `artisan`, `composer.json`, and `composer.lock` confirm these files are NOT in the web root. The Laravel project root is correctly isolated from public access.

The 403 on `.env` is LiteSpeed's built-in dot-file protection, not a Laravel rule. This means `.env` is blocked even if it somehow ended up in the wrong directory. Good, but do not rely on this — the production `.env` must be placed in the Laravel project root (`/home/platetag/platetag-api/.env`), not in `public_html`.

---

### File Permissions Audit (via File Manager)

| Path | Expected | Actual | Status |
|---|---|---|---|
| `storage/` | 0755 | 0755 | ✅ PASS |
| `bootstrap/cache/` | 0755 | 0755 | ✅ PASS |
| `public/` | 0755 | 0755 | ✅ PASS |
| `*.php` source files | 0644 | 0644 | ✅ PASS |
| `bootstrap/cache/packages.php` | 0644 | **0755** | ⚠️ MINOR |
| `bootstrap/cache/services.php` | 0644 | **0755** | ⚠️ MINOR |

**Action — fix the two cache files:** In cPanel File Manager, select `bootstrap/cache/packages.php`, click Permissions, and set to `0644`. Repeat for `services.php`. These are Artisan-generated files that do not need to be executable. They get regenerated on next `php artisan config:cache` run anyway.

Note: `vendor/` and `bootstrap/cache/` were not reviewed in full — acceptable for this pass.

---

### Document Root Verification

The Domains panel shows Document Root: **`/public_html`**

This is a problem that requires investigation. For Laravel to work securely, the web server must point to `platetag-api/public/`, not to the Laravel project root and not to a bare `public_html` folder that may contain source files.

The URL test results are reassuring (no `artisan` or `composer.json` exposure), which suggests one of:
- `public_html` contains only the contents of Laravel's `public/` folder (correct), OR
- A redirect or symlink from `public_html` to `platetag-api/public/` exists

**Required action — confirm the document root setup:**
1. In cPanel → File Manager, navigate to `public_html`
2. Confirm it contains `index.php` and `.htaccess` (or similar) — not the full Laravel tree
3. If it contains `app/`, `config/`, `routes/` etc., the document root is misconfigured and the entire Laravel source is web-accessible — this is a critical finding

If `public_html` is correct (only `public/` contents), the Domains panel document root should be updated to explicitly show `/home/platetag/platetag-api/public` for clarity. Contact A2 support if the panel doesn't allow this change.

---

### Production `.env` — Not Located

The production `.env` was not found in the File Manager during the audit. Two likely causes:

1. **Hidden files are not displayed** (most likely). The cPanel File Manager hides dot-files by default.
   - Click the **Settings** gear icon (top-right of File Manager)
   - Check **"Show Hidden Files (dotfiles)"**
   - Click Save
   - Navigate to `/home/platetag/platetag-api/` and `.env` should now be visible

2. **The file does not exist yet.** If the site was freshly deployed after the database wipe, the production `.env` may not have been restored. Without it, the application cannot connect to the database and will fail silently or return 500 errors.

**If `.env` does not exist on production:** It must be created before the database restore. Do not upload the local `.env` directly — it contains local WAMP paths and credentials. Create a new production `.env` from the template below.

---

### Production `.env` — Required Values Before Database Restore

The following values must be set correctly in `/home/platetag/platetag-api/.env` on A2 Hosting. Do not copy the local file — edit these values for the production environment:

```
APP_ENV=production
APP_DEBUG=false
APP_URL=https://platetag.app

LOG_LEVEL=warning
BCRYPT_ROUNDS=12

# Production MySQL — get these from cPanel → MySQL Databases
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=<production_db_name>
DB_USERNAME=<production_db_user>
DB_PASSWORD=<production_db_password>

# MySQL binary paths on A2 Linux
MYSQLDUMP_PATH=/usr/bin/mysqldump
MYSQL_PATH=/usr/bin/mysql

# Sanctum — leave expiration as-is or confirm value
SANCTUM_TOKEN_EXPIRATION=10080

# Mail — use production SMTP, NOT Mailtrap
MAIL_MAILER=smtp
...
```

---

## ⚠️ User Action Checklist — All Items Require Manual Completion

This section tracks every action that cannot be automated and requires Larry to complete. Items remain here until explicitly verified and checked off.

**Rule for this document:** No finding marked OPEN here may be considered resolved until the checkbox below is manually checked and the date recorded. This checklist must be reviewed at the start of every production deploy session.

| # | Action | Blocking production restore? | Status |
|---|---|---|---|
| U-1 | **Restrict Geoapify API key** — log into [app.geoapify.com](https://app.geoapify.com), find key `bdf13805f53643739a50ba6eae18cbb0`, add HTTP referrer restriction or usage quota | No | ❌ OPEN |
| U-2 | **Confirm production `.env` exists** — enable hidden files in File Manager, verify `/home/platetag/platetag-api/.env` is present | **YES** | ✅ CONFIRMED 2026-05-10 — found, permissions 0644 |
| U-3 | **Verify production `.env` values** — `APP_DEBUG=false`, `LOG_LEVEL=warning`, `BCRYPT_ROUNDS=12`, `MYSQLDUMP_PATH=/bin/mysqldump`, `MYSQL_PATH=/bin/mysql` | **YES** | ✅ CONFIRMED 2026-05-10 — values verified and corrected via File Manager; `BCRYPT_ROUNDS=12`, `MYSQLDUMP_PATH=/bin/mysqldump`, `MYSQL_PATH=/bin/mysql` added; `LOG_LEVEL=error` (stricter than warning, acceptable); production SMTP confirmed (`mail.platetag.app`) |
| U-4 | **Confirm document root** — navigate to `public_html` in File Manager, confirm it contains only `index.php` + `.htaccess`, NOT the full Laravel source tree | **YES** | ✅ CONFIRMED 2026-05-10 — public_html contains index.php, robots.txt, favicon.ico, css/, js/, vendor/ (Filament assets), storage/ (symlink). No app/, config/, routes/. |
| U-5 | **Fix cache file permissions** — set `bootstrap/cache/packages.php` and `bootstrap/cache/services.php` to `0644` via File Manager | No | ✅ CONFIRMED 2026-05-10 — corrected to rw-r--r-- (0644) |
| U-6 | **Confirm production SMTP** — verify production `.env` uses production SMTP credentials, not Mailtrap | No | ✅ CONFIRMED 2026-05-10 — `MAIL_HOST=mail.platetag.app`, not Mailtrap sandbox |
| U-7 | **Confirm A2 proxy IP** — after first production deploy, check what IP Laravel sees for `$request->ip()` on a known request; if it's wrong (shows a private LiteSpeed IP), add that IP to `trustProxies` in `bootstrap/app.php` | No | ❌ OPEN — verify post-deploy |

**Production restore is unblocked. All blocking items (U-2, U-3, U-4) are confirmed.**

---

## Open Items — Require Action Outside Codebase

See User Action Checklist above. All items consolidated there.

---

## Re-Audit Summary (Pass 2)

All HIGH and MEDIUM findings from Pass 1 were remediated in the same session. A targeted re-check confirmed:

- `bootstrap/app.php` — `trustProxies` now scoped to private ranges ✅
- `PlatesController::show()` — `is_active` filter present ✅
- `AuthController::login()` — per-email lockout wired ✅
- `DatabaseTools.php` — all shell args escaped; binary paths from env ✅
- `.env` — `BCRYPT_ROUNDS=12`, `LOG_LEVEL=warning` ✅
- `platetag-app/.gitignore` — `*.apk`, `*.aab`, `*.zip` added ✅
- Stray binary files — moved to `build-artifacts/` ✅

No new findings surfaced during the re-check.
