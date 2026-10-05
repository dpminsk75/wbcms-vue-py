-- Базовые комиссии WB по предметам (common-api .../tariffs/commission).
-- Срезы бессрочно, но пишем только изменения (PK не даст дублей за день,
-- воркер сам сравнивает с последним срезом). Тарифы глобальные — company_id нет.
CREATE TABLE IF NOT EXISTS `wb_commission_tariffs` (
  `tariff_date` DATE NOT NULL COMMENT 'Дата среза (день синка)',
  `subject_id` INT NOT NULL COMMENT 'subjectID из tariffs/commission',
  `subject_name` VARCHAR(255) DEFAULT NULL,
  `parent_id` INT DEFAULT NULL,
  `parent_name` VARCHAR(255) DEFAULT NULL,
  `kgvp_booking` DECIMAL(6,2) DEFAULT NULL,
  `kgvp_marketplace` DECIMAL(6,2) DEFAULT NULL,
  `kgvp_pickup` DECIMAL(6,2) DEFAULT NULL,
  `kgvp_supplier` DECIMAL(6,2) DEFAULT NULL,
  `kgvp_supplier_express` DECIMAL(6,2) DEFAULT NULL,
  `paid_storage_kgvp` DECIMAL(6,2) DEFAULT NULL,
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`tariff_date`,`subject_id`),
  KEY `idx_tariff_subject` (`subject_id`,`tariff_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
