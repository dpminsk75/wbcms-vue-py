-- Добавление колонок в журнал воркера разбора фраз (wb_phrase_miner_log).
--
-- Случай: миграция 20261028_phrase_miner.sql была применена в ранней версии,
-- где у журнала не было колонок action/company_id/source_nm_id/queue_id/priority.
-- CREATE TABLE IF NOT EXISTS не дополняет уже созданную таблицу — нужен ALTER.
--
-- Применять ДО рестарта wbcms-py.
--
-- Скрипт ИДЕМПОТЕНТЕН: каждая колонка/индекс добавляется только если её ещё нет
-- (проверка по information_schema). Можно запускать повторно.
--
-- Проверить после выполнения:
--   SHOW COLUMNS FROM wb_phrase_miner_log;

-- 1. Колонки
SET @db := DATABASE();

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD COLUMN `action` VARCHAR(32) NULL COMMENT ''refill|start|done|error|skip|rest|manual'' AFTER `level`',
  'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND COLUMN_NAME = 'action');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD COLUMN `company_id` INT NULL COMMENT ''компания карточки'' AFTER `msg`',
  'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND COLUMN_NAME = 'company_id');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD COLUMN `source_nm_id` INT NULL COMMENT ''наш nmID'' AFTER `company_id`',
  'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND COLUMN_NAME = 'source_nm_id');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD COLUMN `queue_id` INT NULL COMMENT ''строка очереди'' AFTER `competitor_nm_id`',
  'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND COLUMN_NAME = 'queue_id');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD COLUMN `priority` TINYINT NULL COMMENT ''1=из SEO-мониторинга, 2=общий поток'' AFTER `queue_id`',
  'SELECT 1')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND COLUMN_NAME = 'priority');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- 2. Индексы
SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD KEY `idx_pml_ts` (`ts`)',
  'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND INDEX_NAME = 'idx_pml_ts');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD KEY `idx_pml_comp` (`competitor_nm_id`)',
  'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND INDEX_NAME = 'idx_pml_comp');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @s := (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE `wb_phrase_miner_log` ADD KEY `idx_pml_company` (`company_id`,`id`)',
  'SELECT 1')
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'wb_phrase_miner_log' AND INDEX_NAME = 'idx_pml_company');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;
