-- Ext-токены (§10 md): долгоживущий Bearer для расширения.
-- Сырой токен показываем один раз при выдаче, храним только sha256 + префикс для списка.
CREATE TABLE IF NOT EXISTS `ext_tokens` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT 'на сотрудника/машину, отзыв по одному',
  `token_sha256` CHAR(64) NOT NULL COMMENT 'SHA256 сырого токена, сырой тут не храним',
  `token_prefix` VARCHAR(12) NOT NULL DEFAULT '' COMMENT 'первые символы для опознания в списке',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `last_used_at` DATETIME NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ext_tokens_hash` (`token_sha256`),
  KEY `idx_ext_tokens_company` (`company_id`,`is_active`),
  CONSTRAINT `fk_ext_tokens_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ext_tokens_user` FOREIGN KEY (`created_by`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
