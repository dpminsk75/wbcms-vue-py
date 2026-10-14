-- Индекс под отчет "Продажи на карте" (GET /api/geo/sales-map):
-- равенства company_id + supplier_oper_name, диапазон sale_dt, опционально nm_id IN (...).
-- Порядок важен: сначала равенства, потом диапазон.
CREATE INDEX `idx_detail_geo` ON `detail_by_period`
  (`company_id`, `supplier_oper_name`, `sale_dt`, `nm_id`);
