-- Вариант B: живой прогресс — воркер пишет текущую попытку в item.note
-- ("кандидат 2/5: model-id"), фронт показывает у записи и в консоли.
ALTER TABLE `ai_job_item`
  ADD COLUMN `note` VARCHAR(500) NULL COMMENT 'текущая попытка, чистится при done/error' AFTER `error`;
