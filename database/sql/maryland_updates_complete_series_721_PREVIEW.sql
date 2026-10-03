-- =============================================================
-- PREVIEW — updates_complete = 1 for series 721 (currently 0)
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (read-only)
-- Local WAMP only.
-- =============================================================

USE platetag_db1;

SELECT COUNT(*) AS total_in_series
FROM plates
WHERE series_id = 721;

SELECT COUNT(*) AS would_update_zero_to_one
FROM plates
WHERE series_id = 721 AND updates_complete = 0;

SELECT COUNT(*) AS already_complete
FROM plates
WHERE series_id = 721 AND updates_complete = 1;

-- Sample rows that WOULD change
SELECT id, name, header_override, footer_override, updates_complete
FROM plates
WHERE series_id = 721 AND updates_complete = 0
ORDER BY id
LIMIT 10;

-- Rows already marked complete (should stay untouched)
SELECT id, name, updates_complete
FROM plates
WHERE series_id = 721 AND updates_complete = 1
ORDER BY id
LIMIT 10;
