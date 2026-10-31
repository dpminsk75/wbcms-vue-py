<template>
  <div class="tbl-card tbl-card--compact">
    <div class="card__hd">
      <span><i class="bi bi-graph-up me-2"></i> {{ heading ?? 'Динамика позиций' }}</span>
      <span class="spacer"></span>
      <button v-if="showExcel" class="hd-btn" @click="exportExcel" :disabled="!rows.length"><i class="bi bi-file-earmark-excel me-1"></i> Excel</button>
    </div>
    <div v-if="isLoading" class="text-center p-4"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
    <div v-else id="grid-scroll" class="tbl-wrap phrases-matrix" ref="wrapRef">
      <table ref="tbl" class="tbl phrases-matrix__table">
        <thead>
          <tr>
            <template v-if="props.mode === 'by-card'">
              <th class="t-left phrases-matrix__sticky phrases-matrix__sticky--product phrases-matrix__sort" @click="sortBy('title')">
                Товар / Позиция <span v-if="sortKey==='title'">{{ sortDir==='asc' ? '▲' : '▼' }}</span><span v-else>⇅</span>
              </th>
            </template>
            <template v-else>
              <th class="t-left phrases-matrix__sticky phrases-matrix__sort" @click="sortBy('phrase')">
                Поисковый запрос <span v-if="sortKey==='phrase'">{{ sortDir==='asc' ? '▲' : '▼' }}</span><span v-else>⇅</span>
              </th>
              <th class="num phrases-matrix__col--freq">Ср. част</th>
            </template>
            <th class="num phrases-matrix__col--num">Клики</th>
            <th class="num phrases-matrix__col--num">Заказы</th>
            <th v-for="d in dates" :key="d" class="num phrases-matrix__col--day">{{ d }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length"><td :colspan="4+dates.length" class="text-center text-muted">Нет данных</td></tr>
          <tr
            v-for="r in sortedRows"
            :key="props.mode === 'by-card' ? r.nmID : r.phrase"
            class="clickable-row"
            :class="{ 'selected-row': sel === (props.mode === 'by-card' ? String(r.nmID) : r.phrase) }"
            @click="sel = props.mode === 'by-card' ? String(r.nmID) : r.phrase"
          >
            <template v-if="props.mode === 'by-card'">
              <!-- Карточка товара — общий блок ProductCell (компактный: фото 30×40) -->
              <td class="t-left phrases-matrix__sticky phrases-matrix__sticky--product">
                <ProductCell
                  :photo="r.photos"
                  :title="r.title"
                  :sub="r.subject"
                  :brand="r.brand"
                  :vendor="r.vendor_code"
                  :link="'/wb/detail?nm_id=' + r.nmID"
                  :link-label="'WB: ' + r.nmID"
                  compact
                />
              </td>
            </template>
            <template v-else>
              <td class="t-left phrases-matrix__sticky">
                <a class="wb-query-link" :href="'https://www.wildberries.ru/catalog/0/search.aspx?search=' + encodeURIComponent(r.phrase)" target="_blank" rel="noopener">{{ r.phrase }}</a>
              </td>
              <td class="num col-dim">{{ r.avg_freq ?? '' }}</td>
            </template>
            <td class="num col-dim">{{ r.total_clicks ?? '' }}</td>
            <td class="num col-accent">{{ r.total_orders ?? '' }}</td>
            <td v-for="d in dates" :key="d" :class="cellCls(r,d)" :title="cellTitle(r,d)" class="phrases-matrix__day">{{ cellPos(r,d) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { api } from '@/api/client'
import { exportXlsx } from '@/utils/exportXlsx'
import ProductCell from './ProductCell.vue'
const props = withDefaults(defineProps<{
  rows: any[]
  dates: string[] // uniqueDates yyyy-mm-dd
  isLoading?: boolean
  showExcel?: boolean // в /wb-search/* Excel не было — скрывать кнопкой
  mode?: 'by-phrase' | 'by-card' // by-card: строки=карточки (phrase.php зеркальная матрица)
  heading?: string | null // by-card: «Товары по запросу: {phrase}»
}>(), { isLoading:false, showExcel:true, mode:'by-phrase', heading:null })
const tbl = ref<HTMLTableElement|null>(null)
const wrapRef = ref<HTMLDivElement|null>(null)
const sel = ref('')
// сортировка как phraseDataProvider в WbController.php:878 (дефолт total_orders DESC)
const sortKey = ref<'phrase'|'nmID'|'title'|'avg_freq'|'total_clicks'|'total_orders'>('total_orders')
const sortDir = ref<'asc'|'desc'>('desc')
const sortedRows = computed(()=>{
  const arr=[...props.rows]
  const k=sortKey.value, d=sortDir.value==='asc'?1:-1
  arr.sort((a:any,b:any)=>{
    if(k==='phrase' || k==='title') return String(a[k]||'').localeCompare(String(b[k]||''),'ru')*d
    return ((Number(a[k])||0)-(Number(b[k])||0))*d
  })
  return arr
})
const sortBy=(k:'phrase'|'nmID'|'title'|'avg_freq'|'total_clicks'|'total_orders')=>{
  if(sortKey.value===k) sortDir.value=sortDir.value==='asc'?'desc':'asc'
  else{ sortKey.value=k; sortDir.value= (k==='phrase'||k==='title')?'asc':'desc' }
}
const cellData = (r:any,d:string)=> r[d] ?? null
const cellPos = (r:any,d:string)=> cellData(r,d)?.pos ?? ''
const cellTitle = (r:any,d:string)=> { const o=cellData(r,d)?.orders; return o>0?`Заказов: ${o}`:'' }
const cellCls = (r:any,d:string)=>{
  const data=cellData(r,d); if(!data) return ''
  const c:string[]=[]
  const p=data.pos||0, o=data.orders||0
  if(p>0 && p<=10) c.push('pos-top-10')
  else if(p>10 && p<=50) c.push('pos-top-50')
  if(o>0) c.push('has-orders')
  return c.join(' ')
}
watch(()=>props.rows, ()=> nextTick(()=>{}))
onMounted(()=>{})
const fetchPhrases = async () => {
  if (!props.nmId || !props.dateFrom || !props.dateTo) return
  isLoading.value = true
  try {
    const { data:j } = await api.get(`/api/wb/detail/phrases?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    rows.value = j.models || []
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}
onMounted(fetchPhrases)
const exportExcel = async()=>{
  if(!props.rows.length) return
  const data=sortedRows.value.map((r:any)=>{
    if(props.mode==='by-card'){
      const base:any={'Арт WB':r.nmID,'Товар':r.title,'Клики':r.total_clicks,'Заказы':r.total_orders}
      props.dates.forEach((d:string)=> base[d] = cellPos(r,d))
      return base
    }
    const base:any={'Поисковый запрос':r.phrase,'Ср част':r.avg_freq,'Клики':r.total_clicks,'Заказы':r.total_orders}
    props.dates.forEach((d:string)=> base[d] = cellPos(r,d))
    return base
  })
  const first=props.dates[0]||'', last=props.dates[props.dates.length-1]||''
  await exportXlsx({
    rows: data,
    filename: props.mode==='by-card' ? `phrase-cards_${first}_${last}.xlsx` : `phrases_${first}_${last}.xlsx`,
    sheetName: props.mode==='by-card' ? 'Товары' : 'Фразы',
    cols: [
      { wch: props.mode==='by-card' ? 12 : 40 }, { wch: props.mode==='by-card' ? 40 : 10 },
      { wch: 10 }, { wch: 10 },
      ...props.dates.map(() => ({ wch: 12 })),
    ],
  })
}
</script>
<style scoped>
/* Матрица фраз/карточек — плотная таблица темы: липкая шапка, липкая первая колонка,
   свои градации позиции. Селекторы — по id (#grid-scroll), чтобы перебить зебру темы
   без !important (правило §8.1.9). */
.phrases-matrix { max-height: 70vh; overflow: auto; position: relative; }
/* ширины колонок: таблица по содержимому (без min-width:100%), иначе лишнее
   место расписывается по колонкам и «Ср. част / Клики / Заказы» разъезжаются */
.phrases-matrix__table { table-layout: auto; width: auto; display: table; overflow: visible; }

/* липкая шапка */
#grid-scroll thead th { position: sticky; top: 0; z-index: 10; background: var(--surface); }

/* липкая первая колонка */
#grid-scroll .phrases-matrix__sticky {
  position: sticky; left: 0; z-index: 5;
  background: var(--surface);
  box-shadow: inset -1px 0 0 var(--line-strong);
}
#grid-scroll tbody tr:nth-child(even) .phrases-matrix__sticky { background: var(--surface-2); }
#grid-scroll thead th.phrases-matrix__sticky { z-index: 11; }
/* первая колонка: фраза (режим by-phrase) — 220px, перенос по словам */
#grid-scroll .phrases-matrix__sticky { width: 220px; min-width: 200px; max-width: 320px; white-space: normal; }
/* колонка товара (режим by-card) */
#grid-scroll .phrases-matrix__sticky--product { width: 300px; min-width: 300px; }

/* ширины колонок */
#grid-scroll .phrases-matrix__col--num { width: 68px; white-space: nowrap; }
#grid-scroll .phrases-matrix__col--freq { width: 80px; white-space: nowrap; }
/* колонки дней: подпись YYYY-MM-DD */
#grid-scroll .phrases-matrix__col--day { min-width: 64px; padding: 4px 2px; font-size: 11px; white-space: nowrap; }
#grid-scroll td.phrases-matrix__day { padding: 4px 2px; font-size: 11px; text-align: center; }
#grid-scroll .phrases-matrix__sort { cursor: pointer; user-select: none; white-space: nowrap; }

/* подсветка позиций — цвета темы */
#grid-scroll tbody td.pos-top-10 { background: var(--good-tint); color: var(--good-deep); font-weight: 600; }
#grid-scroll tbody td.pos-top-50 { background: var(--warn-tint); color: var(--warn-deep); }
/* ячейка с заказом — жирный шрифт */
#grid-scroll tbody td.has-orders { font-weight: 800; }
/* приглушённые колонки «Ср. част» и «Клики» */
#grid-scroll tbody td.col-dim { background: var(--surface-2); }
#grid-scroll tbody td.col-accent { background: var(--brand-tint); }
/* выбранная строка — 34% акцента + жирный текст */
#grid-scroll tbody tr.selected-row > td { background: color-mix(in srgb, var(--brand) 34%, var(--surface)); color: var(--ink); font-weight: 700; }
/* курсор кликабельной строки */
#grid-scroll tbody tr.clickable-row { cursor: pointer; }
</style>
