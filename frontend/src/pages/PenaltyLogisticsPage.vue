<template>
  <div class="container-xxl page-penalty-logistics">
    <h1 class="page-title">Штрафы и потери на доставке</h1>

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

    <div class="page-penalty-logistics__blocks">
      <!-- Итого за период, по причинам -->
      <div class="tbl-card page-penalty-logistics__block">
        <div class="card__hd">
          <span>Итого за период</span>
          <span class="spacer"></span>
          <span class="hd-badge">Записей: {{ totals.total_count }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Причина</th>
                <th class="num">Кол-во</th>
                <th class="num">Сумма, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!period.length"><td colspan="3" class="page-penalty-logistics__empty">Нет данных за период</td></tr>
              <tr v-for="r in period" :key="r.bonus_type_name">
                <td class="t-left">{{ r.bonus_type_name }}</td>
                <td class="num">{{ r.items_count }}</td>
                <td class="num">{{ fmt2(r.total_sum) }}</td>
              </tr>
            </tbody>
            <tfoot v-if="period.length">
              <tr class="tbl__total">
                <td class="t-left">Итого</td>
                <td class="num">{{ totals.total_count }}</td>
                <td class="num">{{ fmt2(totals.total_sum) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Штрафы WB (отдельная операция «Штраф») -->
      <div class="tbl-card page-penalty-logistics__block">
        <div class="card__hd">
          <span>Штрафы WB</span>
          <span class="spacer"></span>
          <span class="hd-badge">Записей: {{ penalties.total_count }}</span>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th class="t-left">Причина</th>
                <th class="num">Кол-во</th>
                <th class="num">Сумма, ₽</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!penalties.rows.length"><td colspan="3" class="page-penalty-logistics__empty">Штрафов WB за период нет</td></tr>
              <tr v-for="r in penalties.rows" :key="r.bonus_type_name">
                <td class="t-left">{{ r.bonus_type_name }}</td>
                <td class="num">{{ r.items_count }}</td>
                <td class="num">{{ fmt2(r.total_sum) }}</td>
              </tr>
            </tbody>
            <tfoot v-if="penalties.rows.length">
              <tr class="tbl__total">
                <td class="t-left">Итого</td>
                <td class="num">{{ penalties.total_count }}</td>
                <td class="num">{{ fmt2(penalties.total_sum) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>

    <!-- Сводная по товарам -->
    <div class="tbl-card page-penalty-logistics__products">
      <div class="card__hd">
        <span>Сводная по товарам</span>
        <span class="spacer"></span>
        <span class="hd-badge">Товаров: {{ products.total }} · Стр {{ page }} / {{ totalPages }}</span>
        <ExcelButton :disabled="!products.rows.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить данные.</div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="num">Кол-во</th>
              <th class="num" title="Логистика К клиенту при отмене">Отмена (→)</th>
              <th class="num" title="Логистика ОБРАТНО: клиент отменил заказ">Отмена (←)</th>
              <th class="num" title="Возврат товара клиентом">Возврат (←)</th>
              <th class="num" title="Возврат брака">Брак</th>
              <th class="num" title="Прочие причины (корректировки и т.п.)">Прочее</th>
              <th class="num">Итого</th>
              <th class="t-center">Отчёт</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!products.rows.length"><td colspan="9" class="page-penalty-logistics__empty">Нет данных за период</td></tr>
            <tr v-for="r in products.rows" :key="r.nm_id">
              <td class="t-left">
                <ProductCell
                  :photo="r.photos"
                  :title="r.card_name"
                  :sub="subLine(r)"
                  :vendor="r.vendorCode"
                  :link="'/wb/detail?nm_id=' + r.nm_id"
                  :link-label="'WB: ' + r.nm_id"
                />
              </td>
              <td class="num">{{ r.items_count }}</td>
              <td class="num">{{ fmt2(r.sum_to_client_cancel) }}</td>
              <td class="num">{{ fmt2(r.sum_from_client_cancel) }}</td>
              <td class="num">{{ fmt2(r.sum_from_client_return) }}</td>
              <td class="num">{{ fmt2(r.sum_defect) }}</td>
              <td class="num">{{ fmt2(r.sum_other) }}</td>
              <td class="num">{{ fmt2(r.total_sum) }}</td>
              <td class="t-center">
                <a class="page-penalty-logistics__link" :href="detailUrl(r.nm_id)" target="_blank" title="Отчёт по штрафам товара"><i class="bi bi-file-earmark-text"></i></a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pager :page="page" :total-pages="totalPages" :total="products.total" @change="goPage" />
    </div>

    <!-- «Статистика по дням» в Yii2 была недостижимым блоком (AJAX target=days, кнопки нет) —
         в прототипе убрана. Метод summary_by_days остался в API на будущее. -->
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-penalty-logistics.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import WbUniversalFilter from '../components/common/WbUniversalFilter.vue'
import ProductCell from '../components/common/ProductCell.vue'
import ExcelButton from '../components/common/ExcelButton.vue'
import Pager from '../components/common/Pager.vue'

const route = useRoute()
const router = useRouter()

// локальное время (toISOString даёт UTC и сдвигает сутки)
// дефолт — ровно 7 суток (как пресет «7 дней» фильтра)
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const defaultDates = () => {
  const to = new Date()
  const from = new Date(to.getTime())
  from.setDate(from.getDate() - 6)
  return { date_from: iso(from), date_to: iso(to) }
}
const defaults = defaultDates()

const filters = ref({
  product: '',
  date_from: defaults.date_from,
  date_to: defaults.date_to,
  office_name: '',
  bonus_type_name: '',
})

const period = ref<any[]>([])
const products = ref<{ rows: any[], total: number }>({ rows: [], total: 0 })
const penalties = ref<{ rows: any[], total_sum: number }>({ rows: [], total_sum: 0 })
const totals = ref<{ total_sum: number, total_count: number, to_client_cancel_sum: number, from_client_cancel_sum: number, from_client_return_sum: number, defect_sum: number, other_sum: number }>({ total_sum: 0, total_count: 0, to_client_cancel_sum: 0, from_client_cancel_sum: 0, from_client_return_sum: 0, defect_sum: 0, other_sum: 0 })
const filterLists = ref<{ offices: string[], reasons: string[], doc_types: string[] }>({ offices: [], reasons: [], doc_types: [] })
const isLoading = ref(false)
const error = ref(false)
const page = ref(1)
const pageSize = 50

const totalPages = computed(() => Math.max(1, Math.ceil((products.value.total || 0) / pageSize)))

const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)

/** Подпись под названием товара: предмет и бренд одной строкой (как на остальных страницах). */
const subLine = (r: any) => {
  const subject = String(r.subject || '')
  const brandName = String(r.brand || '')
  if (subject && brandName) return subject + ' • ' + brandName
  return subject || brandName
}

const detailUrl = (nmId: number) =>
  `/wb-penalty/detail?nm_id=${nmId}&date_from=${filters.value.date_from}&date_to=${filters.value.date_to}`

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
  if (filters.value.office_name) p.set('office_name', filters.value.office_name)
  if (filters.value.bonus_type_name) p.set('bonus_type_name', filters.value.bonus_type_name)
  if (nmId) p.set('nm_id', nmId)
  return p
}

const fetchData = async (nmId: string) => {
  isLoading.value = true
  error.value = false
  try {
    const { data: d } = await api.get('/api/penalty/logistics', { params: buildQuery(nmId) })
    period.value = d.period || []
    products.value = d.products || { rows: [], total: 0 }
    penalties.value = d.penalties || { rows: [], total_sum: 0 }
    totals.value = d.totals || { total_sum: 0, total_count: 0, to_client_cancel_sum: 0, from_client_cancel_sum: 0, from_client_return_sum: 0, defect_sum: 0, other_sum: 0 }
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
  router.replace({ path: '/wb-penalty/logistics', query: q }).catch(() => {})
}

const onApply = async () => {
  page.value = 1
  const nmId = await resolveNmId(filters.value.product)
  syncRoute(nmId)
  fetchData(nmId)
  fetchFilterLists()
}
const onReset = () => {
  const d = defaultDates()
  filters.value = { product: '', date_from: d.date_from, date_to: d.date_to, office_name: '', bonus_type_name: '' }
  page.value = 1
  syncRoute('')
  fetchData('')
  fetchFilterLists()
}
const goPage = (p: number) => { page.value = Math.min(Math.max(1, p), totalPages.value); fetchData(currentNmId.value) }

const currentNmId = ref('')

const exportExcel = async () => {
  if (!products.value.rows.length) return
  const XLSX = await import('xlsx')
  const data = products.value.rows.map((r: any, i: number) => ({
    '#': i + 1,
    'Арт WB': r.nm_id,
    'Товар': r.card_name || '',
    'Кол-во': r.items_count,
    'Отмена (к клиенту), руб': r.sum_to_client_cancel,
    'Отмена (обратно), руб': r.sum_from_client_cancel,
    'Возврат, руб': r.sum_from_client_return,
    'Брак, руб': r.sum_defect,
    'Прочее, руб': r.sum_other,
    'Итого, руб': r.total_sum,
  }))
  data.push({
    '#': '', 'Арт WB': '', 'Товар': 'ИТОГО', 'Кол-во': '',
    'Отмена (к клиенту), руб': totals.value.to_client_cancel_sum,
    'Отмена (обратно), руб': totals.value.from_client_cancel_sum,
    'Возврат, руб': totals.value.from_client_return_sum,
    'Брак, руб': totals.value.defect_sum,
    'Прочее, руб': totals.value.other_sum,
    'Итого, руб': totals.value.total_sum,
  } as any)
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Потери')
  XLSX.writeFile(wb, `penalty_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
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
