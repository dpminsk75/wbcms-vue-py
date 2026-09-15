CREATE TABLE IF NOT EXISTS `auth_invite_tokens` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `token_ciphertext` TEXT NOT NULL,
  `token_type` ENUM('company', 'user') NOT NULL,
  `company_id` INT NULL,
  `target_user_id` INT NULL,
  `target_email` VARCHAR(255) NULL,
  `role` ENUM('admin', 'member') NULL,
  `company_name` VARCHAR(255) NULL,
  `expires_at` DATETIME NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `used_at` TIMESTAMP NULL,
  `created_by` INT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_auth_invite_tokens_active` (`token_type`, `company_id`, `expires_at`, `used_at`),
  KEY `idx_auth_invite_tokens_created_by` (`created_by`),
  CONSTRAINT `fk_auth_invite_tokens_company`
    FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_auth_invite_tokens_created_by`
    FOREIGN KEY (`created_by`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `auth_item` (`name`, `type`, `description`, `created_at`, `updated_at`)
VALUES ('global_admin', 1, 'Global administrator', UNIX_TIMESTAMP(), UNIX_TIMESTAMP());

INSERT IGNORE INTO `auth_assignment` (`item_name`, `user_id`, `created_at`)
VALUES ('global_admin', '100', UNIX_TIMESTAMP());
