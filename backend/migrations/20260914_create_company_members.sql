CREATE TABLE IF NOT EXISTS `company_members` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `role` ENUM('owner','admin','member','viewer') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'member',
  `status` ENUM('active','blocked','invited') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `invited_by` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_members_company_user` (`company_id`,`user_id`),
  KEY `idx_company_members_user` (`user_id`),
  KEY `idx_company_members_company_status` (`company_id`,`status`),
  KEY `fk_company_members_invited_by` (`invited_by`),
  CONSTRAINT `fk_company_members_company`
    FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_company_members_invited_by`
    FOREIGN KEY (`invited_by`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_company_members_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
