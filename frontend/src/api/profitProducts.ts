// Отчёт «Маржа по продуктам» (/wb-profit/products).
// Контракт совпадает по полям с маржой по карточкам (api/profit.ts),
// но строки — по линейкам (product), а не по карточкам.

export type CostSource = 'manual' | 'derived' | 'none'

export interface ProductMarginRow {
  product_id: number
  product_name: string
  product_type: string
  brand: string
  cards_count: number
  // объём
  qnt: number
  amount: number
  // статьи
  commission: number
  f_acquiring_fee: number
  f_acceptance: number
  f_delivery: number
  f_storage_fee: number
  f_penalty: number
  f_deduction: number
  f_otziv: number
  f_adv: number
  f_cashback: number
  net_profit: number
  total_nds: number
  // себестоимость
  total_cost: number
  cost_source: CostSource
  // прибыль
  profit_before_tax: number
  tax_amount: number
  clean_margin: number
  // на единицу
  amount_per_item: number
  profit_per_item: number
  clear_per_item: number
  cost_per_item: number
  // предупреждения по строке
  p_incomplete: boolean
  no_cost: boolean
}

export interface ProductMarginWarnings {
  /** карточек, входящих в больше чем один продукт (выручка задвоена) */
  duplicated_cards: number
  /** на сколько рублей задвоена выручка из-за этих карточек */
  duplicated_amount: number
  /** карточек, у которых сумма долей (p) != 100 */
  p_incomplete_cards: number
  /** линеек без себестоимости (ни ручной, ни производной) */
  products_without_cost: number
  /** линеек, где себестоимость задана вручную */
  products_manual_cost: number
}

export interface ProductMarginResponse {
  rows: ProductMarginRow[]
  date_from: string
  date_to: string
  warnings: ProductMarginWarnings
  totals: ProductMarginRow
}

export interface ProductCardRow {
  nm_id: number
  title: string
  brand: string
  vendor_code: string
  /** сколько штук карточки входит в продукт */
  q: number
  /** доля карточки в продукте, % (исходное значение) */
  p: number
  /** нормализованная доля (p / сумма p по карточке) */
  p_norm: number
  /** сумма p по этой карточке во всех продуктах (100 = норма) */
  p_sum: number
  /** закупочная цена за единицу */
  cost_price: number
  /** вклад карточки в себестоимость продукта */
  cost_contribution: number
  qnt: number
  amount: number
  net_profit: number
  total_nds: number
  total_cost: number
  profit_before_tax: number
  tax_amount: number
  clean_margin: number
  /** есть ли у карточки продажи в периоде */
  has_sales: boolean
}

export interface ProductCardsResponse {
  product_id: number
  product_name: string
  rows: ProductCardRow[]
  total_cost: number
  cost_source: CostSource
}

export const PRODUCT_MARGIN_SORTABLE = [
  'qnt', 'amount', 'net_profit', 'clean_margin', 'total_cost',
] as const
export type ProductMarginSort = typeof PRODUCT_MARGIN_SORTABLE[number]

export function validateProductSort(s: string): ProductMarginSort {
  return (PRODUCT_MARGIN_SORTABLE as readonly string[]).includes(s)
    ? (s as ProductMarginSort)
    : 'amount'
}
