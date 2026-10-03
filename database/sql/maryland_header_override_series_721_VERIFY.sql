-- =============================================================
-- VERIFY — Maryland header_override series 721 (read-only)
-- Database: platetag_db1
-- Run anytime to check current state. No changes made.
-- =============================================================

USE platetag_db1;

-- 1) Series identity
SELECT
    s.id          AS series_id,
    s.name        AS series_name,
    r.name        AS region_name
FROM series s
LEFT JOIN regions r ON r.id = s.region_id
WHERE s.id = 721;

-- 2) Header breakdown (compare to dry-run: 978 null, 21 non-null, 999 total)
SELECT
    CASE
        WHEN header_override IS NULL THEN '(NULL)'
        ELSE header_override
    END AS header_override,
    COUNT(*) AS plate_count
FROM plates
WHERE series_id = 721
GROUP BY header_override
ORDER BY plate_count DESC, header_override;

SELECT COUNT(*) AS total_in_series FROM plates WHERE series_id = 721;
SELECT COUNT(*) AS null_header FROM plates WHERE series_id = 721 AND header_override IS NULL;
SELECT COUNT(*) AS maryland_header FROM plates WHERE series_id = 721 AND header_override = 'Maryland';

-- 3) If APPLY had committed: null_header = 0, maryland_header = 999 (or 978+existing Maryland)
-- If nothing saved: null_header should still be 978

-- 4) Sample rows still NULL (proves update did not stick)
SELECT id, name, header_override, footer_override, updated_at
FROM plates
WHERE series_id = 721 AND header_override IS NULL
ORDER BY id
LIMIT 10;

-- 5) Rows that already had a header (should be unchanged)
SELECT id, name, header_override, footer_override, updated_at
FROM plates
WHERE series_id = 721 AND header_override IS NOT NULL
ORDER BY id
LIMIT 10;

-- 6) Spot-check: other columns on a few NULL-header rows (UPDATE only touched header_override + updated_at)
SELECT
    id,
    name,
    slug,
    series_id,
    category_id,
    vehicle_class,
    header_override,
    footer_override,
    LEFT(detail, 80) AS detail_preview,
    updated_at
FROM plates
WHERE series_id = 721
ORDER BY id
LIMIT 5;
