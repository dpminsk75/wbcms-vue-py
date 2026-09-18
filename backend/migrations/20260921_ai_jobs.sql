-- Вариант B (AI-jobs): очередь фоновых AI-задач с опросом статуса.
-- Job = один запуск (analyze-all / batch), item = одна запись (конкурент/nmID).
CREATE TABLE IF NOT EXISTS `ai_job` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `company_id` INT NULL,
  `kind` VARCHAR(50) NOT NULL COMMENT 'competitor_analyze_all | seo_process_batch ...',
  `nm_id` INT NULL,
  `status` ENUM('queued','running','done','error','interrupted') NOT NULL DEFAULT 'queued',
  `total` INT NOT NULL DEFAULT '0',
  `done` INT NOT NULL DEFAULT '0',
  `error` VARCHAR(500) NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ai_job_company` (`company_id`),
  KEY `idx_ai_job_status` (`status`),
  CONSTRAINT `fk_ai_job_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_ai_job_user` FOREIGN KEY (`created_by`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_job_item` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `job_id` INT NOT NULL,
  `label` VARCHAR(255) NULL COMMENT 'подпись для лоадера (nmID конкурента...)',
  `ref_id` INT NULL COMMENT 'id записи-источника (wb_competitor_analysis.id)',
  `status` ENUM('pending','processing','done','error') NOT NULL DEFAULT 'pending',
  `result` JSON NULL,
  `error` VARCHAR(500) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ai_job_item_job` (`job_id`),
  CONSTRAINT `fk_ai_job_item_job` FOREIGN KEY (`job_id`) REFERENCES `ai_job` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
