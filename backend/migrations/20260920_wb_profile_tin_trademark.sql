-- Профиль продавца: ИНН/марка из seller-info отдельными колонками
-- (кросс-чек с companies.inn). Зависит от 20260919_wb_token_type_profile.sql.
ALTER TABLE `company_wb_profile`
  ADD COLUMN `tin` VARCHAR(12) NULL COMMENT 'ИНН из seller-info' AFTER `seller_name`,
  ADD COLUMN `trademark` VARCHAR(255) NULL COMMENT 'tradeMark из seller-info' AFTER `tin`;
