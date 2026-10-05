-- Сканы поставок FBS (GET /api/v3/supplies): scanDt — фактическое время сдачи,
-- closedAt/done — «оценка по закрытию». Стыковка: wb_orders_fbs.supply_id.
-- Синк каждые 30 мин (свежесть внутри дня), upsert по supply_id.
CREATE TABLE IF NOT EXISTS `wb_orders_fbs_supplies` (
  `supply_id` VARCHAR(100) NOT NULL COMMENT 'WB-GI-... из /api/v3/supplies',
  `name` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME DEFAULT NULL COMMENT 'createdAt поставки (UTC)',
  `closed_at` DATETIME DEFAULT NULL COMMENT 'closedAt (UTC, может отсутствовать)',
  `scan_dt` DATETIME DEFAULT NULL COMMENT 'scanDt — скан приёмки (UTC, может отсутствовать)',
  `done` TINYINT(1) NOT NULL DEFAULT '0' COMMENT 'флаг закрытия поставки',
  `cargo_type` TINYINT DEFAULT NULL,
  `destination_office_id` BIGINT DEFAULT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'когда синкнули',
  PRIMARY KEY (`supply_id`),
  KEY `idx_scan_dt` (`scan_dt`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
