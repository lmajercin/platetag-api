-- =============================================================
-- VERIFY — after bulk Vision tagger run for series 721
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (read-only)
-- Local WAMP only.
--
-- Run AFTER:
--   php artisan tagger:bulk-series 721
-- =============================================================

USE platetag_db1;

-- -----------------------------------------------------------------
-- Step 1: Pass/fail summary — all plates in series should be complete
-- -----------------------------------------------------------------
SELECT
    COUNT(*) AS total_in_series
FROM plates
WHERE series_id = 721;

SELECT
    COUNT(*) AS pass_all_fields_set_and_reviewed
FROM plates
WHERE series_id = 721
  AND detail IS NOT NULL AND detail != ''
  AND tags IS NOT NULL AND tags != ''
  AND ai_detail IS NOT NULL AND ai_detail != ''
  AND ai_tags IS NOT NULL AND ai_tags != ''
  AND ai_reviewed = 1
  AND detail = ai_detail
  AND tags = ai_tags;

SELECT
    COUNT(*) AS fail_still_missing_detail_or_tags
FROM plates
WHERE series_id = 721
  AND (
      detail IS NULL OR detail = ''
      OR tags IS NULL OR tags = ''
  );

SELECT
    COUNT(*) AS fail_ai_reviewed_still_zero
FROM plates
WHERE series_id = 721
  AND ai_reviewed = 0;

SELECT
    COUNT(*) AS fail_live_and_ai_mismatch
FROM plates
WHERE series_id = 721
  AND (
      (detail IS NOT NULL AND ai_detail IS NOT NULL AND detail != ai_detail)
      OR (tags IS NOT NULL AND ai_tags IS NOT NULL AND tags != ai_tags)
  );

-- -----------------------------------------------------------------
-- Step 2: Any problem rows (investigate before sync to production)
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    CASE WHEN detail IS NULL OR detail = '' THEN 'MISSING' ELSE 'ok' END AS detail_status,
    CASE WHEN tags IS NULL OR tags = '' THEN 'MISSING' ELSE 'ok' END AS tags_status,
    ai_reviewed,
    CASE WHEN detail = ai_detail THEN 'match' ELSE 'MISMATCH' END AS detail_match,
    CASE WHEN tags = ai_tags THEN 'match' ELSE 'MISMATCH' END AS tags_match,
    image_filename
FROM plates
WHERE series_id = 721
  AND (
      detail IS NULL OR detail = ''
      OR tags IS NULL OR tags = ''
      OR ai_reviewed = 0
      OR detail != ai_detail
      OR tags != ai_tags
  )
ORDER BY id;

-- -----------------------------------------------------------------
-- Step 3: Spot-check sample — random-style first/last/middle IDs
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    LEFT(detail, 120)    AS detail_preview,
    LEFT(tags, 120)      AS tags_preview,
    ai_reviewed,
    updated_at
FROM plates
WHERE series_id = 721
ORDER BY id
LIMIT 5;

SELECT
    id,
    name,
    LEFT(detail, 120)    AS detail_preview,
    LEFT(tags, 120)      AS tags_preview,
    ai_reviewed,
    updated_at
FROM plates
WHERE series_id = 721
ORDER BY id DESC
LIMIT 5;
