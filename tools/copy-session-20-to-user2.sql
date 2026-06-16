-- ============================================================
-- Copy session_id = 20 (Jean, user_id = 7) → user_id = 2
-- Run on: Production phpMyAdmin → platetag_db1 → SQL tab
-- Prepared: 2026-05-17
-- Creates a new discovery_session for user_id = 2, then
-- copies all 235 rows from session 20 with user_id = 2.
-- ============================================================

-- Step 1: Create the discovery session for user_id = 2
INSERT INTO discovery_sessions (user_id, name, is_default, created_at, updated_at)
VALUES (2, 'Legacy Import — Pre-App Sightings', 0, NOW(), NOW());

SET @new_session_id = LAST_INSERT_ID();

-- Step 2: Copy all rows from session 20, replacing user_id and session_id
INSERT INTO user_discovered_plates
  (session_id, user_id, plate_id, discovered_at, latitude, longitude, location_label, is_first_discovery, notes, created_at, updated_at)
SELECT
  @new_session_id,
  2,
  plate_id,
  discovered_at,
  latitude,
  longitude,
  location_label,
  is_first_discovery,
  notes,
  NOW(),
  NOW()
FROM user_discovered_plates
WHERE session_id = 20;

-- Step 3: Verify the count — should match the source session row count
SELECT
  (SELECT COUNT(*) FROM user_discovered_plates WHERE session_id = 20)      AS source_rows,
  (SELECT COUNT(*) FROM user_discovered_plates WHERE session_id = @new_session_id) AS copied_rows,
  @new_session_id AS new_session_id;
