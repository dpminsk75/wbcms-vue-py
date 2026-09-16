import { useMoneyFmt } from '@/composables/useMoneyFmt'

const { sumCol } = useMoneyFmt()

export interface MarginTotals {
  qnt: number
  amount: number
  commission: number
  f_acquiring_fee: number
  f_delivery: number
  f_penalty: number
  f_otziv: number
  f_adv: number
  f_cashback: number
  net_profit: number
  total_nds: number
  total_cost: number
  profit_before_tax: number
  tax_amount: number
  clean_margin: number
}

export function marginTotals(rows: any[]): MarginTotals {
  const keys: (keyof MarginTotals)[] = [
    'qnt', 'amount', 'commission', 'f_acquiring_fee', 'f_delivery', 'f_penalty',
    'f_otziv', 'f_adv', 'f_cashback', 'net_profit', 'total_nds', 'total_cost',
    'profit_before_tax', 'tax_amount', 'clean_margin',
  ]
  const out = {} as MarginTotals
  for (const k of keys) out[k] = sumCol(rows, k)
  return out
}

// Экспорт как Kartik ExportMenu: русские ключи + итоговая строка
export async function exportMarginExcel(rows: any[], fileName: string, sheet: string) {
  if (!rows.length) return
  const t = marginTotals(rows)
  const { default: XLSX } = await import('xlsx')
  const data = rows.map((r, i) => ({
    '#': i + 1,
    'Арт WB': r.nm_id,
    'Артикул': r.vendor_code,
    'Наименование': r.title,
    'Бренд': r.brand,
    'Кол-во': r.qnt,
    'Выручка': r.amount,
    'Ком. WB': r.commission,
    'Экв.': r.f_acquiring_fee,
    'Лог-ка': r.f_delivery,
    'Штрафы': r.f_penalty,
    'Отзывы': r.f_otziv,
    'Реклама': r.f_adv,
    'Кэшбек': r.f_cashback,
    'Итого': r.net_profit,
    'НДС': r.total_nds,
    'Себ-ть': r.total_cost,
    'Прибыль': r.profit_before_tax,
    'Налог (7%)': r.tax_amount,
    'Маржа': r.clean_margin,
    'Цена/шт': r.amount_per_item,
    'Итог/шт': r.profit_per_item,
    'Маржа/шт': r.clear_per_item,
  }))
  data.push({
    '#': '', 'Арт WB': '', 'Артикул': '', 'Наименование': 'ИТОГО', 'Бренд': '',
    'Кол-во': t.qnt, 'Выручка': t.amount, 'Ком. WB': t.commission, 'Экв.': t.f_acquiring_fee,
    'Лог-ка': t.f_delivery, 'Штрафы': t.f_penalty, 'Отзывы': t.f_otziv, 'Реклама': t.f_adv,
    'Кэшбек': t.f_cashback, 'Итого': t.net_profit, 'НДС': t.total_nds, 'Себ-ть': t.total_cost,
    'Прибыль': t.profit_before_tax, 'Налог (7%)': t.tax_amount, 'Маржа': t.clean_margin,
    'Цена/шт': null, 'Итог/шт': null, 'Маржа/шт': null,
  } as any)
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, sheet)
  XLSX.writeFile(wb, fileName)
}
