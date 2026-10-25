-- Очередь фраз на пересборку выдачи WB — 2026-10-22.
--
-- Что это: из отчёта «Выдача WB» можно отметить фразы и отправить их в
-- расширение — оно их пересобирает (как при обычном поиске: DOM-выдача +
-- JSON-каталог → позиции, цены, рейтинг, отзывы, файлы сырья).
--
-- Отличие от wb_competitor_query («Запросы конкурентов»): там фраза — это
-- широкий запрос ДЛЯ СБОРА КОНКУРЕНТОВ (по ней потом подбираем конкурентов),
-- здесь — просто фраза, выдачу по которой надо обновить. Разные статусы,
-- разный интерфейс, не смешиваются.
--
-- source_nm_id — наша карточка, относительно которой меряем позиции
-- (0 = без привязки: соберём сырьё по нише, позиций «нас» не будет).
--
-- MySQL 8, InnoDB, utf8mb4.

CREATE TABLE IF NOT EXISTS `wb_search_phrase_queue` (
  `id`            INT NOT NULL AUTO_INCREMENT,
  `company_id`    INT NOT NULL DEFAULT 0,
  `source_nm_id`  INT NOT NULL DEFAULT 0 COMMENT 'наша карточка (0 — без привязки)',
  `query_phrase`  VARCHAR(500) NOT NULL COMMENT 'фраза нормализованная',
  `phrase_raw`    VARCHAR(500) NOT NULL DEFAULT '' COMMENT 'как пришла из отчёта',
  `status`        ENUM('pending','processing','done','error') NOT NULL DEFAULT 'pending',
  `priority`      INT NOT NULL DEFAULT 10,
  `source`        VARCHAR(20) NOT NULL DEFAULT 'report' COMMENT 'откуда: report | manual',
  `last_error`    VARCHAR(500) DEFAULT NULL,
  `created_by`    INT DEFAULT NULL,
  `created_at`    TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_phrase` (`company_id`, `query_phrase`(190)),
  KEY `idx_status` (`company_id`, `status`, `priority`, `id`),
  KEY `idx_nm` (`source_nm_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Очередь фраз на пересборку выдачи WB';

-- Проверка после миграции:
-- SHOW CREATE TABLE wb_search_phrase_queue;
