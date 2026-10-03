-- =============================================================
-- APPLY — updates_complete = 1 for series 687 (where currently 0)
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go (autocommit)
--
-- Touches ONLY: updates_complete, updated_at
-- Skips: rows already updates_complete = 1
--
-- Local WAMP only (Content Editing Rule — never production Filament).
-- =============================================================

USE platetag_db1;

-- ── BEFORE ────────────────────────────────────────────────────
SELECT COUNT(*) AS zero_before
FROM plates
WHERE series_id = 687 AND updates_complete = 0;

SELECT COUNT(*) AS one_before
FROM plates
WHERE series_id = 687 AND updates_complete = 1;

-- ── UPDATE (saves immediately) ────────────────────────────────
UPDATE plates
SET
    updates_complete = 1,
    updated_at       = NOW()
WHERE series_id = 687
  AND updates_complete = 0;

-- ── AFTER ─────────────────────────────────────────────────────
SELECT COUNT(*) AS zero_after
FROM plates
WHERE series_id = 687 AND updates_complete = 0;

SELECT COUNT(*) AS one_after
FROM plates
WHERE series_id = 687 AND updates_complete = 1;

SELECT id, name, header_override, footer_override, updates_complete
FROM plates
WHERE series_id = 687
ORDER BY id
LIMIT 10;

-- PASS: zero_after = 0, one_after = total_in_series
