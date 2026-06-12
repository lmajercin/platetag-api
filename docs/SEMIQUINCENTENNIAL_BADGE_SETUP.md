# Adding the Semiquincentennial Collection Badge

## Overview

This guide walks through adding the "America's 250th - Semiquincentennial" badge — a new **collection** type badge where users must collect 16 specific plates across multiple states.

## What's New

- **Badge Type:** `collection` (new type alongside existing `geographic` and `milestone`)
- **Badge Name:** America's 250th - Semiquincentennial
- **Description:** Find all plates celebrating the United States Semiquincentennial (250 Years)!
- **Icon:** `flag` (Phosphor icon)
- **Required Plates:** 16 plates across 15 states

## Files Created

1. **Migration:** `2026_06_12_000001_add_collection_badge_type.php`
   - Adds 'collection' to the badges.type enum

2. **Migration:** `2026_06_12_000002_create_badge_plates_table.php`
   - Creates new junction table linking badges to specific plates

3. **SQL Script:** `database/sql/add_semiquincentennial_badge.sql`
   - Inserts the badge and all 16 plate associations

## Steps to Apply (Local)

### 1. Run migrations

```powershell
cd C:\wamp64\www\platetag-api
php artisan migrate
```

Expected output:
```
Migrating: 2026_06_12_000001_add_collection_badge_type
Migrated:  2026_06_12_000001_add_collection_badge_type (X ms)
Migrating: 2026_06_12_000002_create_badge_plates_table
Migrated:  2026_06_12_000002_create_badge_plates_table (X ms)
```

### 2. Insert badge data via SQL

**Option A — via artisan:**
```powershell
Get-Content C:\wamp64\www\platetag-api\database\sql\add_semiquincentennial_badge.sql | C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe -u root -p"4rfv$RFV" platetag_db1
```

**Option B — via phpMyAdmin:**
1. Open http://localhost/phpmyadmin
2. Select `platetag_db1` database
3. Click **SQL** tab
4. Copy/paste contents of `database/sql/add_semiquincentennial_badge.sql`
5. Click **Go**

### 3. Verify locally

```powershell
C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe -u root -p"4rfv$RFV" -e "SELECT * FROM badges WHERE slug = 'americas-250th-semiquincentennial'" platetag_db1
```

Should show 1 row with type = 'collection'

```powershell
C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe -u root -p"4rfv$RFV" -e "SELECT COUNT(*) as plate_count FROM badge_plates WHERE badge_id = (SELECT id FROM badges WHERE slug = 'americas-250th-semiquincentennial')" platetag_db1
```

Should show `plate_count: 16`

## Steps to Apply (Production)

### 1. Upload migration files via SCP

```powershell
scp C:\wamp64\www\platetag-api\database\migrations\2026_06_12_000001_add_collection_badge_type.php platetag-prod:~/platetag-api/database/migrations/
```

```powershell
scp C:\wamp64\www\platetag-api\database\migrations\2026_06_12_000002_create_badge_plates_table.php platetag-prod:~/platetag-api/database/migrations/
```

### 2. Run migrations on production

```powershell
ssh platetag-prod "cd ~/platetag-api && php artisan migrate --force"
```

The `--force` flag is required in production to confirm you want to run migrations.

### 3. Upload and run SQL script

```powershell
scp C:\wamp64\www\platetag-api\database\sql\add_semiquincentennial_badge.sql platetag-prod:~/semiquincentennial.sql
```

```powershell
ssh platetag-prod "PROD_DB=\$(grep ^DB_DATABASE ~/platetag-api/.env | sed 's/.*=//'); PROD_PASS=\$(grep ^DB_PASSWORD ~/platetag-api/.env | sed 's/.*=//'); mysql -u \$(grep ^DB_USERNAME ~/platetag-api/.env | sed 's/.*=//') -p\"\$PROD_PASS\" \"\$PROD_DB\" < ~/semiquincentennial.sql && rm ~/semiquincentennial.sql"
```

### 4. Verify on production

```powershell
ssh platetag-prod "cd ~/platetag-api && php artisan tinker --execute=\"echo 'Badge count: ' . \App\Models\Badge::where('type', 'collection')->count();\""
```

Should show: `Badge count: 1`

## Plate List (16 plates)

| Region | Plate ID | Region ID | Notes |
|--------|----------|-----------|-------|
| Delaware | 3034 | 8 | |
| Florida | 10647 | 10 | |
| Georgia | 3647 | 11 | |
| Idaho | 10648 | 13 | |
| Indiana | 10649 | 15 | |
| Louisiana | 10556 | 19 | |
| Massachusetts | 4392 | 22 | |
| Michigan | 5788 | 23 | |
| New Hampshire | 7143 | 30 | |
| Pennsylvania | 56 | 39 | |
| Pennsylvania | 1142 | 39 | (2nd PA plate) |
| South Carolina | 8697 | 41 | |
| Texas | 10275 | 44 | |
| Utah | 10652 | 45 | |
| Virginia | 9514 | 47 | |
| West Virginia | 10636 | 49 | |

## Backend Code Updates Needed

After migrations are applied, you'll need to update:

1. **Badge checking logic** — Add collection badge logic to award badges when all required plates are collected
2. **Badge models** — Add relationships for `badge_plates`
3. **API responses** — Include plate requirements for collection badges

Let me know if you want help with the backend logic implementation.

## Rollback (if needed)

If something goes wrong and you need to undo:

```sql
-- Remove badge data
DELETE FROM badge_plates WHERE badge_id = (SELECT id FROM badges WHERE slug = 'americas-250th-semiquincentennial');
DELETE FROM badges WHERE slug = 'americas-250th-semiquincentennial';

-- Then rollback migrations
php artisan migrate:rollback --step=2
```
