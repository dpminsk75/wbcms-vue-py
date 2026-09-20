-- Пресеты фильтра категорий для расширения (§10, уточнение 19.09): несколько именованных
-- вариантов на компанию (xsubject id через «;»). Пусто в таблице = фолбэк «Книги и журналы»
-- отдаёт код, заводить руками не обязательно.
CREATE TABLE IF NOT EXISTS `ext_category_filters` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `name` VARCHAR(100) NOT NULL COMMENT 'Книги и журналы, Канцтовары...',
  `subjects` VARCHAR(500) NOT NULL DEFAULT '' COMMENT 'id subject через ; — в &xsubject= выдачи WB',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ext_catfilter_company_name` (`company_id`,`name`),
  KEY `idx_ext_catfilter_company` (`company_id`,`is_active`),
  CONSTRAINT `fk_ext_catfilter_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ext_catfilter_user` FOREIGN KEY (`created_by`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
