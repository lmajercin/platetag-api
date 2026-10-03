-- =============================================================
-- DRY RUN — Set header_override = 'Washington DC' on series 681
-- Database: platetag_db1
-- Target:   plates WHERE series_id = 681 AND header_override IS NULL
--
-- NO DATA IS SAVED — transaction rolls back at the end.
-- Review all SELECT output before running the apply script.
-- Local WAMP only (Content Editing Rule — never on production Filament).
-- =============================================================

USE platetag_db1;

-- -----------------------------------------------------------------
-- Step 1: Confirm series 681 is the expected WASHINGTON DC series
-- -----------------------------------------------------------------
SELECT
    s.id          AS series_id,
    s.name        AS series_name,
    r.name        AS region_name,
    r.code        AS region_code
FROM series s
LEFT JOIN regions r ON r.id = s.region_id
WHERE s.id = 681;

-- -----------------------------------------------------------------
-- Step 2: Summary counts (what would change vs what would not)
-- -----------------------------------------------------------------
SELECT
    COUNT(*) AS total_plates_in_series
FROM plates
WHERE series_id = 681;

SELECT
    COUNT(*) AS would_update_null_header
FROM plates
WHERE series_id = 681
  AND header_override IS NULL;

SELECT
    COUNT(*) AS skipped_non_null_header
FROM plates
WHERE series_id = 681
  AND header_override IS NOT NULL;

SELECT
    header_override,
    COUNT(*) AS plate_count
FROM plates
WHERE series_id = 681
GROUP BY header_override
ORDER BY plate_count DESC, header_override;

-- -----------------------------------------------------------------
-- Step 3: Preview rows that WOULD be updated (before state)
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    slug,
    series_id,
    header_override,
    footer_override,
    updated_at
FROM plates
WHERE series_id = 681
  AND header_override IS NULL
ORDER BY id;

-- -----------------------------------------------------------------
-- Step 4: Sample rows that would NOT be updated (already set)
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    header_override,
    footer_override
FROM plates
WHERE series_id = 681
  AND header_override IS NOT NULL
ORDER BY id
LIMIT 20;

-- -----------------------------------------------------------------
-- Step 5: Simulate UPDATE inside a transaction, then ROLLBACK
-- -----------------------------------------------------------------
START TRANSACTION;

UPDATE plates
SET
    header_override = 'WASHINGTON DC',
    updated_at      = NOW()
WHERE series_id = 681
  AND header_override IS NULL;

SELECT ROW_COUNT() AS rows_updated_this_run;

SELECT
    id,
    name,
    header_override,
    footer_override,
    updated_at
FROM plates
WHERE series_id = 681
  AND header_override = 'WASHINGTON DC'
ORDER BY id;

ROLLBACK;

-- -----------------------------------------------------------------
-- Step 6: Post-rollback sanity check (should match Step 2 null count)
-- -----------------------------------------------------------------
SELECT
    COUNT(*) AS null_header_after_rollback
FROM plates
WHERE series_id = 681
  AND header_override IS NULL;

-- Expected: null_header_after_rollback = would_update_null_header from Step 2
