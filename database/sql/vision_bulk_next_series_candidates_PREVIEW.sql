-- =============================================================
-- PREVIEW — next bulk Vision tagger series candidates
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (read-only)
-- Local WAMP only.
--
-- Series qualifies for detail/tags bulk tagger when EVERY plate in the series has:
--   updates_complete = 1  (header/footer reviewed — NULL overrides are OK)
--
-- Counts only plates ready for tagger:bulk-series:
--   detail, ai_detail, tags, ai_tags empty; ai_reviewed = 0; has image
-- Plates already tagged in the same series do NOT exclude the series.
-- =============================================================

USE platetag_db1;

WITH series_ready AS (
    SELECT
        p.series_id
    FROM plates p
    GROUP BY p.series_id
    HAVING
        SUM(CASE WHEN COALESCE(p.updates_complete, 0) = 0 THEN 1 ELSE 0 END) = 0
),
eligible AS (
    SELECT
        p.series_id,
        COUNT(*) AS eligible_plates
    FROM plates p
    INNER JOIN series_ready sr ON sr.series_id = p.series_id
    WHERE (p.detail IS NULL OR p.detail = '')
      AND (p.ai_detail IS NULL OR p.ai_detail = '')
      AND (p.tags IS NULL OR p.tags = '')
      AND (p.ai_tags IS NULL OR p.ai_tags = '')
      AND p.ai_reviewed = 0
      AND p.image_filename IS NOT NULL
      AND p.image_filename != ''
    GROUP BY p.series_id
)
SELECT
    e.series_id,
    s.name        AS series_name,
    r.name        AS region_name,
    e.eligible_plates,
    (SELECT COUNT(*) FROM plates p2 WHERE p2.series_id = e.series_id) AS total_plates_in_series
FROM eligible e
INNER JOIN series s ON s.id = e.series_id
LEFT JOIN regions r ON r.id = s.region_id
ORDER BY e.eligible_plates DESC, e.series_id ASC;

-- -----------------------------------------------------------------
-- Optional: series not yet ready for detail/tags bulk (updates_complete gate)
-- -----------------------------------------------------------------
SELECT
    p.series_id,
    s.name AS series_name,
    COUNT(*) AS total_plates,
    SUM(CASE WHEN COALESCE(p.updates_complete, 0) = 0 THEN 1 ELSE 0 END) AS updates_not_complete
FROM plates p
INNER JOIN series s ON s.id = p.series_id
GROUP BY p.series_id, s.name
HAVING updates_not_complete > 0
ORDER BY total_plates DESC, p.series_id ASC
LIMIT 25;
