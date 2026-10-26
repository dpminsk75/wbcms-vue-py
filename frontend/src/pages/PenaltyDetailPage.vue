<template>
  <div class="container-xxl page-penalty-detail">
    <div class="mb-2">
      <a href="/wb-penalty/logistics" class="page-penalty-detail__link"><i class="bi bi-arrow-left me-1"></i>К сводке</a>
    </div>
    <h1 class="page-title">Детализация потерь на доставке</h1>

    <WbUniversalFilter
      v-model:date-from="filters.date_from"
      v-model:date-to="filters.date_to"
      v-model:product="filters.product"
      v-model:brand="filters.office_name"
      v-model:category="filters.bonus_type_name"
      :brands="filterLists.offices"
      :categories="filterLists.reasons"
      brand-label="Склад"
      category-label="Причина"
      @apply="onApply"
      @reset="onReset"
    />

    <!-- Итог по периоду: что вообще смотрим -->
    <div class="card wb-grid-card page-penalty-detail__summary">
      <div class="card-header text-white wb-card-header">
        <span>Итоги за период ({{ filters.date_from }} — {{ filters.date_to }})</span>
      </div>
      <div class="wb-table-wrap page-penalty-detail__summary-wrap">
        <table class="table table-bordered table-striped table-hover mb-0">
          <thead>
            <tr>
              <th class="page-penalty-detail__th-reason">Причина</th>
              <th class="page-penalty-detail__th-num">Записей</th>
              <th class="page-penalty-detail__th-sum">Сумма, ₽</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!byReason.length"><td colspan="3" class="page-penalty-detail__empty">Нет данных за период</td></tr>
            <tr v-for="r in byReason" :key="r.reason">
              <td>{{ r.reason }}</td>
              <td class="text-end">{{ r.items_count }}</td>
              <td class="text-end page-penalty-detail__sum">{{ fmt2(r.amount) }}</td>
            </tr>
          </tbody>
          <tfoot v-if="byReason.length">
            <tr class="page-penalty-detail__total-row">
              <td>Итого</td>
              <td class="text-end">{{ totalCount }}</td>
              <td class="text-end">{{ fmt2(totalSum) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- Построчные записи -->
    <div class="card wb-grid-card mt-3">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header">
        <span>Записи по строкам</span>
        <div class="d-flex align-items-center gap-2">
          <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!rows.length">
            <i class="bi bi-file-earmark-excel me-1"></i>Excel
          </button>
          <span class="text-white-50">Всего: {{ total }} · Стр {{ page }} / {{ totalPages }}</span>
        </div>
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить данные.</div>
      <div v-else class="wb-table-wrap page-penalty-detail__scroll">
        <table class="table table-bordered table-striped table-hover mb-0">
          <thead>
            <tr>
              <th class="page-penalty-detail__th-date">Дата</th>
              <th class="page-penalty-detail__th-nm">Арт. WB</th>
              <th class="page-penalty-detail__th-office">Склад</th>
              <th class="page-penalty-detail__th-reason">Причина</th>
              <th class="page-penalty-detail__th-sum">Сумма, ₽</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length"><td colspan="5" class="page-penalty-detail__empty">Нет данных за период</td></tr>
            <tr v-for="(r, i) in rows" :key="i">
              <td class="page-penalty-detail__date">{{ dt(r.rr_dt) }}</td>
              <td>
                <a class="page-penalty-detail__link" :href="`/wb/detail?nm_id=${r.nm_id}`" target="_blank">{{ r.nm_id }}</a>
              </td>
              <td class="page-penalty-detail__office" :title="r.office_name || ''">{{ r.office_name || '—' }}</td>
              <td class="page-penalty-detail__reason" :title="r.bonus_type_name || ''">{{ r.bonus_type_name }}</td>
              <td class="page-penalty-detail__sum">{{ fmt2(r.delivery_rub) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="total > pageSize" class="d-flex justify-content-center gap-2 p-2">
        <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1" @click="goPage(page - 1)">‹ Назад</button>
        <span class="align-self-center">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-sm btn-outline-secondary" :disabled="page >= totalPages" @click="goPage(page + 1)">Вперёд ›</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-penalty-detail.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'

const route = useRoute()
const router = useRouter()

const today = new Date()
const y = new Date(today); y.setDate(today.getDate() - 7)
const iso = (d: Date) => d.toISOString().slice(0, 10)

const filters = ref({
  product: '',
  date_from: iso(y),
  date_to: iso(today),
  office_name: '',
  bonus_type_name: '',
})

const rows = ref<any[]>([])
const byReason = ref<any[]>([])
const total = ref(0)
const isLoading = ref(false)
const error = ref(false)
const page = ref(1)
const pageSize = 50
const currentNmId = ref('')
const filterLists = ref<{ offices: string[], reasons: string[], doc_types: string[] }>({ offices: [], reasons: [], doc_types: [] })

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))
const totalSum = computed(() => byReason.value.reduce((a: number, r: any) => a + (Number(r.amount) || 0), 0))
const totalCount = computed(() => byReason.value.reduce((a: number, r: any) => a + (Number(r.items_count) || 0), 0))

const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
const dt = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T]?(\d{2}:\d{2})?/.exec(iso || '')
  if (!m) return iso || '—'
  return m[4] ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}` : `${m[3]}.${m[2]}.${m[1]}`
}

// WbUniversalFilter даёт свободную маску (nm_id/артикул/название) — резолвим в nm_id
const resolveNmId = async (mask: string): Promise<string> => {
  const q = String(mask || '').trim()
  if (!q) return ''
  try {
    const { data } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    const list: any[] = Array.isArray(data) ? data : []
    const exact = list.find((c: any) => String(c.nmID) === q || String(c.vendorCode || '') === q)
    if (exact) return String(exact.nmID)
    return list.length === 1 ? String(list[0].nmID) : ''
  } catch {
    return ''
  }
}

const buildQuery = (nmId: string) => {
  const p = new URLSearchParams()
  p.set('date_from', filters.value.date_from)
  p.set('date_to', filters.value.date_to)
  p.set('page', String(page.value))
  p.set('page_size', String(pageSize))
  if (nmId) p.set('nm_id', nmId)
  if (filters.value.office_name) p.set('office_name', filters.value.office_name)
  if (filters.value.bonus_type_name) p.set('bonus_type_name', filters.value.bonus_type_name)
  return p
}

const fetchData = async (nmId: string) => {
  isLoading.value = true
  error.value = false
  try {
    const { data: d } = await api.get('/api/penalty/detail', { params: buildQuery(nmId) })
    rows.value = d.rows || []
    total.value = d.total || 0
    // сводка по причинам — тот же срез, отдельным запросом попапов (быстрый)
    const { data: pop } = await api.get('/api/penalty/popup', {
      params: { date_from: filters.value.date_from, date_to: filters.value.date_to, ...(nmId ? { nm_id: nmId } : {}) },
    })
    byReason.value = pop?.by_reason || []
  } catch {
    error.value = true
  } finally {
    isLoading.value = false
  }
}

const fetchFilterLists = async () => {
  try {
    const { data: d } = await api.get('/api/penalty/filter-lists', {
      params: { date_from: filters.value.date_from, date_to: filters.value.date_to },
    })
    filterLists.value = { offices: d.offices || [], reasons: d.reasons || [], doc_types: d.doc_types || [] }
  } catch {
    filterLists.value = { offices: [], reasons: [], doc_types: [] }
  }
}

const syncRoute = (nmId: string) => {
  const q: Record<string, string> = {}
  if (filters.value.date_from) q.date_from = filters.value.date_from
  if (filters.value.date_to) q.date_to = filters.value.date_to
  if (nmId) q.nm_id = nmId
  if (filters.value.office_name) q.office_name = filters.value.office_name
  if (filters.value.bonus_type_name) q.bonus_type_name = filters.value.bonus_type_name
  router.replace({ path: '/wb-penalty/detail', query: q }).catch(() => {})
}

const onApply = async () => {
  page.value = 1
  const nmId = await resolveNmId(filters.value.product)
  currentNmId.value = nmId
  syncRoute(nmId)
  fetchData(nmId)
  fetchFilterLists()
}
const onReset = () => {
  filters.value = { product: '', date_from: iso(y), date_to: iso(today), office_name: '', bonus_type_name: '' }
  currentNmId.value = ''
  page.value = 1
  syncRoute('')
  fetchData('')
  fetchFilterLists()
}
const goPage = (p: number) => { page.value = Math.min(Math.max(1, p), totalPages.value); fetchData(currentNmId.value) }

const exportExcel = async () => {
  if (!rows.value.length) return
  const XLSX = await import('xlsx')
  const data = rows.value.map((r: any, i: number) => ({
    '#': i + 1,
    'Дата': dt(r.rr_dt),
    'Арт WB': r.nm_id,
    'Склад': r.office_name || '',
    'Причина': r.bonus_type_name,
    'Сумма, руб': r.delivery_rub,
  }))
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Детализация')
  XLSX.writeFile(wb, `penalty_detail_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}

const initFromQuery = () => {
  const q: any = route.query
  if (q.date_from) filters.value.date_from = String(q.date_from)
  if (q.date_to) filters.value.date_to = String(q.date_to)
  if (q.nm_id) { currentNmId.value = String(q.nm_id); filters.value.product = String(q.nm_id) }
  if (q.office_name) filters.value.office_name = String(q.office_name)
  if (q.bonus_type_name) filters.value.bonus_type_name = String(q.bonus_type_name)
}

onMounted(() => { initFromQuery(); fetchData(currentNmId.value); fetchFilterLists() })
watch(() => route.query, () => { initFromQuery(); page.value = 1; fetchData(currentNmId.value) })
</script>
