-- =============================================================
-- Trailer / Non-Passenger Category — INSERT + ASSIGN
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go
-- Local WAMP only.
--
-- Steps:
--   1. Preview: check for existing Trailer category + candidate plates
--   2. Insert new category row (idempotent — skips if slug already exists)
--   3. Assign new category_id to eligible trailer plates
--   4. Verify counts
--
-- Scope of assignment:
--   Only plates currently in 'Other / Specialty' (id=15) whose name
--   contains 'Trailer'. Plates already in Agricultural, Dealer,
--   Government/Exempt, Standard Issue, etc. keep their existing
--   category — those are correct for their plate type.
--
--   Farm Trailer plates → stay in Agricultural (correct)
--   Dealer Trailer plates → stay in Dealer / Manufacturer (correct)
--   Government / Exempt trailers → stay in Government / Exempt (correct)
--   Standard Issue motorcycle trailers → stay in Standard Issue (correct)
--   "Other / Specialty" trailers → move to Trailer / Non-Passenger
-- =============================================================

USE platetag_db1;

-- -----------------------------------------------------------------
-- Step 1 — Preview: existing Trailer category + candidate plates
-- -----------------------------------------------------------------

-- Current categories
SELECT id, name, slug, is_active FROM categories ORDER BY id;

-- Candidate plates: Other/Specialty + name contains Trailer
SELECT COUNT(*) AS candidates_to_reassign
FROM plates
WHERE category_id = 15
  AND name LIKE '%Trailer%';

-- Sample of candidates (first 20)
SELECT id, name, series_id, category_id
FROM plates
WHERE category_id = 15
  AND name LIKE '%Trailer%'
ORDER BY id
LIMIT 20;

-- Plates that WILL NOT be moved (already in a better category)
SELECT COUNT(*) AS kept_in_existing_category
FROM plates
WHERE category_id != 15
  AND name LIKE '%Trailer%';

-- -----------------------------------------------------------------
-- Step 2 — Insert Trailer category (skip if already exists)
-- -----------------------------------------------------------------

INSERT INTO categories (name, slug, description, is_active, created_at, updated_at)
SELECT
    'Trailer / Non-Passenger',
    'trailer-non-passenger',
    'Permanent trailer, semi-permanent trailer, travel trailer, and non-passenger vehicle plates',
    1,
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE slug = 'trailer-non-passenger'
);

-- Confirm the new row
SELECT id, name, slug, is_active FROM categories WHERE slug = 'trailer-non-passenger';

-- -----------------------------------------------------------------
-- Step 3 — Assign new category to eligible trailer plates
-- -----------------------------------------------------------------

-- Capture new category id into a variable
SET @trailer_cat_id = (SELECT id FROM categories WHERE slug = 'trailer-non-passenger' LIMIT 1);

SELECT @trailer_cat_id AS new_category_id;

-- Assign: Other/Specialty trailer plates → Trailer / Non-Passenger
UPDATE plates
SET
    category_id = @trailer_cat_id,
    updated_at  = NOW()
WHERE category_id = 15
  AND name LIKE '%Trailer%';

-- -----------------------------------------------------------------
-- Step 4 — Verify
-- -----------------------------------------------------------------

-- How many plates now in Trailer / Non-Passenger
SELECT COUNT(*) AS plates_in_trailer_category
FROM plates
WHERE category_id = @trailer_cat_id;

-- Spot-check: first 10 assigned plates
SELECT id, name, category_id, updated_at
FROM plates
WHERE category_id = @trailer_cat_id
ORDER BY id
LIMIT 10;

-- Confirm no Other/Specialty trailers remain
SELECT COUNT(*) AS other_specialty_trailers_remaining
FROM plates
WHERE category_id = 15
  AND name LIKE '%Trailer%';

-- Final category counts
SELECT c.id, c.name, COUNT(p.id) AS plate_count
FROM categories c
LEFT JOIN plates p ON p.category_id = c.id
GROUP BY c.id, c.name
ORDER BY c.id;
