-- Нормализованные названия для группировки в отчетах (см. backend/services/geo_names.py).
-- DaData пишет регион/город в двух форматах («Московская область»/«Московская обл»,
-- «Москва»/«г Москва»); нормы считает scripts/pvz_norm.py, отчеты группируют готовое.
ALTER TABLE `pvz_all`
  ADD COLUMN `region_norm` VARCHAR(255) NULL COMMENT 'нормализованный region (группировки)',
  ADD COLUMN `city_norm` VARCHAR(255) NULL COMMENT 'нормализованный city (группировки)';
CREATE INDEX `idx_pvz_region_norm` ON `pvz_all` (`region_norm`(100));
CREATE INDEX `idx_pvz_city_norm` ON `pvz_all` (`city_norm`(100));
