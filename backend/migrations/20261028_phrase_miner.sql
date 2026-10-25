-- Фоновый разбор фраз карточек конкурентов («phrase miner», план 2026-10-25).
-- Применять ДО рестарта wbcms-py. Данные не удаляются.
--
--   wb_phrase_miner_queue — очередь работ: одна строка = пара (наша карточка, конкурент).
--                           priority: 1 = свежесобранные из SEO-мониторинга (watch, 24 ч),
--                                     2 = общий поток (неразобранные пары, свежие → старые).
--   wb_phrase_miner_log   — журнал работы воркера (append-only, хвост чистим до 10 000 строк).
--
-- ВАЖНО: ALTER ... ADD COLUMN в MySQL 8 не идемпотентен — повторный прогон упадёт
-- на "Duplicate column". Проверить перед повторным запуском:
--   SHOW TABLES LIKE 'wb_phrase_miner_queue';
--
-- ЕСЛИ ЭТОТ ФАЙЛ УЖЕ ПРИМЕНЯЛСЯ в ранней версии (без колонок action/company_id/
-- source_nm_id/queue_id/priority в wb_phrase_miner_log) — прогони
-- 20261029_phrase_miner_log_columns.sql (идемпотентный ALTER).

CREATE TABLE IF NOT EXISTS `wb_phrase_miner_queue` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `company_id` INT NOT NULL COMMENT 'компания карточки (владелец source_nm_id)',
  `source_nm_id` INT NOT NULL COMMENT 'наш nmID',
  `competitor_nm_id` INT NOT NULL COMMENT 'nmID конкурента',
  `content_hash` CHAR(32) NOT NULL COMMENT 'md5 описания конкурента на момент постановки',
  `priority` TINYINT NOT NULL DEFAULT 2 COMMENT '1=из SEO-мониторинга, 2=общий поток',
  `status` ENUM('pending','processing','done','error') NOT NULL DEFAULT 'pending',
  `attempts` INT NOT NULL DEFAULT 0,
  `last_error` VARCHAR(500) NULL,
  `error_until` DATETIME NULL COMMENT 'после N неудач не трогаем до этого момента',
  `model` VARCHAR(100) NULL,
  `phrases_cnt` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `processed_at` DATETIME NULL,
  UNIQUE KEY `uq_pmq` (`source_nm_id`,`competitor_nm_id`,`content_hash`),
  KEY `idx_pmq_pick` (`status`,`priority`,`id`),
  KEY `idx_pmq_comp` (`competitor_nm_id`,`content_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_phrase_miner_log` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `ts` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `level` ENUM('info','warn','error') NOT NULL DEFAULT 'info',
  `action` VARCHAR(32) NULL COMMENT 'refill|start|done|error|skip|rest|manual',
  `msg` VARCHAR(500) NOT NULL,
  `company_id` INT NULL COMMENT 'компания карточки',
  `source_nm_id` INT NULL COMMENT 'наш nmID',
  `competitor_nm_id` INT NULL,
  `queue_id` INT NULL COMMENT 'строка очереди',
  `priority` TINYINT NULL COMMENT '1=из SEO-мониторинга, 2=общий поток',
  `phrases_cnt` INT NULL,
  `model` VARCHAR(100) NULL,
  `ms` INT NULL COMMENT 'длительность LLM-вызова, мс',
  KEY `idx_pml_ts` (`ts`),
  KEY `idx_pml_comp` (`competitor_nm_id`),
  KEY `idx_pml_company` (`company_id`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
