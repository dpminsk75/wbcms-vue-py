-- Индекс под сводку «наша карточка» — 2026-10-22.
--
-- Зачем: GET /api/competitors/positions/our_card ищет строки наблюдений нашей
-- карточки (nm_id) в пределах компании и периода. Без составного индекса MySQL
-- выбирал idx_nm_id либо idx_position_company и сортировал выборку
-- ORDER BY query_phrase (VARCHAR(500)) — файловой сортировкой.
--
-- MySQL 8, InnoDB. Повторный apply не мешает: если индекс уже есть — пропустите.

ALTER TABLE `wb_competitor_position`
  ADD KEY `idx_position_company_nm` (`company_id`, `nm_id`, `collected_at`);

-- Проверка после миграции:
-- SHOW INDEX FROM wb_competitor_position WHERE Key_name='idx_position_company_nm';
