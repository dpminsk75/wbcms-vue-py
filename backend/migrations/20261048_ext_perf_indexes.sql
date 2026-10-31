-- Индексы для ext-коллектора: разгрузка БД на поллер-пути.
--
-- 1) wb_sr_report_item_phrases — индекс с ВЕДУЩИМ nmID.
--    Отчётные фразы (_next_report_phrase / _report_counts) читаются как
--    `WHERE nmID=:n AND orders>0 GROUP BY phrase ORDER BY SUM(orders)` — без
--    ведущего nmID это фулл-скан всей таблицы (~300k строк) + temporary +
--    filesort НА КАЖДЫЙ опрос расширения (EXPLAIN: type=index, rows=193809,
--    Using temporary; Using filesort).
--    С индексом (nmID, orders) — range по срезу карточки.
--
-- 2) wb_card_badges_history — nm_id ведущей колонкой.
--    _badge_history_write ищет последний снимок набора бейджей по nm_id;
--    при индексе (company_id, nm_id, at) это фулл-скан таблицы истории
--    на каждый /result (nm_id — вторая колонка, плюс OR по company_id).
--    Новый индекс (nm_id, company_id, at) покрывает и запрос по карточке,
--    и выборку «своя компания + компания 0».
--
-- MySQL 8, InnoDB. ADD/DROP KEY — INPLACE, без пересборки данных.
-- Требуется существующая wb_card_badges_history (миграция 20261038).

ALTER TABLE `wb_sr_report_item_phrases`
  ADD KEY `idx_phrase_nm_orders` (`nmID`,`orders`);

ALTER TABLE `wb_card_badges_history`
  DROP KEY `idx_bh_nm`,
  ADD KEY `idx_bh_nm_company` (`nm_id`,`company_id`,`at`);

-- Проверка после применения:
-- SHOW INDEX FROM wb_sr_report_item_phrases WHERE Key_name='idx_phrase_nm_orders';
-- SHOW INDEX FROM wb_card_badges_history WHERE Key_name='idx_bh_nm_company';
-- EXPLAIN SELECT phrase, MAX(orders) FROM wb_sr_report_item_phrases
--   WHERE nmID=<NM> AND orders>0 GROUP BY phrase ORDER BY SUM(orders) DESC LIMIT 20;
