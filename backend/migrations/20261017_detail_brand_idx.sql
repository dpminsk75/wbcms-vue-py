-- DISTINCT brand_name для фильтра ТОП продаж (без него — фулскан detail_by_period).
-- Loose index scan по (company_id, brand_name): MySQL прыгает по префиксу.
CREATE INDEX `idx_detail_brand` ON `detail_by_period` (`company_id`, `brand_name`);
