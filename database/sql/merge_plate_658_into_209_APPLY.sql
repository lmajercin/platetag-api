-- ============================================================
-- APPLY: Merge plate 658 discoveries into plate 209
-- Run merge_plate_658_into_209_PREVIEW.sql first and confirm
-- the counts look correct before running this.
--
-- After this script completes:
--   - All unique 658 discoveries are re-pointed to plate 209
--   - Duplicate records (users who had both) are removed
--   - No user loses a discovery they legitimately had
--   - Manually deactivate plate 658 in Filament after verifying
-- ============================================================

-- Step 1: Re-point unique discoveries (658 → 209)
-- Only affects users who do NOT already have plate 209.
UPDATE user_discovered_plates
SET plate_id = 209
WHERE plate_id = 658
  AND user_id NOT IN (
      SELECT user_id FROM (
          SELECT user_id FROM user_discovered_plates WHERE plate_id = 209
      ) AS already_have_209
  );

-- Step 2: Delete remaining plate 658 records
-- These are users who already had plate 209 — their 658 record is now a true duplicate.
DELETE FROM user_discovered_plates
WHERE plate_id = 658;

-- Step 3: Verify — should return 0 rows remaining for plate 658
--         and an increased count for plate 209.
SELECT
    plate_id,
    COUNT(*) AS discovery_count
FROM user_discovered_plates
WHERE plate_id IN (209, 658)
GROUP BY plate_id;
