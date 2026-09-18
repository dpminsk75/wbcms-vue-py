-- AI-разбор: какая модель сделала + когда (показ в results).
ALTER TABLE `wb_competitor_analysis`
  ADD COLUMN `model` VARCHAR(100) NULL COMMENT 'модель, давшая ai_result' AFTER `ai_result`;
