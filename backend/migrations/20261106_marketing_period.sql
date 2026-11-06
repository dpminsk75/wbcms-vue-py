-- Период размещения в документах маркетинговых расходов.
--
-- Зачем: расход «растягивается» по дням периода. При формировании отчёта
-- по товару в окно отчёта попадает только та часть суммы позиции, которая
-- приходится на дни пересечения периода размещения с окном отчёта.
--
-- document_date  — дата документа (акта). Остаётся как есть: по ней фильтруются
--                 документы в списке, и она не меняется при добавлении периода.
-- period_start   — начало размещения (расход «работает» с этой даты).
-- period_end     — окончание размещения.
--
-- Бэкфилл: у существующих документов период = дата документа (разовое
-- размещение в один день). «Растягивание» для них ничего не меняет —
-- суммы в отчётах не поедут.
--
-- Идемпотентность: ALTER выполняется один раз (MySQL 8 не поддерживает
-- ADD COLUMN IF NOT EXISTS), повторный прогон упадёт — применять один раз.

ALTER TABLE `marketing_expense_documents`
  ADD COLUMN `period_start` DATE NULL AFTER `document_date`,
  ADD COLUMN `period_end` DATE NULL AFTER `period_start`,
  ADD KEY `idx_med_company_period` (`company_id`, `period_start`, `period_end`);

UPDATE `marketing_expense_documents`
   SET `period_start` = `document_date`,
       `period_end`   = `document_date`
 WHERE `period_start` IS NULL;

ALTER TABLE `marketing_expense_documents`
  MODIFY `period_start` DATE NOT NULL,
  MODIFY `period_end` DATE NOT NULL;
