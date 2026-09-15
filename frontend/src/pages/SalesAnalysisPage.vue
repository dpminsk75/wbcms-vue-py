<template>
  <div class="site-index container-xxl page-sales-analysis">
    <div class="row">
      <div class="nav_div col-md-2"><SideMenu /></div>
      <div class="col-md-10">
        <h1 class="mb-2 page-sales-analysis__title">ТОП Продаж WB</h1>
        <p class="page-sales-analysis__lede"><i> Данные по продажам с 1/09/2025 </i></p>

        <div class="card shadow-sm mb-4 card-body">
          <div class="row g-3 mb-3 page-sales-analysis__filters">
            <div class="col-md-4">
              <label class="form-label">Период</label>
              <div class="d-flex gap-2">
                <input type="date" v-model="dateFrom" class="form-control page-sales-analysis__date-input">
                <span class="page-sales-analysis__date-sep"> | </span>
                <input type="date" v-model="dateTo" class="form-control page-sales-analysis__date-input">
              </div>
            </div>
            <div class="btn-group col-md-3 page-sales-analysis__range-group">
              <button class="btn btn-outline-secondary btn-sm" @click="setRange('quarter')">Квартал</button>
              <button class="btn btn-outline-secondary btn-sm" @click="setRange('year')">Год</button>
              <button class="btn btn-outline-secondary btn-sm" @click="setRange('last_year')">Прошлый год</button>
            </div>
            <div class="col-md-2">
              <label class="form-label">Тип ТОПа</label>
              <select v-model="reportType" class="form-select">
                <option value="revenue">По выручке</option>
                <option value="qty">По количеству</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label">Показать ТОП</label>
              <select v-model.number="topLimit" class="form-select">
                <option :value="20">20</option><option :value="30">30</option><option :value="50">50</option><option :value="100">100</option>
              </select>
            </div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label fw-bold">Бренд</label>
              <select v-model="brand" class="form-select">
                <option value="">Все бренды</option>
                <option v-for="b in filterData?.brands" :key="b" :value="b">{{ b }}</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label fw-bold">Категория</label>
              <select v-model="category" class="form-select" id="category-id">
                <option value="">Выберите категорию...</option>
                <option v-for="c in filterData?.categories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label fw-bold">Тип</label>
              <select v-model="typeVal" class="form-select">
                <option value="">Ожидание категории...</option>
                <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label fw-bold">Страна</label>
              <select v-model="country" class="form-select" id="country-id">
                <option value="">Выберите страну...</option>
                <option v-for="c in filterData?.countries" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label fw-bold">Округ (для РФ)</label>
              <select v-model="oblast" class="form-select">
                <option value="">Необязательно...</option>
                <option v-for="o in oblasts" :key="o" :value="o">{{ o }}</option>
              </select>
            </div>
            <div class="col-md-4">
              <label class="form-label fw-bold">Регион</label>
              <select v-model="region" class="form-select">
                <option value="">Выберите регион...</option>
                <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
              </select>
            </div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-primary w-100" @click="refetch" :disabled="isLoading">{{ isLoading ? 'Загрузка...' : 'Сформировать' }}</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header text-white bg-wb d-flex justify-content-between align-items-center page-sales-analysis__result-head">
            <span>Результаты анализа продаж</span>
            <button class="btn btn-sm btn-light wb-excel-btn" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
          </div>
          <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
          <div v-else class="wb-table-wrap page-sales-analysis__table-wrap" ref="wrapRef">
            <table ref="tableRef" class="table table-bordered table-striped table-hover kv-grid-table mb-0 page-sales-analysis__table">
              <thead>
                <tr>
                  <th style="width:40px; min-width:40px; text-align:center">#</th>
                  <th style="width:95px; min-width:95px; text-align:center">Арт WB</th>
                  <th style="width:150px; min-width:120px; max-width:160px; text-align:center">Артикул</th>
                  <th style="min-width:280px; text-align:center">Товар</th>
                  <th style="width:70px; min-width:70px; text-align:center">Кол-во</th>
                  <th style="width:90px; min-width:90px; text-align:center">Выручка</th>
                  <th style="width:90px; min-width:90px; text-align:center">К оплате</th>
                  <th style="width:95px; min-width:95px; text-align:center">Цена со ск, ₽</th>
                  <th style="width:75px; min-width:75px; text-align:center">СПП, %</th>
                  <th style="width:85px; min-width:85px; text-align:center">Цена Прд, ₽</th>
                  <th style="width:85px; min-width:85px; text-align:center">К оплате, ₽</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="rows.length===0"><td colspan="11" class="text-center text-muted">Нет данных</td></tr>
                <tr v-for="(r,i) in rows" :key="r.nm_id">
                  <td class="page-sales-analysis__cell">{{ i+1 }}</td>
                  <td class="page-sales-analysis__cell page-sales-analysis__cell--center"><a :href="`/wb/detail?nm_id=${r.nm_id}&date_from=${dateFrom}&date_to=${dateTo}`" target="_blank" class="page-sales-analysis__nm-link">{{ r.nm_id }}</a></td>
                  <td class="page-sales-analysis__vendor" :title="r.vendorCode">{{ r.vendorCode }}</td>
                  <td class="page-sales-analysis__product-cell">
                    <div class="page-sales-analysis__product-name">{{ r.card_name }}</div>
                    <div class="page-sales-analysis__product-sub"><b>{{ r.brand }}</b> | {{ r.subject }} | {{ r.category }}</div>
                  </td>
                  <td class="page-sales-analysis__num--bold">{{ fmt0(r.sales_qty) }}</td>
                  <td class="page-sales-analysis__num">{{ fmt2(r.finished_sum) }}</td>
                  <td class="page-sales-analysis__num">{{ fmt2(r.for_pay_sum) }}</td>
                  <td class="page-sales-analysis__num">{{ fmt2(r.apwd) }}</td>
                  <td class="page-sales-analysis__num">{{ fmt1(r.aspp) }}</td>
                  <td class="page-sales-analysis__num--bold">{{ fmt2(r.afp) }}</td>
                  <td class="page-sales-analysis__num--bold">{{ fmt2(r.aforPay) }}</td>
                </tr>
              </tbody>
              <tfoot v-if="rows.length">
                <tr class="page-sales-analysis__totals">
                  <td colspan="4">Итого</td>
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
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/pages/page-sales-analysis.css'
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api/client'
import SideMenu from '../components/dashboard/SideMenu.vue'

const tableRef = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const enableResize = ()=>{
  const table = tableRef.value; if(!table) return
  const ths = table.querySelectorAll('th') as NodeListOf<HTMLTableCellElement>
  ths.forEach(th=>{
    if(th.querySelector('.col-resizer')) return
    th.style.position = 'relative'
    const r = document.createElement('div')
    r.className = 'col-resizer'
    r.style.cssText = 'position:absolute; top:0; right:0; width:6px; height:100%; cursor:col-resize; user-select:none; z-index:1'
    th.appendChild(r)
    let startX=0, startW=0
    const onMove = (e:MouseEvent)=>{
      const dx = e.clientX - startX
      const w = Math.max(40, startW + dx)
      th.style.width = w+'px'
      th.style.minWidth = w+'px'
      table.style.tableLayout = 'fixed'
      table.style.width = '100%'
    }
    const onUp = ()=>{
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
    }
    r.addEventListener('mousedown', (e:MouseEvent)=>{
      startX = e.clientX; startW = th.offsetWidth
      document.body.style.cursor = 'col-resize'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
      e.preventDefault()
    })
  })
  const fit = ()=>{
    if(!table) return
    table.style.width = '100%'
    table.style.tableLayout = 'fixed'
  }
  window.addEventListener('resize', fit)
  fit()
}

const today = new Date()
const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0,10)
const yesterday = new Date(Date.now()-864e5).toISOString().slice(0,10)

const dateFrom = ref(firstDay)
const dateTo = ref(yesterday)
const reportType = ref('revenue')
const topLimit = ref(20)
const brand = ref('')
const category = ref('')
const typeVal = ref('')
const country = ref('')
const oblast = ref('')
const region = ref('')

const setRange = (p:string)=>{
  const base = dateTo.value ? new Date(dateTo.value) : new Date()
  const fmt = (d:Date)=> d.toISOString().slice(0,10)
  let df = new Date(base)
  let nt: Date | null = null
  if(p==='year'){ df.setFullYear(base.getFullYear()-1); df.setDate(df.getDate()+1) }
  else if(p==='quarter'){ df.setMonth(base.getMonth()-3); df.setDate(df.getDate()+1) }
  else if(p==='last_year'){ const y=base.getFullYear()-1; df=new Date(y,0,1); nt=new Date(y,11,31) }
  dateFrom.value = fmt(df)
  if(nt) dateTo.value = fmt(nt)
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
})
const rows = computed(()=> Array.isArray(rowsRaw.value) ? rowsRaw.value : [])
const totals = computed(()=>{
  const s = (k:string)=> rows.value.reduce((a:number,r:any)=> a + (Number(r[k])||0),0)
  return { sales_qty: s('sales_qty'), finished_sum: s('finished_sum'), for_pay_sum: s('for_pay_sum') }
})
onMounted(()=> nextTick(enableResize))
watch(rows, ()=> nextTick(enableResize))
const refetch = ()=> doFetch()

const { data: filterData } = useQuery({
  queryKey: ['sales-filters'],
  queryFn: ()=> api.get('/api/sales-analysis/filters').then(r=>r.data),
  initialData: {brands:[], categories:[], types:[], countries:[]} as any,
})

const { data: oblastsRaw } = useQuery({
  queryKey: computed(()=> ['sales-districts', country.value] as const),
  queryFn: ()=> country.value==='Россия' ? api.get('/api/sales-analysis/districts', {params:{country: country.value}}).then(r=>r.data) : Promise.resolve([]),
  initialData: [] as any,
})
const oblasts = computed(()=> Array.isArray(oblastsRaw.value) ? oblastsRaw.value : [])

const { data: regionsRaw } = useQuery({
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
  // fallback из filterData
  return []
})
watch(category, ()=> { if(!category.value) typeVal.value='' })
watch(country, ()=> { if(country.value!=='Россия') oblast.value=''; region.value='' })

const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt1 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)

const exportExcel = async ()=>{
  if(!rows.value.length) return
  const XLSX = await import('xlsx')
  const data = rows.value.map((r:any,i:number)=> ({
    '#': i+1,
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
    '#': '', 'Арт WB': '', 'Артикул': '', 'Товар': 'ИТОГО', 'Бренд': '', 'Предмет': '', 'Категория': '',
    'Кол-во': totals.value.sales_qty, 'Выручка': totals.value.finished_sum, 'К оплате': totals.value.for_pay_sum,
    'Цена со ск': '', 'СПП %': '', 'Цена прод': '', 'К оплате шт': '',
  } as any)
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:4},{wch:12},{wch:14},{wch:32},{wch:14},{wch:16},{wch:16},{wch:8},{wch:12},{wch:12},{wch:10},{wch:8},{wch:10},{wch:10}]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'ТОП продаж')
  XLSX.writeFile(wb, `top-sales_${dateFrom.value}_${dateTo.value}.xlsx`)
}
</script>
