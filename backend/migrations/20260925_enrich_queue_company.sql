-- Скоуп очереди обогащения по компании (§10 md): seed/next/status/reset фильтруют по company_id.
-- Старые строки (company_id IS NULL) видит только seed-пересоздание; захват next проставляет компанию.
ALTER TABLE `wb_enrich_queue`
  ADD COLUMN `company_id` INT NULL COMMENT 'скоуп §10: кто seed`ил' AFTER `nm_id`,
  ADD KEY `idx_enrich_company_status` (`company_id`,`status`);
