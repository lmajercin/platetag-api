-- =============================================================
-- REPORT — plate counts per series (ranked high → low)
-- Database: platetag_db1
-- Export:   phpMyAdmin → run query → Export results as CSV
-- Or run:   php tools/report_series_plate_counts.php
-- =============================================================

USE platetag_db1;

SELECT
    p.series_id,
    s.name AS series_name,
    COUNT(*) AS plate_count
FROM plates p
INNER JOIN series s ON s.id = p.series_id
GROUP BY p.series_id, s.name
ORDER BY plate_count DESC, p.series_id ASC;
