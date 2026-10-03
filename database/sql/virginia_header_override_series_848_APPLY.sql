-- =============================================================
-- APPLY — header_override = 'Virginia' for series 848 (NULL only)
-- Database: platetag_db1
-- Tool:     phpMyAdmin → http://localhost/phpmyadmin
--
-- phpMyAdmin rule: ONE paste, ONE Go. Do not run COMMIT separately.
-- This script uses autocommit (no transaction) — saves on UPDATE.
--
-- Touches ONLY: header_override, updated_at
-- Does NOT touch: name, slug, footer_override, detail, or any other column
--
-- Local WAMP only (Content Editing Rule — never production Filament).
-- =============================================================

USE platetag_db1;

-- ── BEFORE (read-only check) ──────────────────────────────────
SELECT
    s.id AS series_id,
    s.name AS series_name,
    r.name AS region_name
FROM series s
LEFT JOIN regions r ON r.id = s.region_id
WHERE s.id = 848;

SELECT COUNT(*) AS null_before
FROM plates
WHERE series_id = 848 AND header_override IS NULL;

-- ── UPDATE (saves immediately) ────────────────────────────────
UPDATE plates
SET
    header_override = 'Virginia',
    updated_at      = NOW()
WHERE series_id = 848
  AND header_override IS NULL;

-- ── AFTER (confirm it worked) ─────────────────────────────────
SELECT COUNT(*) AS null_after
FROM plates
WHERE series_id = 848 AND header_override IS NULL;

SELECT COUNT(*) AS Virginia_count
FROM plates
WHERE series_id = 848 AND header_override = 'Virginia';

SELECT
    header_override,
    COUNT(*) AS plate_count
FROM plates
WHERE series_id = 848
GROUP BY header_override
ORDER BY plate_count DESC;

SELECT id, name, header_override, footer_override
FROM plates
WHERE series_id = 848
ORDER BY id
LIMIT 10;

-- PASS: null_after = 0, Virginia_count increased by null_before amount
-- Spot-check: Browse → plates → filter series_id = 848 → header_override shows Virginia
