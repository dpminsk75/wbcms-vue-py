-- WB: налоговые настройки компании + ручной маркетинг (площадки, документы, позиции).
--
-- company_tax_settings      — версии настроек налога компании (valid_from/valid_to).
--                            Ставка НДС здесь НЕ хранится: НДС заложен в товаре и лежит
--                            в wbcards_nds (nmID + load_date -> nds). Здесь только режим
--                            (none/income/profit/osno), ставка основного налога и аудит.
-- marketing_channels       — справочник площадок (блогеры/сайты/Telegram/…).
-- marketing_expense_documents — документ маркетингового расхода (акт/интеграция/договор).
-- marketing_expense_lines  — позиции документа: всегда привязаны к nmID (SKU).
--
-- Идемпотентно: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS `company_tax_settings` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `valid_from` DATE NOT NULL COMMENT 'с какого дня действует версия',
  `valid_to` DATE NULL COMMENT 'до какого дня действует (NULL = бессрочно)',
  `mode` VARCHAR(32) NOT NULL DEFAULT 'income' COMMENT 'none|income|profit|osno',
  `main_rate` DECIMAL(6,4) NOT NULL DEFAULT 0 COMMENT 'ставка УСН/основного налога, %',
  `vat_source` VARCHAR(16) NOT NULL DEFAULT 'cards' COMMENT 'cards (wbcards_nds) | none',
  `profit_rate` DECIMAL(6,4) NULL COMMENT 'налог на прибыль/НДФЛ, % (только osno)',
  `reason` VARCHAR(500) NULL COMMENT 'причина изменения — попадает в историю',
  `created_by` INT NULL,
  `updated_by` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cts_company_from` (`company_id`, `valid_from`),
  KEY `idx_cts_company_range` (`company_id`, `valid_from`, `valid_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `marketing_channels` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `name` VARCHAR(255) NOT NULL COMMENT 'название площадки',
  `channel_type` VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT 'blogger|site|telegram|youtube|instagram|other',
  `website_or_contact` VARCHAR(512) NULL COMMENT 'ссылка, @handle, почта',
  `contact_name` VARCHAR(255) NULL,
  `contact_phone` VARCHAR(64) NULL,
  `inn` VARCHAR(32) NULL,
  `comment` VARCHAR(1000) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by` INT NULL,
  `updated_by` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_mc_company_name` (`company_id`, `name`),
  KEY `idx_mc_company` (`company_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `marketing_expense_documents` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `document_key` VARCHAR(64) NOT NULL COMMENT 'ключ документа (для Excel и импорта)',
  `document_date` DATE NOT NULL,
  `channel_id` BIGINT UNSIGNED NULL COMMENT 'площадка',
  `doc_type` VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT 'blogger_post|giveaway|self_buyout|review_cashback|other',
  `title` VARCHAR(255) NOT NULL DEFAULT '',
  `comment` VARCHAR(1000) NULL,
  `total_amount` DECIMAL(14,2) NOT NULL DEFAULT 0 COMMENT 'итог = сумма позиций',
  `created_by` INT NULL,
  `updated_by` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_med_company_key` (`company_id`, `document_key`),
  KEY `idx_med_company_date` (`company_id`, `document_date`),
  KEY `idx_med_channel` (`channel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `marketing_expense_lines` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `document_id` BIGINT UNSIGNED NOT NULL,
  `nm_id` INT NOT NULL COMMENT 'SKU WB — расход всегда привязан к товару',
  `vendor_code` VARCHAR(255) NULL,
  `product_title` VARCHAR(255) NULL,
  `amount` DECIMAL(14,2) NOT NULL,
  `comment` VARCHAR(500) NULL,
  `created_by` INT NULL,
  `updated_by` INT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mel_document` (`document_id`),
  KEY `idx_mel_company_nm` (`company_id`, `nm_id`),
  KEY `idx_mel_company_date` (`company_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
