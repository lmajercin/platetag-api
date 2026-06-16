-- America's 250th - Semiquincentennial Badge Setup
-- Run this SQL after running the migrations

-- 1. Insert the badge
INSERT INTO badges (slug, name, description, type, threshold, icon, sort_order, is_active, created_at, updated_at)
VALUES (
    'americas-250th-semiquincentennial',
    'America\'s 250th - Semiquincentennial',
    'Find all plates celebrating the United States Semiquincentennial (250 Years)!',
    'collection',
    NULL,
    'flag',
    0,
    1,
    NOW(),
    NOW()
);

-- 2. Insert the plate associations (using the badge_id from above)
-- Note: Replace @badge_id with the actual ID if running these separately
SET @badge_id = LAST_INSERT_ID();

INSERT INTO badge_plates (badge_id, plate_id) VALUES
(@badge_id, 3034),   -- Delaware
(@badge_id, 10647),  -- Florida
(@badge_id, 3647),   -- Georgia
(@badge_id, 10648),  -- Idaho
(@badge_id, 10649),  -- Indiana
(@badge_id, 10556),  -- Louisiana
(@badge_id, 4392),   -- Massachusetts
(@badge_id, 5788),   -- Michigan
(@badge_id, 7143),   -- New Hampshire
(@badge_id, 56),     -- Pennsylvania
(@badge_id, 1142),   -- Pennsylvania
(@badge_id, 8697),   -- South Carolina
(@badge_id, 10275),  -- Texas
(@badge_id, 10652),  -- Utah
(@badge_id, 9514),   -- Virginia
(@badge_id, 10636);  -- West Virginia

-- 3. Verify the badge was created
SELECT * FROM badges WHERE slug = 'americas-250th-semiquincentennial';

-- 4. Verify all plates are associated
SELECT bp.id, bp.badge_id, bp.plate_id, p.name as plate_name, r.name as region_name
FROM badge_plates bp
JOIN plates p ON bp.plate_id = p.id
JOIN series s ON p.series_id = s.id
JOIN regions r ON s.region_id = r.id
WHERE bp.badge_id = @badge_id
ORDER BY r.name;
