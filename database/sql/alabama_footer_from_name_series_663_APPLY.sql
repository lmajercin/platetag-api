-- =============================================================
-- APPLY — footer_override from name (strip "AL - ") for series 721
-- Database: platetag_db1
-- Tool:     phpMyAdmin → http://localhost/phpmyadmin
--
-- phpMyAdmin rule: ONE paste, ONE Go. Autocommit — saves on UPDATE.
--
-- Logic:  IF footer_override IS NULL AND name starts with "AL - "
--         THEN footer_override = SUBSTRING(name, 6)
--
-- Touches ONLY: footer_override, updated_at
-- Skips:    rows that already have footer_override; prefix mismatches
--
-- Local WAMP only (Content Editing Rule — never production Filament).
-- =============================================================

USE platetag_db1;

-- ── BEFORE ────────────────────────────────────────────────────
SELECT COUNT(*) AS null_footer_before
FROM plates
WHERE series_id = 663 AND footer_override IS NULL;

SELECT COUNT(*) AS has_footer_before
FROM plates
WHERE series_id = 663 AND footer_override IS NOT NULL;

-- Should be 0 rows — if not, stop and review before UPDATE
SELECT id, name, footer_override
FROM plates
WHERE series_id = 663
  AND footer_override IS NULL
  AND LEFT(name, 5) <> 'AL - '
ORDER BY id;

-- ── UPDATE (saves immediately) ────────────────────────────────
UPDATE plates
SET
    footer_override = SUBSTRING(name, 6),
    updated_at      = NOW()
WHERE series_id = 663
  AND footer_override IS NULL
  AND LEFT(name, 5) = 'AL - ';

-- ── AFTER ─────────────────────────────────────────────────────
SELECT COUNT(*) AS null_footer_after
FROM plates
WHERE series_id = 663 AND footer_override IS NULL;

SELECT COUNT(*) AS has_footer_after
FROM plates
WHERE series_id = 663 AND footer_override IS NOT NULL;

SELECT id, name, footer_override
FROM plates
WHERE series_id = 663
ORDER BY id
LIMIT 10;

-- PASS: null_footer_after = 0 (or only rows that had prefix mismatch / already skipped)
-- Spot-check: footer_override = plate title without leading "AL - "
