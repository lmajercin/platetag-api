-- =============================================================
-- PREVIEW — Header/Footer Vision tagger — test plates (read-only)
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (no changes)
-- Local WAMP only.
--
-- Purpose:  Validate eligibility + context before manual Vision trials
--           and before building: php artisan tagger:header-footer-series {series_id}
--
-- Test plate IDs (8110 excluded — already complete):
--   7324  NM - Pearl Harbor Survivor
--   8441  SC - Air Medal - V2          (trap: SC state name often in FOOTER)
--   9661  WV - World War II Veteran
--   8976  VT - US Veteran - Vietnam War
--   8778  SD - Permanently Disabled Person
--
-- Eligibility (ALL must be true):
--   header_override IS NULL (or '')
--   footer_override IS NULL (or '')
--   updates_complete = 0
--   image_filename present
--
-- On success: write header_override and/or footer_override; set updates_complete = 1
-- NULL is valid when no text in that zone (reviewed, intentionally empty).
-- Multi-line text in one field: join lines with | (pipe)
-- =============================================================

USE platetag_db1;

-- -----------------------------------------------------------------
-- 1) Test plates — current row state + eligibility
-- -----------------------------------------------------------------
SELECT
    p.id,
    p.name,
    p.series_id,
    s.name AS series_name,
    r.name AS region_name,
    r.code AS region_code,
    p.header_override,
    p.footer_override,
    p.updates_complete,
    p.image_filename,
    CASE
        WHEN (p.header_override IS NOT NULL AND p.header_override <> '')
          OR (p.footer_override IS NOT NULL AND p.footer_override <> '')
            THEN 'EXCLUDED — override already set'
        WHEN COALESCE(p.updates_complete, 0) = 1
            THEN 'EXCLUDED — updates_complete = 1'
        WHEN p.image_filename IS NULL OR p.image_filename = ''
            THEN 'EXCLUDED — no image'
        ELSE 'ELIGIBLE'
    END AS eligibility,
    CASE p.id
        WHEN 8441 THEN 'PITFALL: South Carolina — state name often appears in FOOTER, not header'
        WHEN 7324 THEN 'FOOTER includes Pearl Harbor Survivor (below serial) + New Mexico USA — use | top-to-bottom'
        ELSE NULL
    END AS vision_note
FROM plates p
INNER JOIN series s ON s.id = p.series_id
LEFT JOIN regions r ON r.id = s.region_id
WHERE p.id IN (7324, 8441, 9661, 8976, 8778)
ORDER BY p.id;

-- -----------------------------------------------------------------
-- 2) Hint context the Vision script will receive (region + plate name)
-- -----------------------------------------------------------------
SELECT
    p.id,
    p.name AS plate_name_hint,
    r.name AS region_name_hint,
    CONCAT(
        'Region hint: ', COALESCE(r.name, '(unknown)'),
        ' | Plate name hint: ', COALESCE(p.name, '(unknown)'),
        ' | Read HEADER (top-center) and FOOTER (bottom-center) from image only.',
        ' | Ignore middle-left, middle-right, middle-center text.',
        ' | NULL if zone has no text. Multi-line: use | separator.'
    ) AS prompt_context_preview
FROM plates p
INNER JOIN series s ON s.id = p.series_id
LEFT JOIN regions r ON r.id = s.region_id
WHERE p.id IN (7324, 8441, 9661, 8976, 8778)
ORDER BY p.id;

-- -----------------------------------------------------------------
-- 3) Per-series eligible counts for the five test plates' series
-- -----------------------------------------------------------------
SELECT
    p.series_id,
    s.name AS series_name,
    r.name AS region_name,
    COUNT(*) AS eligible_plates
FROM plates p
INNER JOIN series s ON s.id = p.series_id
LEFT JOIN regions r ON r.id = s.region_id
WHERE p.series_id IN (
    SELECT DISTINCT series_id FROM plates WHERE id IN (7324, 8441, 9661, 8976, 8778)
)
  AND (p.header_override IS NULL OR p.header_override = '')
  AND (p.footer_override IS NULL OR p.footer_override = '')
  AND COALESCE(p.updates_complete, 0) = 0
  AND p.image_filename IS NOT NULL
  AND p.image_filename <> ''
GROUP BY p.series_id, s.name, r.name
ORDER BY p.series_id;

-- -----------------------------------------------------------------
-- 4) Global queue size — remaining unchecked plates (~3,000 target)
-- -----------------------------------------------------------------
SELECT COUNT(*) AS eligible_plates_total
FROM plates p
WHERE (p.header_override IS NULL OR p.header_override = '')
  AND (p.footer_override IS NULL OR p.footer_override = '')
  AND COALESCE(p.updates_complete, 0) = 0
  AND p.image_filename IS NOT NULL
  AND p.image_filename <> '';

-- -----------------------------------------------------------------
-- 5) Partial-NULL rows (EXCLUDED by design — both overrides must be NULL)
-- -----------------------------------------------------------------
SELECT COUNT(*) AS excluded_one_override_set
FROM plates p
WHERE COALESCE(p.updates_complete, 0) = 0
  AND p.image_filename IS NOT NULL
  AND p.image_filename <> ''
  AND (
    (
      (p.header_override IS NULL OR p.header_override = '')
      AND (p.footer_override IS NOT NULL AND p.footer_override <> '')
    )
    OR (
      (p.footer_override IS NULL OR p.footer_override = '')
      AND (p.header_override IS NOT NULL AND p.header_override <> '')
    )
  );

-- -----------------------------------------------------------------
-- 6) Spot-check: South Carolina series with eligible plates (footer-trap region)
-- -----------------------------------------------------------------
SELECT
    p.id,
    p.name,
    p.header_override,
    p.footer_override,
    p.updates_complete
FROM plates p
INNER JOIN series s ON s.id = p.series_id
LEFT JOIN regions r ON r.id = s.region_id
WHERE r.code = 'SC'
  AND (p.header_override IS NULL OR p.header_override = '')
  AND (p.footer_override IS NULL OR p.footer_override = '')
  AND COALESCE(p.updates_complete, 0) = 0
  AND p.image_filename IS NOT NULL
  AND p.image_filename <> ''
ORDER BY p.id
LIMIT 15;

-- -----------------------------------------------------------------
-- Manual check: open plate images in Filament Browse for the five IDs above.
-- Compare expected header/footer bands to Vision output before series runs.
-- -----------------------------------------------------------------
