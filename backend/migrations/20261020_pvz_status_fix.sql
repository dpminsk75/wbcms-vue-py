-- Статус разбора по собственным полигонам (scripts/pvz_geo_fill_once.py):
-- регион есть, города/улицы нет — не путать с geo (полный разбор DaData).
-- Такие строки DaData не добьет (вне покрытия), из витрины неразобранных исключаем.
ALTER TABLE `pvz_all`
  MODIFY `dadata_status`
  ENUM('pending','ok','not_found','error','foreign','mismatch','geo','moved','fix')
  NOT NULL DEFAULT 'pending' COMMENT 'pending/ok/not_found/error/foreign/mismatch/geo/moved/fix';

CREATE OR REPLACE VIEW `pvz_unresolved` AS
SELECT `wb_id`, `country`, `address`, `lat`, `lon`,
       `source_version`, `is_closed`,
       `dadata_status`, `dadata_error`, `dadata_at`
FROM `pvz_all`
WHERE `dadata_status` NOT IN ('ok', 'geo', 'fix')
ORDER BY `country`, `wb_id`;
