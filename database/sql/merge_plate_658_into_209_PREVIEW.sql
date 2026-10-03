-- ============================================================
-- PREVIEW: Merge plate 658 discoveries into plate 209
-- Run this first to confirm what will happen before applying.
-- Plate 658 will be deactivated manually in Filament after apply.
-- ============================================================

-- Part A: Records that will be RE-POINTED (658 → 209)
-- These users discovered 658 but do NOT already have 209.
SELECT
    udp.id,
    udp.user_id,
    udp.plate_id        AS current_plate_id,
    209                 AS new_plate_id,
    udp.discovered_at,
    udp.is_first_discovery,
    udp.location_label,
    'will_repoint'      AS action
FROM user_discovered_plates udp
WHERE udp.plate_id = 658
  AND udp.user_id NOT IN (
      SELECT user_id FROM user_discovered_plates WHERE plate_id = 209
  );

-- Part B: Records that will be DELETED (user already has plate 209)
SELECT
    udp.id,
    udp.user_id,
    udp.plate_id,
    udp.discovered_at,
    udp.is_first_discovery,
    udp.location_label,
    'will_delete'       AS action
FROM user_discovered_plates udp
WHERE udp.plate_id = 658
  AND udp.user_id IN (
      SELECT user_id FROM user_discovered_plates WHERE plate_id = 209
  );

-- Part C: Count summary
SELECT
    (SELECT COUNT(*) FROM user_discovered_plates WHERE plate_id = 658
       AND user_id NOT IN (SELECT user_id FROM user_discovered_plates WHERE plate_id = 209)
    ) AS records_to_repoint,
    (SELECT COUNT(*) FROM user_discovered_plates WHERE plate_id = 658
       AND user_id IN (SELECT user_id FROM user_discovered_plates WHERE plate_id = 209)
    ) AS records_to_delete,
    (SELECT COUNT(*) FROM user_discovered_plates WHERE plate_id = 658) AS total_658_records,
    (SELECT COUNT(*) FROM user_discovered_plates WHERE plate_id = 209) AS current_209_records;
