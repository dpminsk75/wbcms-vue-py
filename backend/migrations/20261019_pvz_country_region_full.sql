-- DISTINCT регионов: loose scan (Using index for group-by) невозможен по
-- префиксной колонке, поэтому индекс пересоздаём полноразмерным.
-- Длина с запасом влезает в лимит ключа (country CHAR(2) + VARCHAR(255) utf8mb4).
ALTER TABLE `pvz_all`
  DROP INDEX `idx_pvz_country_region`,
  ADD INDEX `idx_pvz_country_region` (`country`, `region_norm`);
