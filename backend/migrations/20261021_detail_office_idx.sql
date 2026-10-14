-- Доступ «офисы -> продажи» для отчетов с parent-фильтром (страна/регион/город):
-- сначала дешево забираем wb_id офисов из pvz_all, потом точечные пробы в деталку.
-- Порядок важен: равенства (company, supplier, ppvz) + диапазон sale_dt; nm_id для GROUP BY.
CREATE INDEX `idx_detail_office` ON `detail_by_period`
  (`company_id`, `supplier_oper_name`, `ppvz_office_id`, `sale_dt`, `nm_id`);
