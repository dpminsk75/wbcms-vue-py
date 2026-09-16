<template>
  <div class="container-xxl page-top-products-vxe">
    <h1 class="page-title">{{ $route.meta.title || 'ТОП товаров за период' }}</h1>
    <p class="text-muted small mb-3">Пилот vxe-table — оригинал не тронут (<code>/wb-profit/top-products</code>). Оценка: виртуал-скролл на ТОП-1000, ресайз из коробки, футер-итоги.</p>

    <!-- Фильтры 1в1 с TopProductsPage.vue:6-47 (локальные, без WbFilterBar — ключа nm_id нет) -->
    <div class="card page-top-products-vxe__filter-card card-body mb-4 shadow-sm">
      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label fw-bold">Период анализа</label>
          <div class="d-flex gap-2 align-items-center">
            <input type="date" v-model="filters.date_from" class="form-control">
            <span>|</span>
            <input type="date" v-model="filters.date_to" class="form-control">
          </div>
        </div>
        <div class="col-md-3">
          <label class="form-label fw-bold">Сортировать по</label>
          <select v-model="filters.sort_by" class="form-select">
            <option value="qnt">Количеству продаж (шт)</option>
            <option value="amount">Выручке (руб)</option>
            <option value="net_profit">По итогу от WB (руб)</option>
            <option value="clean_margin">Марже после налогов (руб)</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label fw-bold">Показать товаров</label>
          <select v-model.number="filters.limit" class="form-select">
            <option :value="20">ТОП-20</option>
            <option :value="50">ТОП-50</option>
            <option :value="200">ТОП-200</option>
            <option :value="500">ТОП-500</option>
            <option :value="1000">ТОП-1000</option>
          </select>
        </div>
        <div class="col-md-3 d-flex gap-2">
          <button class="btn btn-primary flex-grow-1" :disabled="isLoading" @click="refetch">
            <i class="bi bi-filter me-1"></i> Применить
          </button>
          <button class="btn btn-light" title="Сбросить" @click="resetFilters">
            <i class="bi bi-arrow-counterclockwise"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Таблица-пилот -->
    <div class="card shadow-sm">
      <div class="card-header text-white bg-wb-green-deep-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-crown me-2"></i>ТОП-{{ filters.limit }} товаров (vxe)</h5>
        <div class="d-flex gap-2">
          <span class="badge bg-light text-dark align-self-center">{{ filters.date_from }} — {{ filters.date_to }}</span>
          <button class="btn btn-sm btn-light wb-excel-btn" :disabled="!rows.length" @click="exportExcel">
            <i class="bi bi-file-earmark-excel me-1"></i> Excel
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div v-if="isLoading" class="text-center p-5">
          <div class="spinner-border text-primary" role="status"></div>
          <div class="mt-2 text-muted">Загрузка данных...</div>
        </div>
        <div v-else class="page-top-products-vxe__table-wrap">
          <vxe-table
            :data="rows"
            class="page-top-products-vxe__grid"
            height="620"
            border
            stripe
            round
            size="mini"
            show-footer
            auto-resize
            show-overflow="title"
            show-header-overflow="title"
            show-footer-overflow="title"
            :footer-method="footerMethod"
            :footer-cell-class-name="footerCellClass"
            :cell-class-name="cellClass"
            :header-cell-class-name="headerCellClass"
            :column-config="{ resizable: true }"
            :row-config="{ isHover: true, keyField: 'nm_id' }"
            :scroll-y="{ enabled: true, gt: 100 }"
          >
            <vxe-column title="Товар" :width="200" :show-overflow="false">
              <template #default="{ row }">
                <div class="page-top-products-vxe__product">
                  <div class="cart-item-title" :title="row.title || ''">{{ formatTitle(row.title) }}</div>
                  <div class="page-top-products-vxe__sub">{{ row.brand || '' }} • {{ row.vendor_code || '' }}</div>
                  <div class="page-top-products-vxe__sub">
                    <a :href="`/wb/detail?nm_id=${row.nm_id}`" target="_blank" class="page-top-products-vxe__wb-link">WB: {{ row.nm_id }}</a>
                  </div>
                </div>
              </template>
            </vxe-column>
            <!-- v2: тест Gemini — у цифр нет width (auto): vxe делит остаток поровну, min-width 40 как пол -->
            <vxe-column field="qnt" title="Кол-во" :min-width="40" align="center" sortable :formatter="fmt0col" />
            <vxe-column field="amount" title="Выручка" :min-width="40" align="right" sortable :formatter="fmt0col" />
            <vxe-column field="commission" title="Ком. WB" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_acquiring_fee" title="Экв." :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_delivery" title="Лог-ка" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_penalty" title="Штрафы" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_otziv" title="Отзывы" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_adv" title="Реклама" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="f_cashback" title="Кэшбек" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="net_profit" title="Итого" :min-width="40" align="right" sortable :formatter="fmt0col" :class-name="netClass" />
            <vxe-column field="total_nds" title="НДС" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="total_cost" title="Себ-ть" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="profit_before_tax" title="Прибыль" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="tax_amount" title="Налог (7%)" :min-width="40" align="right" :formatter="fmt0col" />
            <vxe-column field="clean_margin" title="Маржа" :min-width="40" align="right" sortable :formatter="fmt0col" :class-name="marginClass" />
            <vxe-column field="amount_per_item" title="Цена" :min-width="40" align="right" :formatter="fmt2col" />
            <vxe-column field="profit_per_item" title="Итог/шт" :min-width="40" align="right" :formatter="fmt2col" />
            <!-- последняя без width: единственный флекс, добирает остаток ширины -->
            <vxe-column field="clear_per_item" title="Маржа/шт" :min-width="40" align="right" :formatter="fmt2col" />
          </vxe-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-top-products-vxe.css'
import 'vxe-table/lib/style.css'
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { VxeTable, VxeColumn } from 'vxe-table'
import { api } from '@/api/client'

// Локальная регистрация для пилота (main.ts не трогаем — чанк грузится только с этой страницей).
// VxeTable/VxeColumn импортированы top-level: <script setup> сам резолвит их в шаблоне как <vxe-table>/<vxe-column>.

const today = new Date()
const defTo = today.toISOString().slice(0, 10)
const defFrom = new Date(today.getTime() - 30 * 864e5).toISOString().slice(0, 10)

const filters = ref({ date_from: defFrom, date_to: defTo, sort_by: 'qnt', limit: 20 })

const { data: rowsRaw, isLoading, refetch } = useQuery({
  queryKey: computed(() => ['top-products-vxe', filters.value.date_from, filters.value.date_to, filters.value.sort_by, filters.value.limit]),
  queryFn: () => api.get('/api/wb-profit/top-products', { params: filters.value }).then((r) => r.data),
  initialData: [] as any[],
})

const rows = computed(() => (Array.isArray(rowsRaw.value) ? rowsRaw.value : []))
const totals = computed(() => {
  const sum = (k: string) => rows.value.reduce((a, r) => a + (Number(r[k]) || 0), 0)
  return {
    qnt: sum('qnt'), amount: sum('amount'), commission: sum('commission'),
    f_acquiring_fee: sum('f_acquiring_fee'), f_delivery: sum('f_delivery'),
    f_penalty: sum('f_penalty'), f_otziv: sum('f_otziv'), f_adv: sum('f_adv'),
    f_cashback: sum('f_cashback'), net_profit: sum('net_profit'), total_nds: sum('total_nds'),
    total_cost: sum('total_cost'), profit_before_tax: sum('profit_before_tax'),
    tax_amount: sum('tax_amount'), clean_margin: sum('clean_margin'),
  }
})

const resetFilters = () => {
  filters.value = { date_from: defFrom, date_to: defTo, sort_by: 'qnt', limit: 20 }
}

const formatTitle = (s: string) => {
  if (!s) return '—'
  return s.replace(/([:,.])(?=[^\s])/ug, '$1 ')
}
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
const fmt0col = ({ cellValue }: any) => fmt0(cellValue)
const fmt2col = ({ cellValue }: any) => fmt2(cellValue)

// Подсветка как в оригинале: text-danger/text-success через class-name vxe
const netClass = ({ row }: any) => (Number(row.net_profit) < 0 ? 'text-danger fw-bold' : 'text-success fw-bold')
const marginClass = ({ row }: any) => (Number(row.clean_margin) < 0 ? 'text-danger fw-bold' : 'text-success fw-bold')
const cellClass = ({ column }: any) => {
  if (column.field === 'net_profit') return 'page-top-products-vxe__net-cell'
  if (column.field === 'profit_before_tax') return 'page-top-products-vxe__profit-cell'
  if (column.field === 'clean_margin') return 'page-top-products-vxe__margin-cell'
  if (['amount_per_item', 'profit_per_item', 'clear_per_item'].includes(column.field)) return 'page-top-products-vxe__per-item'
  return ''
}
const headerCellClass = ({ column }: any) => {
  if (column.field === 'net_profit') return 'page-top-products-vxe__net-cell'
  if (column.field === 'profit_before_tax') return 'page-top-products-vxe__profit-cell'
  if (column.field === 'clean_margin') return 'page-top-products-vxe__margin-cell'
  if (['amount_per_item', 'profit_per_item', 'clear_per_item'].includes(column.field)) return 'page-top-products-vxe__per-item'
  return ''
}
const footerCellClass = () => 'page-top-products-vxe__footer-cell'

// Футер-итоги 1в1 с tfoot оригинала (первая колонка — текст; колонки #: нет, удалена)
const footerMethod = () => {
  const t = totals.value as Record<string, number>
  const foot = ['Итого по ТОПу:']
  const order = ['qnt', 'amount', 'commission', 'f_acquiring_fee', 'f_delivery', 'f_penalty', 'f_otziv', 'f_adv', 'f_cashback', 'net_profit', 'total_nds', 'total_cost', 'profit_before_tax', 'tax_amount', 'clean_margin', '', '', '']
  // Товар-колонка уже занята первым элементом
  for (const k of order) foot.push(k ? fmt0(t[k]) : '')
  return [foot]
}

// Excel 1в1 с TopProductsPage.vue:274-329 (динамический xlsx, русские шапки, ИТОГО-строка)
const exportExcel = async () => {
  if (!rows.value.length) return
  const XLSX = await import('xlsx')
  const data = rows.value.map((r, i) => ({
    '#': i + 1, 'Арт WB': r.nm_id, 'Артикул': r.vendor_code, 'Наименование': r.title, 'Бренд': r.brand,
    'Кол-во': r.qnt, 'Выручка': r.amount, 'Ком. WB': r.commission, 'Экв.': r.f_acquiring_fee,
    'Лог-ка': r.f_delivery, 'Штрафы': r.f_penalty, 'Отзывы': r.f_otziv, 'Реклама': r.f_adv,
    'Кэшбек': r.f_cashback, 'Итого': r.net_profit, 'НДС': r.total_nds, 'Себ-ть': r.total_cost,
    'Прибыль': r.profit_before_tax, 'Налог (7%)': r.tax_amount, 'Маржа': r.clean_margin,
    'Цена/шт': r.amount_per_item, 'Итог/шт': r.profit_per_item, 'Маржа/шт': r.clear_per_item,
  }))
  data.push({
    '#': '', 'Арт WB': '', 'Артикул': '', 'Наименование': 'ИТОГО', 'Бренд': '',
    'Кол-во': totals.value.qnt, 'Выручка': totals.value.amount, 'Ком. WB': totals.value.commission,
    'Экв.': totals.value.f_acquiring_fee, 'Лог-ка': totals.value.f_delivery, 'Штрафы': totals.value.f_penalty,
    'Отзывы': totals.value.f_otziv, 'Реклама': totals.value.f_adv, 'Кэшбек': totals.value.f_cashback,
    'Итого': totals.value.net_profit, 'НДС': totals.value.total_nds, 'Себ-ть': totals.value.total_cost,
    'Прибыль': totals.value.profit_before_tax, 'Налог (7%)': totals.value.tax_amount, 'Маржа': totals.value.clean_margin,
    'Цена/шт': null, 'Итог/шт': null, 'Маржа/шт': null,
  } as any)
  const ws = XLSX.utils.json_to_sheet(data)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'ТОП товаров (vxe)')
  XLSX.writeFile(wb, `top-products-vxe_${filters.value.date_from}_${filters.value.date_to}.xlsx`)
}
</script>
