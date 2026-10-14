-- DISTINCT регионов для каскада фильтров (sales-analysis) и parent_okrug (geo_sales).
-- Loose index scan по префиксу (country, region_norm): без temp/filesort.
CREATE INDEX `idx_pvz_country_region` ON `pvz_all` (`country`, `region_norm`(100));
