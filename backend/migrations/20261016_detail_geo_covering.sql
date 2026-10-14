-- Покрывающий индекс под ТОП продаж (sales_analysis) и карту (geo_sales):
-- range-скан становится index-only (без лукапов строк для агрегатов).
-- Текстовые brand_name/subject_name сюда не влезают по длине ключа —
-- их отображение берём из wbcards (уже в JOIN), фильтры по ним остаются предикатами.
ALTER TABLE `detail_by_period`
  DROP INDEX `idx_detail_geo`,
  ADD INDEX `idx_detail_geo`
    (`company_id`, `supplier_oper_name`, `sale_dt`, `nm_id`, `ppvz_office_id`,
     `retail_amount`, `ppvz_for_pay`, `retail_price_withdisc_rub`, `ppvz_spp_prc`);
