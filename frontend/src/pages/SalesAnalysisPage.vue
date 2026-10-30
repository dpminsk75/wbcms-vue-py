<template>
  <div class="container-xxl page-sales-analysis">
    <h1 class="page-sales-analysis__title">ТОП Продаж WB</h1>
    <p class="page-sales-analysis__lede"><i>Данные по продажам с 1/09/2025</i></p>

    <!-- Фильтры: даты — общим WbDateRangeFilter (7/14/30/90/365/с начала года) -->
    <div class="wb-panel page-sales-analysis__filters">
      <div class="wb-panel__bd">
        <div class="page-sales-analysis__row-top">
          <WbDateRangeFilter v-model:from="dateFrom" v-model:to="dateTo" default-preset="30" bare @apply="onDates" />
          <div class="wb-field">
            <label class="wb-field__label">Тип ТОПа</label>
            <select v-model="reportType" class="wb-input">
              <option value="revenue">По выручке</option>
              <option value="qty">По количеству</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Показать ТОП</label>
            <select v-model.number="topLimit" class="wb-input">
              <option :value="20">20</option><option :value="30">30</option><option :value="50">50</option><option :value="100">100</option>
            </select>
          </div>
        </div>

        <div class="page-sales-analysis__grid">
          <div class="wb-field">
            <label class="wb-field__label">Бренд</label>
            <select v-model="brand" class="wb-input">
              <option value="">Все бренды</option>
              <option v-for="b in filterData?.brands" :key="b" :value="b">{{ b }}</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Категория</label>
            <select v-model="category" class="wb-input" id="category-id">
              <option value="">Выберите категорию...</option>
              <option v-for="c in filterData?.categories" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Тип</label>
            <select v-model="typeVal" class="wb-input">
              <option value="">Ожидание категории...</option>
              <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>

        <div class="page-sales-analysis__grid">
          <div class="wb-field">
            <label class="wb-field__label">Страна</label>
            <select v-model="country" class="wb-input" id="country-id">
              <option value="">Выберите страну...</option>
              <option v-for="c in filterData?.countries" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Округ (для РФ)</label>
            <select v-model="oblast" class="wb-input" :disabled="oblastsLoading">
              <option value="">Необязательно...</option>
              <option v-for="o in oblasts" :key="o" :value="o">{{ o }}</option>
            </select>
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Регион</label>
            <select v-model="region" class="wb-input" :disabled="regionsLoading">
              <option value="">Выберите регион...</option>
              <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
            </select>
          </div>
        </div>

        <div class="page-sales-analysis__actions">
          <button class="btn btn--brand" @click="refetch" :disabled="isLoading">{{ isLoading ? 'Загрузка...' : 'Сформировать' }}</button>
          <button class="btn btn--outline" @click="resetFilters" :disabled="isLoading">Сбросить</button>
        </div>
      </div>
    </div>

    <div class="tbl-card">
      <div class="card__hd">
        <span>Результаты анализа продаж</span>
        <span class="spacer"></span>
        <ExcelButton :disabled="!rows.length" @click="exportExcel" />
      </div>
      <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
      <div v-else class="tbl-wrap" ref="wrapRef">
        <table ref="tableRef" class="tbl" style="width:100%; table-layout:auto">
          <thead>
            <tr>
              <th class="t-left">Товар</th>
              <th class="t-center">Кол-во</th>
              <th class="t-center">Выручка</th>
              <th class="t-center">К оплате</th>
              <th class="t-center">Цена со ск, ₽</th>
              <th class="t-center">СПП, %</th>
              <th class="t-center">Цена Прд, ₽</th>
              <th class="t-center">К оплате, ₽</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length"><td colspan="8" class="text-center text-muted">Нет данных</td></tr>
            <tr v-for="r in rows" :key="r.nm_id">
              <td class="t-left">
                <ProductCell
                  :photo="r.photos"
                  :title="r.card_name"
                  :sub="subLine(r)"
                  :vendor="r.vendorCode"
                  :link="wbLink(r)"
                  :link-label="'WB: ' + r.nm_id"
                />
              </td>
              <td>{{ fmt0(r.sales_qty) }}</td>
              <td>{{ fmt2(r.finished_sum) }}</td>
              <td>{{ fmt2(r.for_pay_sum) }}</td>
              <td>{{ fmt2(r.apwd) }}</td>
              <td>{{ fmt1(r.aspp) }}</td>
              <td>{{ fmt2(r.afp) }}</td>
              <td>{{ fmt2(r.aforPay) }}</td>
            </tr>
          </tbody>
          <tfoot v-if="rows.length">
            <tr class="tbl__total">
              <td class="t-left">Итого</td>
              <td>{{ fmt0(totals.sales_qty) }}</td>
              <td>{{ fmt2(totals.finished_sum) }}</td>
              <td>{{ fmt2(totals.for_pay_sum) }}</td>
              <td colspan="4"></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-sales-analysis.css'
import { ref, computed, watch, onMounted } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api/client'
import WbDateRangeFilter from '../components/common/WbDateRangeFilter.vue'
import ProductCell from '../components/common/ProductCell.vue'
import ExcelButton from '../components/common/ExcelButton.vue'
import { useTableResize } from '../composables/useTableResize'
import { useNumFmt } from '../composables/useNumFmt'
import { exportXlsx } from '../utils/exportXlsx'

const { fmt0, fmt1, fmt2 } = useNumFmt()

const tableRef = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
useTableResize(tableRef, { storeKey: 'sales-analysis' })

// локальное время (toISOString даёт UTC и сдвигает сутки)
const fmtD = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const today = new Date()
const start30 = new Date(today); start30.setDate(start30.getDate() - 29)

const dateFrom = ref(fmtD(start30))
const dateTo = ref(fmtD(today))
const reportType = ref('revenue')
const topLimit = ref(20)
const brand = ref('')
const category = ref('')
const typeVal = ref('')
const country = ref('')
const oblast = ref('')
const region = ref('')

/** Пресеты дат из WbDateRangeFilter — только смена периода, запрос по кнопке «Сформировать». */
const onDates = (p: { from: string, to: string }) => {
  dateFrom.value = p.from
  dateTo.value = p.to
}

const q = computed(()=> ({
  date_from: dateFrom.value, date_to: dateTo.value, report_type: reportType.value,
  top_limit: topLimit.value, brand: brand.value || undefined,
  category: category.value || undefined, type: typeVal.value || undefined,
  country: country.value || undefined, region: region.value || undefined, oblast: oblast.value || undefined,
}))

const { data: rowsRaw, isLoading, refetch: doFetch } = useQuery({
  queryKey: computed(()=> ['sales-top', dateFrom.value, dateTo.value, reportType.value, topLimit.value, brand.value, category.value, typeVal.value, country.value, oblast.value, region.value] as const),
  queryFn: ()=> api.get('/api/sales-analysis/top', {params: q.value}).then(r=>r.data),
  initialData: [] as any,
  enabled: false, // тяжелый топ — только по «Сформировать», а не на каждое движение фильтров
})
const rows = computed(()=> Array.isArray(rowsRaw.value) ? rowsRaw.value : [])
const totals = computed(()=>{
  const s = (k:string)=> rows.value.reduce((a:number,r:any)=> a + (Number(r[k])||0),0)
  return { sales_qty: s('sales_qty'), finished_sum: s('finished_sum'), for_pay_sum: s('for_pay_sum') }
})
onMounted(()=> { doFetch() })
const refetch = ()=> doFetch()

/** Сброс фильтров к значениям по умолчанию (стандарт темы: «Сбросить» в каждом отчёте). */
const resetFilters = ()=>{
  dateFrom.value = fmtD(start30)
  dateTo.value = fmtD(today)
  reportType.value = 'revenue'
  topLimit.value = 20
  brand.value = ''
  category.value = ''
  typeVal.value = ''
  country.value = ''
  oblast.value = ''
  region.value = ''
  doFetch()
}

const { data: filterData } = useQuery({
  queryKey: ['sales-filters'],
  queryFn: ()=> api.get('/api/sales-analysis/filters').then(r=>r.data),
  initialData: {brands:[], categories:[], types:[], countries:[]} as any,
})

const { data: oblastsRaw, isFetching: oblastsLoading } = useQuery({
  queryKey: computed(()=> ['sales-districts', country.value] as const),
  queryFn: ()=> country.value==='Россия' ? api.get('/api/sales-analysis/districts', {params:{country: country.value}}).then(r=>r.data) : Promise.resolve([]),
  initialData: [] as any,
})
const oblasts = computed(()=> Array.isArray(oblastsRaw.value) ? oblastsRaw.value : [])

const { data: regionsRaw, isFetching: regionsLoading } = useQuery({
  queryKey: computed(()=> ['sales-regions', country.value, oblast.value] as const),
  queryFn: ()=> country.value ? api.get('/api/sales-analysis/regions', {params:{country: country.value, oblast: oblast.value}}).then(r=>r.data) : Promise.resolve([]),
  initialData: [] as any,
})
const regions = computed(()=> Array.isArray(regionsRaw.value) ? regionsRaw.value : [])

const { data: typesRaw } = useQuery({
  queryKey: computed(()=> ['sales-types', category.value] as const),
  queryFn: ()=> category.value ? api.get('/api/sales-analysis/types', {params:{category: category.value}}).then(r=>r.data) : Promise.resolve([]),
  initialData: [] as any,
})
const types = computed(()=> {
  const v = typesRaw.value as any
  if(Array.isArray(v) && v.length) return v
  return filterData.value?.types || []
})
watch(category, ()=> { if(!category.value) typeVal.value='' })
watch(country, ()=> { if(country.value!=='Россия') oblast.value=''; region.value='' })

/** Подпись под названием товара: предмет и бренд одной строкой. */
const subLine = (r: any) => {
  const subject = String(r.subject || '')
  const brandName = String(r.brand || '')
  if (subject && brandName) return subject + ' • ' + brandName
  return subject || brandName
}

/** Ссылка на карточку WB с текущим периодом. */
const wbLink = (r: any) => `/wb/detail?nm_id=${r.nm_id}&date_from=${dateFrom.value}&date_to=${dateTo.value}`

const exportExcel = async ()=>{
  if(!rows.value.length) return
  const data = rows.value.map((r:any)=> ({
    'Арт WB': r.nm_id,
    'Артикул': r.vendorCode,
    'Товар': r.card_name,
    'Бренд': r.brand,
    'Предмет': r.subject,
    'Категория': r.category,
    'Кол-во': r.sales_qty,
    'Выручка': r.finished_sum,
    'К оплате': r.for_pay_sum,
    'Цена со ск': r.apwd,
    'СПП %': r.aspp,
    'Цена прод': r.afp,
    'К оплате шт': r.aforPay,
  }))
  // итого
  data.push({
    'Арт WB': '', 'Артикул': '', 'Товар': 'ИТОГО', 'Бренд': '', 'Предмет': '', 'Категория': '',
    'Кол-во': totals.value.sales_qty, 'Выручка': totals.value.finished_sum, 'К оплате': totals.value.for_pay_sum,
    'Цена со ск': '', 'СПП %': '', 'Цена прод': '', 'К оплате шт': '',
  } as any)
  await exportXlsx({
    rows: data,
    filename: `top-sales_${dateFrom.value}_${dateTo.value}.xlsx`,
    sheetName: 'ТОП продаж',
    cols: [{wch:12},{wch:14},{wch:32},{wch:14},{wch:16},{wch:16},{wch:8},{wch:12},{wch:12},{wch:10},{wch:8},{wch:10},{wch:10}],
  })
}
</script>
