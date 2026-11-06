-- Акции WB: календарь, номенклатура акции, пометки пользователя.
-- Схема переносится дампом БД целиком; миграция локальная, в git не коммитится.
--
-- wb_promotions            — кэш календаря (GET /api/v1/calendar/promotions + /details)
-- wb_promotion_products    — кэш номенклатуры акции (GET /api/v1/calendar/promotions/nomenclatures)
-- wb_promotion_decisions   — пометки пользователя (снял рекомендацию / добавил товар)

CREATE TABLE IF NOT EXISTS `wb_promotions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `promo_id` INT NOT NULL COMMENT 'id акции в WB',
  `name` VARCHAR(255) NOT NULL DEFAULT '',
  `promo_type` VARCHAR(16) NOT NULL DEFAULT '' COMMENT 'regular | auto',
  `start_dt` DATETIME NULL,
  `end_dt` DATETIME NULL,
  `description` TEXT NULL,
  `advantages` TEXT NULL COMMENT 'JSON: список преимуществ акции',
  `in_promo_leftovers` INT NULL COMMENT 'товаров в акции (с остатком)',
  `in_promo_total` INT NULL COMMENT 'всего товаров в акции',
  `not_in_promo_leftovers` INT NULL,
  `not_in_promo_total` INT NULL,
  `participation_percentage` INT NULL,
  `exception_products_count` INT NULL,
  `ranging` TEXT NULL COMMENT 'JSON: шкала скидок',
  `fetched_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_promo` (`company_id`, `promo_id`),
  KEY `idx_promo_range` (`company_id`, `start_dt`, `end_dt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_promotion_products` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `promo_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `in_action` TINYINT NOT NULL DEFAULT 0,
  `price` DECIMAL(12,2) NULL COMMENT 'текущая розничная цена',
  `plan_price` DECIMAL(12,2) NULL COMMENT 'плановая цена в акции',
  `currency_code` VARCHAR(8) NULL,
  `discount` INT NULL COMMENT 'текущая скидка, %',
  `plan_discount` INT NULL COMMENT 'рекомендуемая скидка для участия, %',
  -- --- из отчёта WB (ЛК «Товары для исключения из акции») ---
  `min_price` DECIMAL(12,2) NULL COMMENT 'минимальная цена для применения скидки по автоакции',
  `blocked` TINYINT NULL COMMENT 'стоит блокировка применения скидки по автоакции',
  `status` VARCHAR(255) NULL COMMENT 'статус участия из отчёта WB',
  `turnover_days` DECIMAL(10,2) NULL,
  `stock_wb` INT NULL,
  `stock_fbs` INT NULL,
  `barcode` VARCHAR(64) NULL,
  `vendor_code` VARCHAR(128) NULL,
  `brand` VARCHAR(255) NULL,
  `subject` VARCHAR(255) NULL,
  `title` VARCHAR(1024) NULL,
  `source` VARCHAR(16) NOT NULL DEFAULT '' COMMENT 'api | report',
  `fetched_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pp` (`company_id`, `promo_id`, `nm_id`),
  KEY `idx_pp_nm` (`company_id`, `nm_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_promotion_decisions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `promo_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `selected` TINYINT NOT NULL DEFAULT 1 COMMENT '1 — берём в акцию, 0 — не берём',
  `manual` TINYINT NOT NULL DEFAULT 1 COMMENT '1 — правил пользователь, 0 — по алгоритму',
  `user_id` INT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dec` (`company_id`, `promo_id`, `nm_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Идемпотентное добавление колонок отчёта WB.
--
-- Файл можно применять повторно и на базу, где таблицы созданы в более
-- ранней редакции: CREATE TABLE IF NOT EXISTS ничего не меняет, а колонки
-- ниже добавляются только если их ещё нет.
-- ---------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS `wb_add_col`;
DELIMITER //
CREATE PROCEDURE `wb_add_col`(IN p_table VARCHAR(64), IN p_col VARCHAR(64), IN p_ddl TEXT)
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table AND COLUMN_NAME = p_col
  ) THEN
    SET @s := CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN ', p_ddl);
    PREPARE st FROM @s;
    EXECUTE st;
    DEALLOCATE PREPARE st;
  END IF;
END//
DELIMITER ;

CALL wb_add_col('wb_promotion_products', 'min_price', '`min_price` DECIMAL(12,2) NULL');
CALL wb_add_col('wb_promotion_products', 'blocked', '`blocked` TINYINT NULL');
CALL wb_add_col('wb_promotion_products', 'status', '`status` VARCHAR(255) NULL');
CALL wb_add_col('wb_promotion_products', 'turnover_days', '`turnover_days` DECIMAL(10,2) NULL');
CALL wb_add_col('wb_promotion_products', 'stock_wb', '`stock_wb` INT NULL');
CALL wb_add_col('wb_promotion_products', 'stock_fbs', '`stock_fbs` INT NULL');
CALL wb_add_col('wb_promotion_products', 'barcode', '`barcode` VARCHAR(64) NULL');
CALL wb_add_col('wb_promotion_products', 'vendor_code', '`vendor_code` VARCHAR(128) NULL');
CALL wb_add_col('wb_promotion_products', 'brand', '`brand` VARCHAR(255) NULL');
CALL wb_add_col('wb_promotion_products', 'subject', '`subject` VARCHAR(255) NULL');
CALL wb_add_col('wb_promotion_products', 'title', '`title` VARCHAR(1024) NULL');
CALL wb_add_col('wb_promotion_products', 'source', '`source` VARCHAR(16) NOT NULL DEFAULT ''''');

DROP PROCEDURE `wb_add_col`;
