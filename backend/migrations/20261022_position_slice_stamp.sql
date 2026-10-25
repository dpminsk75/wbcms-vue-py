-- Разрез наблюдений выдачи по ЗАХОДАМ, а не по дням — 2026-10-22.
--
-- Зачем: в БД срез был суточным (collected_at DATE), поэтому несколько заходов
-- в поиск WB за один день склеивались в одну строку — в отчёте «Выдача WB» это
-- выглядело как «170 товаров» в одной выдаче (100 из одного захода + 70 из другого).
--
-- slice_stamp — метка захода (20261022_131023 = дата_время сбора). Расширение
-- уже присылает search_stamp (один на все 4 канала одного поиска).
--
-- UNIQUE-ключ расширяем на slice_stamp: '' (пусто) вместо NULL, чтобы старые
-- строки и пересборка без метки по-прежнему склеивались как раньше.
--
-- MySQL 8, InnoDB, utf8mb4.

ALTER TABLE `wb_competitor_position`
  DROP INDEX `uq_position_company_date`,
  ADD COLUMN `slice_stamp` VARCHAR(20) NOT NULL DEFAULT ''
    COMMENT 'метка захода в поиск WB: 20261022_131023 (день_время)' AFTER `collected_at`,
  ADD UNIQUE KEY `uq_position_company_date`
    (`company_id`, `source_nm_id`, `query_phrase`(200), `nm_id`, `collected_at`, `slice_stamp`),
  ADD KEY `idx_position_slice` (`company_id`, `query_phrase`(100), `slice_stamp`);

-- Проверка после миграции:
-- SHOW INDEX FROM wb_competitor_position WHERE Key_name IN ('uq_position_company_date','idx_position_slice');
-- SHOW COLUMNS FROM wb_competitor_position LIKE 'slice_stamp';
