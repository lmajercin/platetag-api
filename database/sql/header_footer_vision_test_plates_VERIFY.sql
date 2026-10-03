-- =============================================================
-- VERIFY — Header/Footer Vision tagger — test plates (read-only)
-- Database: platetag_db1
-- Tool:     phpMyAdmin — ONE paste, ONE Go
-- Local WAMP only.
--
-- Run AFTER: php artisan tagger:header-footer-series {series} --plate={id}
-- Test IDs: 7324, 8441, 9661, 8976, 8778 (8110 excluded)
-- =============================================================

USE platetag_db1;

SELECT
    p.id,
    p.name,
    p.header_override,
    p.footer_override,
    p.updates_complete,
    p.updated_at
FROM plates p
WHERE p.id IN (7324, 8441, 9661, 8976, 8778)
ORDER BY p.id;

-- Expected results (after successful Vision run):
-- 7324  header=NULL   footer includes Pearl Harbor Survivor + New Mexico USA (| separated)
-- 8441  header=AIR MEDAL   footer=South Carolina
-- 9661  header=West Virginia   footer=World War II Veteran
-- 8976  header=Vermont   footer=United States Veteran
-- 8778  header=South Dakota   footer=NULL
