/**
 * Расшифровка колонок маржи — «По дням» (куб agg_daily_summary) + «Детализация»
 * (исходные таблицы WB). Контракт один для всех статей: бэк отдаёт готовые
 * табы с описанием колонок и типом значения, фронт только форматирует.
 *
 * basis:
 *   'month'   — как в «Финансовой аналитике» дашборда (f_* из детализации продаж);
 *   'product' — как в отчётах по товарам (ff_* из куба).
 */
import { api } from './client'

export type MarginKind =
  | 'acceptance' | 'delivery' | 'storage' | 'penalty'
  | 'deduction' | 'otziv' | 'adv' | 'cashback'

export type MarginBasis = 'month' | 'product'

export type MarginColType = 'money' | 'int' | 'num' | 'pct' | 'rating' | 'date' | 'text' | 'campaign'

export interface MarginCol {
  k: string
  label: string
  type: MarginColType
  cls?: string
}

export interface MarginTotal {
  k: string
  label: string
  type: MarginColType
  value: number
}

/** Строка сводной таблички: логистика (причина) или хранение (склад/тип расчёта). */
export interface MarginBreakdownRow {
  /** Склад (хранение) или название причины (логистика). */
  label: string
  /** Раздел-разделитель (только логистика): «Штатная доставка» / «Потери на доставке». */
  section?: string
  bucket?: string
  /** Тип расчёта (хранение). */
  calc_type?: string
  units?: number
  volume?: number
  cnt?: number
  amount?: number
}

/** Рекламная кампания — для селекта фильтра в шапке модалки. */
export interface MarginCampaign {
  campaign_id: number
  name: string
  cost: number
  views: number
  orders: number
}

export interface MarginTab {
  key: string
  label: string
  sum?: number
  totals: MarginTotal[]
  breakdown: MarginBreakdownRow[]
  /** Заголовок сводной таблички («Итоги по причинам» / «Итоги по складам»). */
  breakdown_title?: string
  /** Колонки сводной таблички (приходят от бэка — у логистики и хранения разные). */
  breakdown_columns?: MarginCol[]
  campaigns: MarginCampaign[]
  /** Итоговая строка таблицы (совпадает с набором колонок). */
  footer: Record<string, any>
  /** true — строки обрезаны лимитом, показана только первая страница. */
  truncated: boolean
  columns: MarginCol[]
  rows: any[]
  shown: number
  total_rows: number
}

export interface MarginBreakdown {
  kind: MarginKind
  basis: MarginBasis
  title: string
  date_from: string
  date_to: string
  nm_id: number | null
  campaign_id: number | null
  tabs: MarginTab[]
}

export const marginApi = {
  breakdown: (p: {
    kind: MarginKind
    basis?: MarginBasis
    dateFrom: string
    dateTo: string
    nmId?: string | number | null
    detail?: 0 | 1
    /** Фильтр по рекламной кампании (только kind='adv'). */
    campaignId?: number | null
  }) =>
    api.get<MarginBreakdown>('/api/profit/breakdown', {
      params: {
        kind: p.kind,
        basis: p.basis || 'product',
        date_from: p.dateFrom,
        date_to: p.dateTo,
        ...(p.nmId ? { nm_id: p.nmId } : {}),
        ...(p.campaignId ? { campaign_id: p.campaignId } : {}),
        detail: p.detail ?? 1,
      },
    }).then(r => r.data),
}
