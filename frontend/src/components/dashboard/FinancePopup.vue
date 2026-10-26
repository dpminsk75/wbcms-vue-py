<template>
  <div class="page-dashboard__popup-overlay" @mousedown.self="$emit('close')">
    <div class="page-dashboard__popup-box" role="dialog" aria-modal="true" :aria-label="meta.title">
      <div class="page-dashboard__popup-head">
        <span class="page-dashboard__popup-title">Детализация: {{ meta.title }} ({{ periodLabel }})</span>
        <button class="btn btn-sm btn-link page-dashboard__popup-close" title="Закрыть" @click="$emit('close')">✕</button>
      </div>
      <div v-if="busy" class="page-dashboard__popup-state"><span class="spinner-border spinner-border-sm me-2"></span> Загрузка детализации…</div>
      <div v-else-if="isError" class="alert alert-danger page-dashboard__popup-state">Ошибка при загрузке детализации. Попробуйте позже.</div>
      <template v-else-if="payload">
        <label v-if="kind === 'feedback'" class="page-dashboard__popup-check">
          <input type="checkbox" v-model="paidOnly" /> Только платные
        </label>
        <div v-if="kind === 'feedback'" class="page-dashboard__popup-note">Суммы в строке «Отзывы» — удержания WB из детализации, здесь — отзывы покупателей (стоимость — только у платных).</div>
        <div class="page-dashboard__popup-stats">
          <div class="page-dashboard__popup-stat">
            <div class="page-dashboard__popup-stat-val" :style="{ color: meta.color }">{{ statMain }}</div>
            <div class="page-dashboard__popup-stat-cap">{{ statMainCap }}</div>
          </div>
          <div v-if="statSecond" class="page-dashboard__popup-stat">
            <div class="page-dashboard__popup-stat-val">{{ statSecond }}</div>
            <div class="page-dashboard__popup-stat-cap">{{ statSecondCap }}</div>
          </div>
        </div>
        <div v-if="truncated" class="page-dashboard__popup-trunc">Показаны первые {{ payload.limit }} записей из {{ totalCount }}</div>
        <div class="page-dashboard__popup-tablewrap">
          <table class="table table-bordered table-hover mb-0 page-dashboard__popup-table">
            <thead>
              <tr>
                <th v-for="c in columns" :key="c" class="page-dashboard__popup-th">{{ c }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!rows.length">
                <td :colspan="columns.length" class="page-dashboard__popup-empty">Данные за указанный период отсутствуют.</td>
              </tr>
              <tr v-for="(r, i) in rows" :key="i">
                <td v-for="c in cols" :key="c.k" :class="c.cls">{{ cell(r, c.k) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'

export type FinancePopupKind = 'shf' | 'udr' | 'feedback' | 'storage' | 'acceptance' | 'adv' | 'logistics'

const props = defineProps<{ kind: FinancePopupKind, dateFrom: string, dateTo: string }>()
const emit = defineEmits<{ close: [] }>()

const auth = useAuthStore()
// Чекбокс «Только платные» (is_pay > 0 или f_cost > 0), по умолчанию включён.
const paidOnly = ref(props.kind === 'feedback')
const { data, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['finance-popup', props.kind, auth.companyId, props.dateFrom, props.dateTo, paidOnly.value] as const),
  queryFn: () => {
    if (props.kind === 'shf' || props.kind === 'udr' || props.kind === 'adv') return dashboardApi.financeDetail(props.kind, props.dateFrom, props.dateTo)
    if (props.kind === 'logistics') return dashboardApi.financeLogistics(props.dateFrom, props.dateTo)
    if (props.kind === 'storage') return dashboardApi.financeStorage(props.dateFrom, props.dateTo)
    if (props.kind === 'acceptance') return dashboardApi.financeAcceptance(props.dateFrom, props.dateTo)
    return dashboardApi.feedbackPopup(props.dateFrom, props.dateTo, paidOnly.value)
  },
} as any)
const busy = computed(() => isLoading.value || isFetching.value)
const payload = computed(() => (data.value as any) || null)

const META: Record<FinancePopupKind, { title: string, color: string }> = {
  shf: { title: 'Штрафы', color: '#e74c3c' },
  udr: { title: 'Удержания', color: '#e67e22' },
  feedback: { title: 'Отзывы', color: '#16a085' },
  storage: { title: 'Хранение', color: '#c0392b' },
  acceptance: { title: 'Приёмка', color: '#c0392b' },
  adv: { title: 'Реклама', color: '#8a2be0' },
  logistics: { title: 'Логистика', color: '#e67e22' },
}
const meta = computed(() => META[props.kind])

const dmy = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}.${m[2]}.${m[1]}` : (iso || '—')
}
const dmyhm = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso || '')
  if (m) return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`
  return dmy(iso)
}
const periodLabel = computed(() => `${dmy(props.dateFrom)} — ${dmy(props.dateTo)}`)
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)

const rows = computed(() => ((payload.value?.items || []) as any[]))
const totalCount = computed(() => Number(payload.value?.total_count ?? payload.value?.stats?.total_feedbacks ?? rows.value.length) || 0)
const truncated = computed(() => !!payload.value?.limit && totalCount.value > (payload.value.limit as number))

const statMain = computed(() => {
  const p = payload.value
  if (!p) return ''
  if (props.kind === 'feedback') return fmt0(p.stats?.total_feedbacks)
  return `${fmt2(p.total_sum)} ₽`
})
const statMainCap = computed(() => (props.kind === 'feedback' ? 'Всего отзывов' : 'Общая сумма'))
const statSecond = computed(() => {
  const p = payload.value
  if (!p) return ''
  if (props.kind === 'shf' || props.kind === 'udr' || props.kind === 'acceptance' || props.kind === 'adv' || props.kind === 'logistics') return fmt0(p.total_count)
  if (props.kind === 'feedback') return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(p.stats?.avg_valuation) || 0)
  return ''
})
const statSecondCap = computed(() => {
  if (props.kind === 'feedback') return 'Средняя оценка'
  return 'Количество записей'
})

interface Col { k: string, cls: string }
const cols = computed<Col[]>(() => {
  switch (props.kind) {
    case 'shf':
    case 'udr':
    case 'adv':
    case 'logistics':
      return [
        { k: 'row_date', cls: 'page-dashboard__popup-date' },
        { k: 'product', cls: '' },
        { k: 'amount', cls: 'page-dashboard__popup-sum' },
        { k: 'reason', cls: '' },
      ]
    case 'feedback':
      return [
        { k: 'row_date', cls: 'page-dashboard__popup-date' },
        { k: 'product', cls: '' },
        { k: 'valuation', cls: 'page-dashboard__popup-center' },
        { k: 'user', cls: '' },
        { k: 'cost', cls: 'page-dashboard__popup-center' },
        { k: 'text', cls: '' },
      ]
    case 'storage':
      return [
        { k: 'date', cls: 'page-dashboard__popup-date' },
        { k: 'warehouse', cls: '' },
        { k: 'total_price', cls: 'page-dashboard__popup-sum' },
        { k: 'total_units', cls: 'page-dashboard__popup-center' },
      ]
    case 'acceptance':
      return [
        { k: 'date', cls: 'page-dashboard__popup-date' },
        { k: 'total', cls: 'page-dashboard__popup-sum' },
        { k: 'cnt', cls: 'page-dashboard__popup-center' },
      ]
  }
})
const columns = computed(() => {
  switch (props.kind) {
    case 'shf':
    case 'udr':
    case 'adv':
    case 'logistics': return ['Дата', 'Товар', 'Сумма', 'Обоснование / Описание']
    case 'feedback': return ['Дата', 'Товар', 'Оценка', 'Пользователь', 'Стоимость', 'Содержимое отзыва']
    case 'storage': return ['Дата', 'Склад', 'Сумма', 'Штук']
    case 'acceptance': return ['Дата', 'Сумма', 'Записей']
  }
})
const cell = (r: any, k: string): string => {
  switch (k) {
    case 'row_date': return dmyhm(String(r.row_date ?? r.createdDate ?? ''))
    case 'date': return dmy(String(r.date ?? ''))
    case 'product': {
      const nm = r.nmID ?? r.nmId ?? ''
      const t = r.card_title || 'Название не найдено'
      return nm ? `${nm} · ${t}` : String(t)
    }
    case 'amount': return `${fmt2(r.amount)} ₽`
    case 'reason': return String(r.reason || '—')
    case 'valuation': return `${r.productValuation ?? '—'} ★`
    case 'user': return String(r.userName || 'Аноним')
    case 'cost': return r.f_cost ? `${fmt0(r.f_cost)} ₽/б` : '0'
    case 'text': {
      const parts = [r.text, r.pros ? `Плюсы: ${r.pros}` : '', r.cons ? `Минусы: ${r.cons}` : ''].filter(Boolean)
      return parts.length ? parts.join(' | ') : 'Оценка без текста'
    }
    case 'warehouse': return String(r.warehouse || '—')
    case 'total_price': return `${fmt2(r.total_price)} ₽`
    case 'total_units': return fmt0(r.total_units)
    case 'total': return `${fmt2(r.total)} ₽`
    case 'cnt': return fmt0(r.cnt)
    default: return ''
  }
}

const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.page-dashboard__popup-overlay { position: fixed; inset: 0; z-index: 1060; background: rgba(17,24,39,.5); display: flex; align-items: flex-start; justify-content: center; padding: 40px 16px; overflow: auto; }
.page-dashboard__popup-box { background: #fff; border-radius: 14px; max-width: 1100px; width: 100%; box-shadow: 0 12px 40px rgba(0,0,0,.28); padding: 16px 18px 18px; font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.page-dashboard__popup-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-dashboard__popup-title { font-size: 16px; font-weight: 700; color: #111827; }
.page-dashboard__popup-close { text-decoration: none; font-size: 14px; }
.page-dashboard__popup-state { margin: 0; }
.page-dashboard__popup-check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #555; margin-bottom: 6px; cursor: pointer; user-select: none; }
.page-dashboard__popup-note { font-size: 11px; color: #888; margin-bottom: 10px; }
.page-dashboard__popup-stats { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.page-dashboard__popup-stat { flex: 1 1 200px; background: #fff; border: 1px solid #e3e7eb; border-radius: 8px; padding: 12px 14px; }
.page-dashboard__popup-stat-val { font-size: 24px; font-weight: 700; color: #2c3e50; line-height: 1.2; }
.page-dashboard__popup-stat-cap { font-size: 11px; text-transform: uppercase; color: #7f8c8d; margin-top: 4px; font-weight: 600; }
.page-dashboard__popup-trunc { font-size: 12px; color: #7f8c8d; margin-bottom: 8px; }
.page-dashboard__popup-tablewrap { overflow-x: auto; max-height: 60vh; overflow-y: auto; }
.page-dashboard__popup-table { font-size: 12px; }
.page-dashboard__popup-th { background: #f8f9fa; color: #34495e; padding: 8px; vertical-align: middle; }
.page-dashboard__popup-table td { padding: 8px; vertical-align: middle; }
.page-dashboard__popup-date { color: #7f8c8d; font-size: 12px; white-space: nowrap; }
.page-dashboard__popup-sum { text-align: center; font-weight: 700; white-space: nowrap; }
.page-dashboard__popup-center { text-align: center; }
.page-dashboard__popup-empty { text-align: center; padding: 30px; color: #95a5a6; font-style: italic; }
</style>
