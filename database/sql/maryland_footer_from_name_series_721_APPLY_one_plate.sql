-- =============================================================
-- APPLY — ONE plate: copy name → footer_override (strip "MD - ")
-- Database: platetag_db1 | Series: 721 | Plate id: 4440
-- Tool:     phpMyAdmin — ONE paste, ONE Go (autocommit)
--
-- Touches ONLY: footer_override, updated_at
-- Only runs if footer_override IS NULL and id = 4440
--
-- Change 4440 to another id if you prefer a different test plate.
-- Local WAMP only.
-- =============================================================

USE platetag_db1;

-- BEFORE
SELECT id, name, footer_override AS footer_before
FROM plates
WHERE id = 4440 AND series_id = 721;

-- UPDATE (saves immediately)
UPDATE plates
SET
    footer_override = SUBSTRING(name, 6),
    updated_at      = NOW()
WHERE id = 4440
  AND series_id = 721
  AND footer_override IS NULL
  AND LEFT(name, 5) = 'MD - ';

-- AFTER
SELECT id, name, footer_override AS footer_after
FROM plates
WHERE id = 4440 AND series_id = 721;

-- PASS: footer_after = name with first 5 chars ("MD - ") removed
-- Example: "MD - Accokeek Volunteer Fire Department" → "Accokeek Volunteer Fire Department"
