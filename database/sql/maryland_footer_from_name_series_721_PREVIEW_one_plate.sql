-- =============================================================
-- PREVIEW — one plate: footer_override from name (strip "MD - ")
-- Database: platetag_db1 | Series: 721
-- Tool:     phpMyAdmin — ONE paste, ONE Go (read-only, no changes)
--
-- Plate ID 4440 used as example (Accokeek VFD). Change id below if needed.
-- Local WAMP only.
-- =============================================================

USE platetag_db1;

-- What the row looks like now + what footer WOULD become
SELECT
    id,
    name,
    footer_override AS footer_now,
    SUBSTRING(name, 6) AS footer_would_be,
    CASE
        WHEN LEFT(name, 5) = 'MD - ' THEN 'prefix OK'
        ELSE 'PREFIX MISMATCH — review before batch'
    END AS prefix_check
FROM plates
WHERE id = 4440
  AND series_id = 721;

-- How many in series 721 would qualify for a full run (NULL footer only)
SELECT COUNT(*) AS null_footer_count
FROM plates
WHERE series_id = 721 AND footer_override IS NULL;

SELECT COUNT(*) AS already_has_footer
FROM plates
WHERE series_id = 721 AND footer_override IS NOT NULL;

-- Any names that do NOT start with "MD - " (batch risk — should be 0)
SELECT id, name, footer_override
FROM plates
WHERE series_id = 721
  AND footer_override IS NULL
  AND LEFT(name, 5) <> 'MD - '
ORDER BY id
LIMIT 25;
