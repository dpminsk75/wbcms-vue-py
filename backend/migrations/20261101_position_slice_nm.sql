-- Покрывающий индекс для среза матрицы /seo-watch:
--   (company_id, query_phrase(100), slice_stamp, nm_id, position)
--
-- Зачем: матрица /seo-watch сворачивает копии выдачи — одна и та же выдача лежит
-- в таблице копиями по каждой нашей карточке (source_nm_id), и по каждой паре
-- (фраза, заход) набирается ~7 копий одних и тех же позиций. Свёртка
-- (фраза, заход, nm_id) + MIN(position) считается по индексу.
--
-- С idx_position_slice (company_id, query_phrase, slice_stamp) MySQL вынужден
-- читать сами строки (nm_id/position в индексе нет) — замер 2026-11-01:
-- 56 594 строки в приложение (2.18 с) → ~400 МБ RAM → OOM на сервере 1 ГБ.
-- С новым индексом свёртка считается index-only, а из таблицы читаются только
-- ~5 тыс. строк-победителей.
--
-- Идемпотентно: если индекс уже есть — ничего не делаем.

SET @c := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wb_competitor_position'
    AND INDEX_NAME = 'idx_position_slice_nm'
);
SET @s := IF(@c = 0,
  'ALTER TABLE `wb_competitor_position` ADD KEY `idx_position_slice_nm` (`company_id`,`query_phrase`(100),`slice_stamp`,`nm_id`,`position`)',
  'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- Проверка: индекс должен состоять из 5 колонок в этом порядке
SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wb_competitor_position'
  AND INDEX_NAME = 'idx_position_slice_nm'
ORDER BY SEQ_IN_INDEX;
