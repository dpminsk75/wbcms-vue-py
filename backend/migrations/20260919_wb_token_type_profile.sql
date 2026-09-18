-- Фаза 3 WB-токенов: тип токена (acc/for/t) + профиль продавца (common-api).
-- Зависит от 20260918_company_wb_tokens.sql.
ALTER TABLE `company_wb_tokens`
  ADD COLUMN `token_type` VARCHAR(16) NULL COMMENT 'basic|test|personal|service|unknown по acc/for/t' AFTER `is_readonly`;

CREATE TABLE IF NOT EXISTS `company_wb_profile` (
  `company_id` INT NOT NULL,
  `sid` VARCHAR(36) NULL COMMENT 'сверка с JWT sid из company_wb_tokens',
  `seller_name` VARCHAR(255) NULL,
  `seller_info` JSON NULL COMMENT 'сырой /api/v1/seller-info',
  `rating` DECIMAL(3,2) NULL,
  `reviews_count` INT NULL,
  `has_jam` TINYINT(1) NULL COMMENT 'NULL = не проверяли; 0 = пустой 200 (Джема не было)',
  `jam` JSON NULL COMMENT 'сырой /api/common/v1/subscriptions',
  `tariffs` JSON NULL COMMENT 'сырой /api/common/v1/tariff-constructor/options',
  `fetched_at` DATETIME NULL,
  `last_error` VARCHAR(500) NULL COMMENT 'метод:http для неуспешных (429/403)',
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`),
  CONSTRAINT `fk_wb_profile_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
