-- Фаза 2 WB-токенов: хранение decode+ping для баннера "токен заканчивается".
-- Активный токен = строка is_active=1 (совпадает с companies.api_key).
-- Черновики из формы (проверка до сохранения) пишутся с is_active=0.
CREATE TABLE IF NOT EXISTS `company_wb_tokens` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `wb_token_id` VARCHAR(36) NULL COMMENT 'JWT id (UUIDv4)',
  `sid` VARCHAR(36) NULL COMMENT 'JWT sid продавца',
  `token_sha256` CHAR(64) NOT NULL COMMENT 'SHA256 полного токена, сырой токен тут не храним',
  `exp_at` DATETIME NULL COMMENT 'JWT exp UTC',
  `days_left` INT NULL COMMENT 'на момент last_check_at',
  `s_mask` INT UNSIGNED NULL COMMENT 'битмаска s',
  `is_test` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'бит 0',
  `is_readonly` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'бит 30',
  `categories` JSON NULL COMMENT 'ключи категорий из s: content,analytics,prices,marketplace,statistics,promotion,feedbacks,recommendations,chat,supplies,returns,documents,finance,users',
  `ping` JSON NULL COMMENT '{category:{http,ok,ms}} последний живой прогон',
  `last_check_at` DATETIME NULL,
  `last_error` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_wb_tokens_company_hash` (`company_id`,`token_sha256`),
  KEY `idx_wb_tokens_company_active` (`company_id`,`is_active`),
  KEY `idx_wb_tokens_exp` (`exp_at`),
  CONSTRAINT `fk_wb_tokens_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
