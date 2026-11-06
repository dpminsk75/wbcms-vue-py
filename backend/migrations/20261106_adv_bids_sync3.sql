-- Реклама WB, дополнение к 20261106_adv_bids_sync.sql:
--   почасовые снимки статистики по поисковым кластерам (normquery/stats),
--   час и дата в истории изменения ставок.
--
-- wb_campaign_query_hour — снимок НАКОПИТЕЛЬНЫХ значений на конец часа
--   (не дельта): почасовой профиль = разности соседних строк,
--   суточные данные = последняя строка за день. Так подход работает
--   независимо от того, отдаёт ли WB накопительные значения или итог за день.
--
-- wb_adv_bid_history — добавляем дату и час: история ставок в разрезе часа.
--
-- Схема переносится дампом БД целиком; миграция локальная, в git не коммитится.

CREATE TABLE IF NOT EXISTS `wb_campaign_query_hour` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `date` DATE NOT NULL,
  `hour` TINYINT NOT NULL COMMENT '0..23 — час, на конец которого снят снимок',
  `query` VARCHAR(255) NOT NULL COMMENT 'поисковый кластер',
  `views` INT NOT NULL DEFAULT 0,
  `clicks` INT NOT NULL DEFAULT 0,
  `atbs` INT NOT NULL DEFAULT 0,
  `orders` INT NOT NULL DEFAULT 0,
  `shks` INT NOT NULL DEFAULT 0,
  `sum` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `avg_pos` DECIMAL(6,2) NULL,
  `is_provisional` TINYINT NOT NULL DEFAULT 0 COMMENT 'снимок текущего дня ещё не закрыт',
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `date`, `hour`, `query`(190)),
  KEY `idx_adv_q_hour` (`company_id`, `date`, `hour`),
  KEY `idx_adv_q_hour_nm` (`company_id`, `nm_id`, `date`)
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

-- история ставок в разрезе часа
CALL wb_add_col('wb_adv_bid_history', 'date', "`date` DATE NULL COMMENT 'день изменения ставки'");
CALL wb_add_col('wb_adv_bid_history', 'hour', "`hour` TINYINT NULL COMMENT 'час изменения ставки 0..23'");

DROP PROCEDURE `wb_add_col`;
