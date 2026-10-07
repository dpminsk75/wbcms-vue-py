-- WB-новости портала продавцов (md 2026-10-07): hourly-синк, фильтр типов на чтении.
CREATE TABLE IF NOT EXISTS `wb_news` (
  `id` BIGINT NOT NULL COMMENT 'id новости WB',
  `date` DATETIME NULL,
  `header` VARCHAR(500) DEFAULT NULL,
  `content` MEDIUMTEXT,
  `types` JSON NULL COMMENT 'плоский [{id, name}] из types ответа',
  `fetched_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `idx_wb_news_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `wb_news_reads` (
  `user_id` INT NOT NULL,
  `news_id` BIGINT NOT NULL COMMENT 'FK -> wb_news.id',
  `read_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`news_id`),
  CONSTRAINT `fk_news_reads_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE `companies`
  ADD COLUMN `news_types` JSON NULL COMMENT 'id типов новостей для сотрудников, NULL/пусто = все';
