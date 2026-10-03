-- ALPCA Best Plate Award milestone badges (5 and 10 unique winner plates).
-- Safe to re-run: uses slug uniqueness.

INSERT INTO badges (slug, name, description, type, threshold, icon, sort_order, is_active, created_at, updated_at)
SELECT 'alpca-collector-5', 'ALPCA Collector', 'Discover 5 unique ALPCA Best Plate Award winners.', 'alpca', 5, 'Medal', 400, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM badges WHERE slug = 'alpca-collector-5');

INSERT INTO badges (slug, name, description, type, threshold, icon, sort_order, is_active, created_at, updated_at)
SELECT 'alpca-master-10', 'ALPCA Master', 'Discover 10 unique ALPCA Best Plate Award winners.', 'alpca', 10, 'Trophy', 410, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM badges WHERE slug = 'alpca-master-10');
