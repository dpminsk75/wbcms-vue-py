-- Реклама WB: ставки, рекомендации, кластеры, минус-фразы, лимиты, бюджет,
-- почасовые дельты, история списаний.
-- Схема переносится дампом БД целиком; миграция локальная, в git не коммитится.
--
-- Источники — ТОЛЬКО чтение из advert-api.wildberries.ru:
--   wb_adv_bid                — POST /adv/v0/normquery/get-bids (текущие ставки кластеров)
--   wb_adv_bid_history        — история изменения ставок (пишем при смене значения)
--   wb_adv_bid_recommendation — GET /api/advert/v0/bids/recommendations (рекомендации WB)
--   wb_adv_minus_phrase       — POST /adv/v0/normquery/get-minus (минус-фразы)
--   wb_adv_cluster            — POST /adv/v0/normquery/list (active/excluded/archived)
--   wb_adv_daily_limit        — GET /api/advert/v0/daily-limits (CPC-кампании)
--   wb_adv_account            — GET /api/advert/v1/config + GET /adv/v1/balance
--   wb_adv_card_bid           — nmSettings[].bidsKopecks из GET /api/advert/v2/adverts
--   wb_adv_upd                — GET /adv/v1/upd (история списаний)
--   wb_adv_campaign_hour      — почасовые дельты (снимок fullstats минус снимок)
--   wb_adv_rules              — пороги правила автоисключения (пока только дефолты)
--   wb_adv_key_flag           — ручные пометки «нужный ключ»
--   wb_adv_action_log         — журнал действий (пока пустой: записи в WB ещё нет)

CREATE TABLE IF NOT EXISTS `wb_adv_bid` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `norm_query` VARCHAR(255) NOT NULL COMMENT 'поисковый кластер',
  `bid_base` DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'ставка за 1000 показов, базовые единицы валюты',
  `bid_kopecks` INT NOT NULL DEFAULT 0 COMMENT 'та же ставка в копейках',
  `currency` VARCHAR(8) NOT NULL DEFAULT 'RUB',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `norm_query`(190)),
  KEY `idx_adv_bid_camp` (`company_id`, `campaign_id`),
  KEY `idx_adv_bid_nm` (`company_id`, `nm_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_bid_history` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `norm_query` VARCHAR(255) NOT NULL,
  `bid_kopecks` INT NOT NULL DEFAULT 0,
  `prev_kopecks` INT NOT NULL DEFAULT 0,
  `changed_by` VARCHAR(64) NOT NULL DEFAULT 'sync' COMMENT 'sync | manual | wb',
  `changed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_adv_bid_hist` (`company_id`, `campaign_id`, `changed_at`),
  KEY `idx_adv_bid_hist_q` (`company_id`, `norm_query`(190), `changed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_bid_recommendation` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `scope` VARCHAR(10) NOT NULL DEFAULT 'cluster' COMMENT 'cluster — по кластеру; base — по карточке',
  `norm_query` VARCHAR(255) NOT NULL DEFAULT '',
  `min_kopecks` INT NULL COMMENT 'reachMin.bidKopecks',
  `medium_kopecks` INT NULL COMMENT 'reachMedium.bidKopecks',
  `max_kopecks` INT NULL COMMENT 'reachMax.bidKopecks',
  `min_limit_kopecks` INT NULL COMMENT 'минимальная ставка WB для кластера (bidKopecksMin)',
  `competitive_kopecks` INT NULL COMMENT 'base.competitiveBid',
  `leaders_kopecks` INT NULL COMMENT 'base.leadersBid',
  `top2_kopecks` INT NULL COMMENT 'base.top2',
  `raw_json` JSON NULL COMMENT 'сырой ответ WB — для CPC-кампаний (levels)',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `scope`, `norm_query`(190)),
  KEY `idx_adv_rec_nm` (`company_id`, `nm_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_minus_phrase` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `norm_query` VARCHAR(255) NOT NULL,
  `in_wb` TINYINT NOT NULL DEFAULT 1 COMMENT '1 — уже применено в WB',
  `added_by` VARCHAR(64) NOT NULL DEFAULT '',
  `added_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `norm_query`(190)),
  KEY `idx_adv_minus_q` (`company_id`, `norm_query`(190))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_cluster` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `norm_query` VARCHAR(255) NOT NULL,
  `state` VARCHAR(12) NOT NULL DEFAULT 'active' COMMENT 'active | excluded | archived',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `norm_query`(190)),
  KEY `idx_adv_cluster_state` (`company_id`, `campaign_id`, `state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_daily_limit` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `enabled` TINYINT NOT NULL DEFAULT 0,
  `daily_limit` INT NOT NULL DEFAULT 0 COMMENT 'разменные единицы (0,01 валюты)',
  `spent_today` INT NOT NULL DEFAULT 0,
  `carry_over` TINYINT NOT NULL DEFAULT 0 COMMENT 'перенос остатка на следующий день',
  `is_valid` TINYINT NOT NULL DEFAULT 1 COMMENT 'хватает ли лимита на текущие ставки',
  `required_limit` INT NOT NULL DEFAULT 0 COMMENT 'рекомендованный минимальный лимит',
  `currency` VARCHAR(8) NOT NULL DEFAULT 'RUB',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_account` (
  `company_id` INT NOT NULL,
  `currency` VARCHAR(8) NOT NULL DEFAULT 'RUB',
  `currency_code` INT NOT NULL DEFAULT 643,
  `cpm_step` INT NOT NULL DEFAULT 0 COMMENT 'шаг ставки CPM, копейки',
  `cpc_step` INT NOT NULL DEFAULT 0 COMMENT 'шаг ставки CPC, копейки',
  `min_daily_limit` INT NOT NULL DEFAULT 0,
  `min_top_up` INT NOT NULL DEFAULT 0,
  `balance_base` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `net_base` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `bonus_base` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_card_bid` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL,
  `placement` VARCHAR(16) NOT NULL COMMENT 'search | recommendations',
  `bid_kopecks` INT NOT NULL DEFAULT 0,
  `min_kopecks` INT NOT NULL DEFAULT 0 COMMENT 'минимальная ставка (bids/min); 0 — неизвестно',
  `currency` VARCHAR(8) NOT NULL DEFAULT 'RUB',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `placement`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_upd` (
  `company_id` INT NOT NULL,
  `advert_id` INT NOT NULL,
  `upd_key` VARCHAR(64) NOT NULL COMMENT 'хеш updTime|advertId|updSum|paymentType',
  `upd_time` DATETIME NULL COMMENT 'бывает NULL — текущее, ещё не проведённое списание',
  `upd_sum` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `camp_name` VARCHAR(255) NOT NULL DEFAULT '',
  `advert_type` INT NOT NULL DEFAULT 0,
  `payment_type` VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'Баланс | Бонусы | Счёт | Кэшбэк',
  `advert_status` INT NOT NULL DEFAULT 0,
  `collected_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `advert_id`, `upd_key`),
  KEY `idx_adv_upd_time` (`company_id`, `upd_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_campaign_hour` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL DEFAULT 0 COMMENT '0 — уровень площадки (app_type), иначе карточка',
  `app_type` INT NOT NULL DEFAULT 0 COMMENT '1 | 32 | 64; 0 — уровень кампании',
  `date` DATE NOT NULL,
  `hour` TINYINT NOT NULL COMMENT '0..23 — бакет часа',
  `views` INT NOT NULL DEFAULT 0,
  `clicks` INT NOT NULL DEFAULT 0,
  `atbs` INT NOT NULL DEFAULT 0,
  `orders` INT NOT NULL DEFAULT 0,
  `canceled` INT NOT NULL DEFAULT 0,
  `shks` INT NOT NULL DEFAULT 0,
  `sum` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `sum_price` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `is_provisional` TINYINT NOT NULL DEFAULT 0 COMMENT 'бакет текущего дня ещё не закрыт',
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `app_type`, `date`, `hour`),
  KEY `idx_adv_hour_day` (`company_id`, `date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_campaign_hour_snap` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL,
  `nm_id` INT NOT NULL DEFAULT 0,
  `app_type` INT NOT NULL DEFAULT 0,
  `date` DATE NOT NULL,
  `hour_taken` TINYINT NOT NULL COMMENT 'час прогона, которым записан снимок',
  `views` INT NOT NULL DEFAULT 0,
  `clicks` INT NOT NULL DEFAULT 0,
  `atbs` INT NOT NULL DEFAULT 0,
  `orders` INT NOT NULL DEFAULT 0,
  `canceled` INT NOT NULL DEFAULT 0,
  `shks` INT NOT NULL DEFAULT 0,
  `sum` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `sum_price` DECIMAL(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `app_type`, `date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_rules` (
  `company_id` INT NOT NULL,
  `rule_enabled` TINYINT NOT NULL DEFAULT 1,
  `min_views` INT NOT NULL DEFAULT 100 COMMENT 'порог статистики: меньше показов — правило не применяем',
  `min_ctr` DECIMAL(6,2) NOT NULL DEFAULT 5.00 COMMENT 'жёсткий пол CTR, %',
  `ctr_ratio` DECIMAL(4,2) NOT NULL DEFAULT 0.50 COMMENT 'мягкий пол: доля от медианы CTR кампании',
  `exclude_if_no_orders` TINYINT NOT NULL DEFAULT 1 COMMENT 'убирать, где нет заказов',
  `keep_if_orders` TINYINT NOT NULL DEFAULT 1 COMMENT 'есть заказы — не исключаем даже при низком CTR',
  `keep_if_atbs` TINYINT NOT NULL DEFAULT 0 COMMENT 'есть только корзины — тоже оставляем',
  `min_atbs` INT NOT NULL DEFAULT 1,
  `keep_top` TINYINT NOT NULL DEFAULT 1 COMMENT 'не исключать ТОП-ключевые',
  `top_days` INT NOT NULL DEFAULT 30 COMMENT 'окно анализа для ТОПа, дней',
  `top_metric` VARCHAR(12) NOT NULL DEFAULT 'orders' COMMENT 'orders | sum | cpo',
  `top_share` DECIMAL(4,2) NOT NULL DEFAULT 0.60 COMMENT 'доля продаж, набираемая ТОПом',
  `min_spend_for_minus` DECIMAL(12,2) NOT NULL DEFAULT 100 COMMENT 'минимальные пустые расходы для кандидата',
  `bid_over_max_ratio` DECIMAL(6,2) NOT NULL DEFAULT 1.10,
  `cpc_over_max_ratio` DECIMAL(6,2) NOT NULL DEFAULT 1.30,
  `leader_orders` INT NOT NULL DEFAULT 5,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_key_flag` (
  `company_id` INT NOT NULL,
  `campaign_id` INT NOT NULL DEFAULT 0 COMMENT '0 — фраза защищена во всех кампаниях',
  `nm_id` INT NOT NULL DEFAULT 0 COMMENT '0 — по всем карточкам',
  `norm_query` VARCHAR(255) NOT NULL,
  `flag` VARCHAR(16) NOT NULL DEFAULT 'keep' COMMENT 'keep — не исключать; exclude — исключить принудительно',
  `reason` VARCHAR(255) NOT NULL DEFAULT '',
  `created_by` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`company_id`, `campaign_id`, `nm_id`, `norm_query`(190)),
  KEY `idx_adv_flag_q` (`company_id`, `norm_query`(190))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `wb_adv_action_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `company_id` INT NOT NULL,
  `user_id` INT NULL,
  `user_name` VARCHAR(64) NOT NULL DEFAULT '',
  `action` VARCHAR(32) NOT NULL COMMENT 'set_bids | delete_bids | set_minus | set_card_bids | set_nms | set_placements | set_daily_limits',
  `target` VARCHAR(16) NOT NULL DEFAULT '' COMMENT 'cluster | card | campaign',
  `campaign_id` INT NULL,
  `nm_id` INT NULL,
  `payload` JSON NULL,
  `result` VARCHAR(16) NOT NULL DEFAULT 'ok' COMMENT 'ok | error',
  `detail` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_adv_log` (`company_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Идемпотентное добавление колонок в существующие таблицы.
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

-- wb_campaign: тип ставки и места размещения (API их уже отдаёт, мы не сохраняли)
CALL wb_add_col('wb_campaign', 'bid_type', "`bid_type` VARCHAR(10) NOT NULL DEFAULT '' COMMENT 'manual | unified'");
CALL wb_add_col('wb_campaign', 'place_search', '`place_search` TINYINT NOT NULL DEFAULT 0');
CALL wb_add_col('wb_campaign', 'place_recommend', '`place_recommend` TINYINT NOT NULL DEFAULT 0');
-- остаток бюджета кампании (GET /adv/v1/budget -> total)
CALL wb_add_col('wb_campaign', 'budget_total', '`budget_total` DECIMAL(14,2) NOT NULL DEFAULT 0');
CALL wb_add_col('wb_campaign', 'budget_updated_at', '`budget_updated_at` DATETIME NULL');
-- средняя позиция по кластеру (adv/v1/normquery/stats -> stat.avgPos)
CALL wb_add_col('wb_campaign_query', 'avg_pos', '`avg_pos` DECIMAL(6,2) NULL');

DROP PROCEDURE `wb_add_col`;
