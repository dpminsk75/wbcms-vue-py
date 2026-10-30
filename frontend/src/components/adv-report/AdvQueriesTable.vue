<template>
  <!-- Запросы кампании, агрегированные по тексту (сырые строки wb_campaign_query идут по датам,
       сверху были бы только последние даты). В php грид queriesProvider вообще не рендерился,
       так что агрегация ничего 1в1 не ломает. Сортировка по колонкам, дефолт Заказы desc. -->
  <div v-if="rows.length" class="tbl-card">
    <div class="card__hd">
      <span>Запросы ({{ agg.length }})</span>
      <span class="spacer"></span>
      <ExcelButton :disabled="!agg.length" @click="exportExcel" />
    </div>
    <div class="expandable-container tbl-wrap" :class="{ 'is-expanded': exp }">
      <table class="tbl" style="width:100%; table-layout:auto">
        <thead><tr>
          <th class="page-adv-report__th-sort" @click="toggleSort('query')">Запрос {{ arrow('query') }}</th>
          <th class="t-center page-adv-report__th-sort" @click="toggleSort('views')">Показы {{ arrow('views') }}</th>
          <th class="t-center page-adv-report__th-sort" @click="toggleSort('clicks')">Клики {{ arrow('clicks') }}</th>
          <th class="t-center page-adv-report__th-sort" @click="toggleSort('atbs')">Корзины {{ arrow('atbs') }}</th>
          <th class="t-center page-adv-report__th-sort" @click="toggleSort('orders')">Заказы {{ arrow('orders') }}</th>
          <th class="t-center page-adv-report__th-sort" @click="toggleSort('sum')">Затраты, ₽ {{ arrow('sum') }}</th>
        </tr></thead>
        <tbody><tr v-for="r in sorted.slice(0, exp?500:3)" :key="r.query">
          <td class="t-left page-adv-report__query">{{ r.query }}</td>
          <td class="num">{{ fmt0(r.views) }}</td>
          <td class="num">{{ fmt0(r.clicks) }}</td>
          <td class="num">{{ fmt0(r.atbs) }}</td>
          <td class="num">{{ fmt0(r.orders) }}</td>
          <td class="num">{{ fmt2(r.sum) }}</td>
        </tr></tbody>
      </table>
    </div>
    <!-- Кнопка — если строк больше трёх -->
    <div v-if="exp || sorted.length > 3" class="expand-btn-wrapper page-adv-report__more-wrap">
      <button class="btn btn--outline btn-sm page-adv-report__more-btn" @click="exp=!exp">{{ exp ? 'Свернуть' : 'Увидеть больше' }}</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import ExcelButton from '../common/ExcelButton.vue'
import { useNumFmt } from '@/composables/useNumFmt'
import { exportXlsx } from '@/utils/exportXlsx'

const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const exp = ref(false)
const { fmt0, fmt2 } = useNumFmt()
type K = 'query'|'views'|'clicks'|'atbs'|'orders'|'sum'
const sortKey = ref<K>('orders')
const sortDir = ref<1|-1>(-1)
// агрегация по тексту запроса за весь период: суммы + число дней, когда запрос встречался
const agg = computed(()=>{
  const m = new Map<string, any>()
  for(const r of props.rows){
    const q = String(r.query ?? r.name ?? '—')
    let a = m.get(q)
    if(!a){ a = {query:q, days:new Set<string>(), views:0, clicks:0, atbs:0, orders:0, sum:0}; m.set(q, a) }
    if(r.date) a.days.add(String(r.date).slice(0,10))
    a.views += Number(r.views)||0; a.clicks += Number(r.clicks)||0; a.atbs += Number(r.atbs)||0; a.orders += Number(r.orders)||0; a.sum += Number(r.sum)||0
  }
  return [...m.values()].map(a=> ({...a, days: a.days.size}))
})
const sorted = computed(()=>{
  const k = sortKey.value, d = sortDir.value
  return [...agg.value].sort((a,b)=>{
    if(k==='query') return a.query.localeCompare(b.query,'ru') * d
    return ((Number(a[k])||0) - (Number(b[k])||0)) * d
  })
})
const toggleSort = (k:K)=>{ if(sortKey.value===k) sortDir.value = sortDir.value===1 ? -1 : 1; else { sortKey.value = k; sortDir.value = k==='query' ? 1 : -1 } }
const arrow = (k:K)=> sortKey.value!==k ? '⇅' : (sortDir.value===1 ? '↑' : '↓')

const exportExcel = async()=>{
  if(!sorted.value.length) return
  const data = sorted.value.map((r:any)=>({ 'Запрос': r.query, 'Дней': r.days, 'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Затраты': +Number(r.sum).toFixed(2) }))
  await exportXlsx({
    rows: data,
    filename: `adv-queries_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`,
    sheetName: 'Запросы',
    cols: [{wch:50},{wch:8},{wch:10},{wch:10},{wch:10},{wch:10},{wch:12}],
  })
}
</script>
