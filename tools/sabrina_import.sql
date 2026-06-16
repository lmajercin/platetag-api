-- =============================================================
-- Sabrina Import — Legacy Discoveries for user_id = 10
-- 23 discoveries from March 27 – April 2, 2026
-- Run this in cPanel phpMyAdmin on the production database
-- =============================================================

START TRANSACTION;

-- Step 1: Create a discovery session for Sabrina's legacy imports
INSERT INTO discovery_sessions (user_id, name, is_default, created_at, updated_at)
VALUES (10, 'Legacy Import — Mar/Apr 2026', 0, NOW(), NOW());

-- Step 2: Capture the new session ID
SET @session_id = LAST_INSERT_ID();

-- Step 3: Insert all 23 legacy discoveries
INSERT INTO user_discovered_plates
    (session_id, user_id, plate_id, discovered_at, latitude, longitude, location_label, is_first_discovery, created_at, updated_at)
VALUES
    (@session_id, 10, 2764, '2026-03-27 08:09:00',  33.7739072,  -116.5409928, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 2651, '2026-03-27 08:10:00',  33.7739443,  -116.5409695, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 2662, '2026-03-27 08:10:00',  33.7739374,  -116.5409659, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 2759, '2026-03-27 08:11:00',  33.7739274,  -116.5409670, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 1430, '2026-03-27 09:19:00',  33.8090370,  -116.5454271, NULL, 1, NOW(), NOW()),
    (@session_id, 10,  205, '2026-03-27 09:22:00',  33.8210160,  -116.5456486, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 2762, '2026-03-27 09:42:00',  33.8222320,  -116.5450159, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 2306, '2026-03-27 12:42:00',  33.8016395,  -116.5281919, NULL, 1, NOW(), NOW()),
    (@session_id, 10,   34, '2026-03-27 12:43:00',  33.7943062,  -116.5360907, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 8781, '2026-03-30 13:10:00',  33.8014181,  -116.5278265, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 8938, '2026-03-30 13:11:00',  33.8014873,  -116.5278278, NULL, 1, NOW(), NOW()),
    (@session_id, 10,  420, '2026-04-02 16:07:00',  35.5498446,  -115.4158103, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 4000, '2026-04-02 16:10:00',  35.5932635,  -115.3971457, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 7415, '2026-04-02 16:15:00',  35.6570057,  -115.3809894, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 5426, '2026-04-02 16:17:00',  35.6867647,  -115.3752925, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 1677, '2026-04-02 16:20:00',  35.7500763,  -115.3506925, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 5750, '2026-04-02 16:24:00',  35.8045098,  -115.3109058, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 1449, '2026-04-02 16:34:00',  35.9644491,  -115.1815908, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 7361, '2026-04-02 16:36:00',  36.0008089,  -115.1804255, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 10201,'2026-04-02 16:39:00',  36.0418256,  -115.1802660, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 7432, '2026-04-02 16:40:00',  36.0737119,  -115.1808373, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 7427, '2026-04-02 16:42:00',  36.0856789,  -115.1807062, NULL, 1, NOW(), NOW()),
    (@session_id, 10, 7395, '2026-04-02 16:43:00',  36.0946576,  -115.1806046, NULL, 1, NOW(), NOW());

-- Step 4: Verify before committing
SELECT
    'discoveries inserted' AS check_label,
    COUNT(*) AS row_count
FROM user_discovered_plates
WHERE user_id = 10;

SELECT
    'session created' AS check_label,
    id,
    name
FROM discovery_sessions
WHERE user_id = 10
ORDER BY id DESC
LIMIT 1;

COMMIT;
