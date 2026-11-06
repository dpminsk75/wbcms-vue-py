-- Реклама WB, дополнение к 20261106_adv_bids_sync.sql:
--   предметы и доступные карточки (supplier/subjects, supplier/nms),
--   история пополнений рекламного счёта (adv/v1/payments),
--   тип оплаты кампании (cpm/cpc) — нужен для bids/min.
--
-- Схема переносится дампом БД целиком; миграция локальная, в git не коммитится.

CREATE TABLE IF NOT EXISTS `wb_adv_subject` (
  `company_id` INT NOT NULL,
  `subject_id` INT NOT NULL COMMENT 'ID предмета WB',
  `name` VARCHAR(255) NOT NULL DEFAULT '',
  `nm_count` INT NOT NULL DEFAULT 0 COMMENT 'сколько артикулов WB с этим предметом',
  `payment_type` VARCHAR(8) NOT NULL DEFAULT 'cpm',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `subject_id`, `payment_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_supplier_nm` (
  `company_id` INT NOT NULL,
  `nm_id` INT NOT NULL COMMENT 'артикул WB',
  `subject_id` INT NOT NULL DEFAULT 0,
  `title` VARCHAR(255) NOT NULL DEFAULT '',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `nm_id`),
  KEY `idx_adv_sn_subject` (`company_id`, `subject_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_payment` (
  `company_id` INT NOT NULL,
  `pay_id` INT NOT NULL COMMENT 'ID платежа',
  `pay_date` DATETIME NULL,
  `sum` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `pay_type` INT NOT NULL DEFAULT 0 COMMENT '0 — счёт, 1 — баланс, 3 — картой',
  `status_id` INT NOT NULL DEFAULT 0 COMMENT '0 — ошибка, 1 — обработано',
  `card_status` VARCHAR(32) NOT NULL DEFAULT '',
  `currency` VARCHAR(8) NOT NULL DEFAULT 'RUB',
  `collected_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `pay_id`),
  KEY `idx_adv_pay_date` (`company_id`, `pay_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Идемпотентное добавление колонок (процедура wb_add_col создаётся заново).
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

-- тип оплаты кампании: settings.paymentType из advert/v2/adverts (cpm | cpc)
CALL wb_add_col('wb_campaign', 'payment_type', "`payment_type` VARCHAR(8) NOT NULL DEFAULT '' COMMENT 'cpm | cpc'");

DROP PROCEDURE `wb_add_col`;
