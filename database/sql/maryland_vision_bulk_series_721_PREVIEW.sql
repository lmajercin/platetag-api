-- =============================================================
-- PREVIEW — bulk Vision tagger eligibility for series 721
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (read-only)
-- Local WAMP only.
--
-- Use BEFORE running:
--   php artisan tagger:bulk-series 721 --dry-run
--   php artisan tagger:bulk-series 721 --limit=5
-- =============================================================

USE platetag_db1;

-- -----------------------------------------------------------------
-- Step 1: Confirm series 721 is Maryland Specialty
-- -----------------------------------------------------------------
SELECT
    s.id          AS series_id,
    s.name        AS series_name,
    r.name        AS region_name,
    r.code        AS region_code
FROM series s
LEFT JOIN regions r ON r.id = s.region_id
WHERE s.id = 721;

-- -----------------------------------------------------------------
-- Step 2: Summary counts for this series
-- -----------------------------------------------------------------
SELECT COUNT(*) AS total_plates_in_series
FROM plates
WHERE series_id = 721;

SELECT COUNT(*) AS eligible_completely_untouched
FROM plates
WHERE series_id = 721
  AND image_filename IS NOT NULL
  AND image_filename != ''
  AND (detail IS NULL OR detail = '')
  AND (ai_detail IS NULL OR ai_detail = '')
  AND (tags IS NULL OR tags = '')
  AND (ai_tags IS NULL OR ai_tags = '')
  AND ai_reviewed = 0;

SELECT COUNT(*) AS skipped_has_any_content_or_reviewed
FROM plates
WHERE series_id = 721
  AND (
      (detail IS NOT NULL AND detail != '')
      OR (ai_detail IS NOT NULL AND ai_detail != '')
      OR (tags IS NOT NULL AND tags != '')
      OR (ai_tags IS NOT NULL AND ai_tags != '')
      OR ai_reviewed = 1
  );

SELECT COUNT(*) AS missing_image_filename
FROM plates
WHERE series_id = 721
  AND (image_filename IS NULL OR image_filename = '');

-- -----------------------------------------------------------------
-- Step 3: Sample rows the bulk tagger WOULD process
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    detail,
    ai_detail,
    tags,
    ai_tags,
    ai_reviewed,
    image_filename
FROM plates
WHERE series_id = 721
  AND image_filename IS NOT NULL
  AND image_filename != ''
  AND (detail IS NULL OR detail = '')
  AND (ai_detail IS NULL OR ai_detail = '')
  AND (tags IS NULL OR tags = '')
  AND (ai_tags IS NULL OR ai_tags = '')
  AND ai_reviewed = 0
ORDER BY id
LIMIT 25;

-- -----------------------------------------------------------------
-- Step 4: Rows skipped (any content or ai_reviewed=1 — never touched)
-- -----------------------------------------------------------------
SELECT
    id,
    name,
    CASE WHEN detail IS NOT NULL AND detail != '' THEN 'set' ELSE '' END AS detail,
    CASE WHEN ai_detail IS NOT NULL AND ai_detail != '' THEN 'set' ELSE '' END AS ai_detail,
    CASE WHEN tags IS NOT NULL AND tags != '' THEN 'set' ELSE '' END AS tags,
    CASE WHEN ai_tags IS NOT NULL AND ai_tags != '' THEN 'set' ELSE '' END AS ai_tags,
    ai_reviewed
FROM plates
WHERE series_id = 721
  AND (
      (detail IS NOT NULL AND detail != '')
      OR (ai_detail IS NOT NULL AND ai_detail != '')
      OR (tags IS NOT NULL AND tags != '')
      OR (ai_tags IS NOT NULL AND ai_tags != '')
      OR ai_reviewed = 1
  )
ORDER BY id
LIMIT 25;
