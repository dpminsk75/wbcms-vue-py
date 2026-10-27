<template>
  <div class="wb-modal-backdrop margin-modal" @click.self="$emit('close')">
    <div
      ref="boxRef"
      class="wb-modal-box margin-modal__box"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      :style="boxStyle"
      data-modal-drag="own"
    >
      <div
        class="d-flex justify-content-between align-items-start gap-3 margin-modal__head"
        data-modal-drag-handle
        title="Потяните, чтобы переместить"
        v-on="dragHandlers"
      >
        <div class="min-w-0">
          <div class="margin-modal__title">{{ title }}</div>
          <div class="margin-modal__sub">
            {{ periodLabel }}
            <span v-if="nmLabel"> · {{ nmLabel }}</span>
          </div>
        </div>
        <div class="d-flex align-items-center gap-2">
          <span v-if="refreshing" class="margin-modal__refresh">
            <span class="spinner-border spinner-border-sm"></span>
          </span>
          <select
            v-if="campaigns.length"
            v-model.number="campaignSel"
            class="form-select form-select-sm margin-modal__campaign-select"
            title="Фильтр по рекламной кампании"
          >
            <option :value="0">Все кампании ({{ campaigns.length }})</option>
            <option v-for="c in campaigns" :key="c.campaign_id" :value="c.campaign_id">
              {{ c.name }} — {{ fmtMoney(c.cost) }} ₽
            </option>
          </select>
          <button class="btn btn-sm btn-link margin-modal__close" title="Закрыть" @click="$emit('close')">✕</button>
        </div>
      </div>

      <div v-if="busy && !data" class="margin-modal__state">
        <span class="spinner-border spinner-border-sm me-2"></span>Загрузка детализации…
      </div>
      <div v-else-if="isError && !data" class="alert alert-danger margin-modal__state">
        Ошибка при загрузке детализации. Попробуйте позже.
      </div>

      <template v-else-if="data">
        <ul class="nav nav-pills gap-1 margin-modal__tabs">
          <li v-for="t in data.tabs" :key="t.key" class="nav-item">
            <button class="nav-link" :class="{ active: activeKey === t.key }" @click="activeKey = t.key">
              {{ t.label }}
            </button>
          </li>
        </ul>

        <div v-if="mismatch" class="alert alert-warning margin-modal__warn mb-2 py-1 px-2 small">
          Сумма по дням ({{ fmtMoney(mismatch.days) }} ₽) не совпадает с детализацией
          ({{ fmtMoney(mismatch.detail) }} ₽) — расхождение {{ fmtMoney(mismatch.diff) }} ₽.
        </div>

        <div v-if="activeTab.totals.length" class="margin-modal__totals">
          <div v-for="t in activeTab.totals" :key="t.k" class="margin-modal__total">
            <div class="margin-modal__total-val">{{ fmtValue(t.value, t.type) }}</div>
            <div class="margin-modal__total-cap">{{ t.label }}</div>
          </div>
        </div>

        <!-- Сводная табличка: логистика — «Итоги по причинам», хранение — «Итоги по складам» -->
        <div v-if="activeTab.breakdown.length" class="margin-modal__breakdown">
          <div class="margin-modal__breakdown-title">{{ activeTab.breakdown_title || 'Итоги по причинам' }}</div>
          <table class="table table-sm table-bordered mb-0 margin-modal__btable">
            <thead>
              <tr>
                <th v-for="c in bdColumns" :key="c.k" :class="c.cls">{{ c.label }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="hasSections">
                <template v-for="sec in breakdownSections" :key="sec.label">
                  <tr class="margin-modal__breakdown-sep">
                    <td :colspan="bdColumns.length">{{ sec.label }}</td>
                  </tr>
                  <tr v-for="b in sec.rows" :key="b.label + (b.section || '')">
                    <td v-for="c in bdColumns" :key="c.k" :class="c.cls">{{ cell(b, c) }}</td>
                  </tr>
                </template>
              </template>
              <template v-else>
                <tr v-for="(b, i) in activeTab.breakdown" :key="i">
                  <td v-for="c in bdColumns" :key="c.k" :class="c.cls">{{ cell(b, c) }}</td>
                </tr>
              </template>
              <tr class="margin-modal__breakdown-total">
                <td>Итого</td>
                <td v-for="c in bdColumns.slice(1)" :key="c.k" :class="c.cls">{{ bdTotal(c) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="margin-modal__tablewrap">
          <table class="table table-sm table-bordered table-hover mb-0 margin-modal__table">
            <thead>
              <tr>
                <th v-for="c in activeTab.columns" :key="c.k" class="margin-modal__th">{{ c.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activeTab.rows.length">
                <td :colspan="Math.max(activeTab.columns.length, 1)" class="text-center text-muted py-3">
                  Данных за указанный период нет
                </td>
              </tr>
              <tr v-for="(r, i) in activeTab.rows" :key="i">
                <td v-for="c in activeTab.columns" :key="c.k" :class="c.cls">
                  <a
                    v-if="c.type === 'campaign' && r.campaign_id"
                    :href="`/wb-adv-report?id=${r.campaign_id}&date_from=${props.dateFrom}&date_to=${props.dateTo}`"
                    target="_blank"
                    class="margin-modal__campaign"
                  >{{ r.campaign || '—' }}</a>
                  <span v-else>{{ cell(r, c) }}</span>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="hasFooter">
              <tr class="margin-modal__tfoot">
                <td v-for="c in activeTab.columns" :key="c.k" :class="c.cls">{{ footCell(c) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-if="activeTab.truncated" class="margin-modal__trunc">
          Показаны первые {{ activeTab.shown }} строк
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { marginApi, type MarginBasis, type MarginBreakdownRow, type MarginCol, type MarginKind, type MarginTab } from '@/api/margin'
import { useDraggable } from '@/composables/useDraggable'

const props = withDefaults(defineProps<{
  kind: MarginKind
  basis?: MarginBasis
  dateFrom: string
  dateTo: string
  nmId?: string | number | null
  title?: string
  detail?: 0 | 1
}>(), { basis: 'product', detail: 1 })

const emit = defineEmits<{ close: [] }>()

const activeKey = ref('days')
/** Фильтр по рекламной кампании (0 — все кампании). */
const campaignSel = ref(0)

const { data, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => [
    'margin-breakdown', props.kind, props.basis, props.dateFrom, props.dateTo,
    props.nmId || 0, props.detail, campaignSel.value,
  ] as const),
  queryFn: () => marginApi.breakdown({
    kind: props.kind,
    basis: props.basis,
    dateFrom: props.dateFrom,
    dateTo: props.dateTo,
    nmId: props.nmId,
    detail: props.detail,
    campaignId: campaignSel.value || null,
  }),
  // при смене кампании старые данные остаются на экране, пока догружаются новые
  placeholderData: (prev: any) => prev,
} as any)

// Перетаскивание модалки за шапку.
const boxRef = ref<HTMLElement | null>(null)
const { boxStyle, dragHandlers } = useDraggable(boxRef)

// Если активной вкладки больше нет (например, при смене статьи) —
// переключаемся на первую.
watch(() => (data.value?.tabs || []).map(t => t.key).join('|'), () => {
  const tabs = (data.value?.tabs || []) as MarginTab[]
  if (tabs.length && !tabs.some(t => t.key === activeKey.value)) activeKey.value = tabs[0].key
})

const busy = computed(() => isLoading.value || isFetching.value)
// обновление (смена кампании): данные прежние на экране, таблица не мигает
const refreshing = computed(() => isFetching.value && !isLoading.value && !!data.value)

const title = computed(() => props.title || data.value?.title || '')
const periodLabel = computed(() => `${dmy(props.dateFrom)} — ${dmy(props.dateTo)}`)
const nmLabel = computed(() => (props.nmId ? `арт. ${props.nmId}` : ''))

const activeTabObj = computed<MarginTab | null>(() => {
  const tabs = (data.value?.tabs || []) as MarginTab[]
  return tabs.find(t => t.key === activeKey.value) || tabs[0] || null
})
const activeTab = computed<MarginTab>(() => activeTabObj.value || {
  key: '', label: '', totals: [], breakdown: [], campaigns: [], footer: {},
  truncated: false, columns: [], rows: [], shown: 0, total_rows: 0,
})

// Кампании для селекта — из любого таба (список всегда считается по всему периоду).
const campaigns = computed(() => {
  const tabs = (data.value?.tabs || []) as MarginTab[]
  for (const t of tabs) if (t.campaigns && t.campaigns.length) return t.campaigns
  return []
})

// Расхождение «по дням» vs «детализация» — индикатор рассинхрона источников.
const mismatch = computed(() => {
  const tabs = (data.value?.tabs || []) as MarginTab[]
  const days = tabs.find(t => t.key === 'days')
  const det = tabs.find(t => t.key === 'detail')
  if (!days || !det) return null
  const a = Number(days.sum || 0)
  const b = Number(det.sum || 0)
  const diff = Math.abs(a - b)
  if (diff <= 1) return null
  return { days: a, detail: b, diff }
})

// «Итоги по причинам» — группировка по разделам (штатная доставка / потери).
const breakdownSections = computed(() => {
  const out: { label: string, rows: MarginBreakdownRow[] }[] = []
  for (const b of activeTab.value.breakdown || []) {
    const secLabel = b.section || ''
    let sec = out.find(s => s.label === secLabel)
    if (!sec) { sec = { label: secLabel, rows: [] }; out.push(sec) }
    sec.rows.push(b)
  }
  return out
})
// Есть ли разделы (строки-разделители) — только у логистики.
const hasSections = computed(() => (activeTab.value.breakdown || []).some(b => !!b.section))

// Колонки сводной таблички: приходят от бэка (логистика/хранение разные).
const bdColumns = computed<MarginCol[]>(() => {
  const c = (activeTab.value as any).breakdown_columns
  if (c && c.length) return c as MarginCol[]
  return [
    { k: 'label', label: 'Причина', type: 'text' },
    { k: 'cnt', label: 'Записей', type: 'int', cls: 'text-end' },
    { k: 'amount', label: 'Сумма', type: 'money', cls: 'text-end fw-bold' },
  ]
})
// Итог по сводной табличке — сумма по числовым колонкам.
const bdTotal = (c: MarginCol): string => {
  const rows = (activeTab.value.breakdown || []) as any[]
  const sum = rows.reduce((a, b) => a + (Number(b?.[c.k]) || 0), 0)
  switch (c.type) {
    case 'money': return fmtMoney(sum)
    case 'int': return fmtInt(sum)
    case 'num': return fmtNum(sum)
    default: return ''
  }
}

const hasFooter = computed(() => {
  const f = activeTab.value.footer || {}
  return Object.keys(f).length > 0
})

const nfMoney = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const nfInt = new Intl.NumberFormat('ru-RU')
const nfNum = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })

const fmtMoney = (v: any) => nfMoney.format(Number(v) || 0)
const fmtInt = (v: any) => nfInt.format(Math.round(Number(v) || 0))
const fmtNum = (v: any) => nfNum.format(Number(v) || 0)
const fmtPct = (v: any) => `${nfNum.format(Number(v) || 0)} %`

const fmtValue = (v: any, type: string) => {
  switch (type) {
    case 'money': return `${fmtMoney(v)} ₽`
    case 'int': return fmtInt(v)
    case 'num': return fmtNum(v)
    case 'pct': return fmtPct(v)
    case 'rating': return v ? `${fmtNum(v)} ★` : '—'
    default: return v === null || v === undefined || v === '' ? '—' : String(v)
  }
}

const dmy = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}.${m[2]}.${m[1]}` : (iso || '—')
}

const cell = (r: any, c: MarginCol): string => {
  const v = r?.[c.k]
  switch (c.type) {
    case 'money': return fmtMoney(v)
    case 'int': return fmtInt(v)
    case 'num': return fmtNum(v)
    case 'pct': return fmtPct(v)
    case 'rating': return v ? `${fmtNum(v)} ★` : '—'
    case 'date': return dmy(String(v ?? ''))
    default: return v === null || v === undefined || v === '' ? '—' : String(v)
  }
}

/** Ячейка строки «Итого» (footer отдаёт бэк по тем же ключам колонок). */
const footCell = (c: MarginCol): string => {
  const f = activeTab.value.footer || {}
  const v = f[c.k]
  if (v === undefined || v === null || v === '') return ''
  if (c.type === 'date' || c.type === 'text' || c.type === 'campaign') return String(v)
  return cell({ [c.k]: v }, c)
}

const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
/* z-index выше навбара (глобальный .wb-modal-backdrop его не имеет) */
.margin-modal { z-index: 1060; }
/* Двойной класс — перебиваем центрирование глобального .wb-modal-backdrop:
   длинная таблица должна открываться сверху, а не по центру экрана. */
.wb-modal-backdrop.margin-modal { align-items: flex-start; padding: 24px 16px; }
.margin-modal__box { max-width: 1180px; width: 100%; max-height: 92vh; overflow: auto; padding: 16px 18px 18px; }
.margin-modal__head { margin-bottom: 10px; }
.margin-modal__refresh { display: inline-flex; align-items: center; color: #7f8c8d; }
.margin-modal__title { font-size: 16px; font-weight: 700; color: #111827; line-height: 1.25; }
.margin-modal__sub { font-size: 11px; color: #6b7280; }
.margin-modal__close { text-decoration: none; font-size: 14px; }
.margin-modal__campaign-select { max-width: 380px; font-size: 12px; }
.margin-modal__state { margin: 0; }
.margin-modal__tabs { margin-bottom: 10px; }
.margin-modal__tabs .nav-link { font-size: 12px; padding: 4px 12px; border-radius: 6px; }
.margin-modal__warn { font-size: 12px; }
.margin-modal__totals { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.margin-modal__total { flex: 1 1 150px; border: 1px solid #e3e7eb; border-radius: 8px; padding: 8px 10px; }
.margin-modal__total-val { font-size: 17px; font-weight: 700; color: #2c3e50; line-height: 1.2; }
.margin-modal__total-cap { font-size: 10px; text-transform: uppercase; color: #7f8c8d; margin-top: 2px; font-weight: 600; }
.margin-modal__breakdown { margin-bottom: 10px; }
.margin-modal__breakdown-title { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #7f8c8d; margin-bottom: 4px; }
.margin-modal__btable { font-size: 12px; }
.margin-modal__btable th { background: #f8f9fa; padding: 5px 6px; }
.margin-modal__btable td { padding: 4px 6px; }
.margin-modal__breakdown-sep td { background: #f1f5f9; font-weight: 700; font-size: 11px; color: #475569; }
.margin-modal__breakdown-total td { background: #f8f9fa; font-weight: 700; }
.margin-modal__tablewrap { overflow: auto; max-height: 52vh; }
.margin-modal__table { font-size: 12px; }
.margin-modal__table th { background: #f8f9fa; color: #34495e; padding: 6px; vertical-align: middle; position: sticky; top: 0; z-index: 1; }
.margin-modal__table td { padding: 5px 6px; vertical-align: middle; }
.margin-modal__tfoot td { background: #f8f9fa; font-weight: 700; border-top: 2px solid #dee2e6; }
.margin-modal__campaign { color: #2980b9; text-decoration: none; }
.margin-modal__campaign:hover { text-decoration: underline; }
.margin-modal__trunc { font-size: 12px; color: #7f8c8d; margin-top: 6px; }
</style>
