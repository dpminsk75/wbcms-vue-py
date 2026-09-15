<template>
  <!-- Запросы кампании, агрегированные по тексту (сырые строки wb_campaign_query идут по датам,
       сверху были бы только последние даты). В php грид queriesProvider вообще не рендерился,
       так что агрегация ничего 1в1 не ломает. Сортировка по колонкам, дефолт Заказы desc. -->
  <div v-if="rows.length" class="row mb-3" style="margin-top:20px">
    <div class="col-12"><div class="card wb-grid-card">
      <div class="card-header text-white d-flex justify-content-between align-items-center wb-card-header wb-card-header--sm">
        <span>Запросы ({{ agg.length }})</span>
        <button class="btn btn-sm btn-light wb-excel-btn--sm" @click="exportExcel" :disabled="!agg.length"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
      </div>
      <div class="expandable-container wb-table-wrap" :class="{'is-expanded': exp}" :style="{maxHeight: exp ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s'}">
        <table class="table table-bordered table-striped table-hover kv-grid-table mb-0 adv-grid">
          <thead><tr>
            <th @click="toggleSort('query')" style="min-width:280px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Запрос {{ arrow('query') }}</th>
            <th @click="toggleSort('views')" style="width:100px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Показы {{ arrow('views') }}</th>
            <th @click="toggleSort('clicks')" style="width:100px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Клики {{ arrow('clicks') }}</th>
            <th @click="toggleSort('atbs')" style="width:100px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Корзины {{ arrow('atbs') }}</th>
            <th @click="toggleSort('orders')" style="width:100px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Заказы {{ arrow('orders') }}</th>
            <th @click="toggleSort('sum')" style="width:100px; text-align:center; cursor:pointer; user-select:none; white-space:nowrap">Затраты, ₽ {{ arrow('sum') }}</th>
          </tr></thead>
          <tbody><tr v-for="r in sorted.slice(0, exp?500:10)" :key="r.query">
            <td style="padding:4px; white-space:normal; overflow-wrap:anywhere">{{ r.query }}</td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.views) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.clicks) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.atbs) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt0(r.orders) }}</td>
            <td style="text-align:right; padding:4px">{{ fmt2(r.sum) }}</td>
          </tr></tbody>
        </table>
      </div>
      <div v-if="sorted.length>10" class="expand-btn-wrapper" style="text-align:center; margin:10px 0 8px">
        <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="exp=!exp">{{ exp ? 'Свернуть' : 'Увидеть больше' }}</button>
      </div>
    </div></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
const props = defineProps<{ rows: any[], campaignId: string|number, dateFrom: string, dateTo: string }>()
const exp = ref(false)
type K = 'query'|'views'|'clicks'|'atbs'|'orders'|'sum'
const sortKey = ref<K>('orders')
const sortDir = ref<1|-1>(-1)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(v)||0)
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
  const XLSX = await import('xlsx')
  const data = sorted.value.map((r:any)=>({ 'Запрос': r.query, 'Дней': r.days, 'Показы': r.views, 'Клики': r.clicks, 'Корзины': r.atbs, 'Заказы': r.orders, 'Затраты': +Number(r.sum).toFixed(2) }))
  const ws = XLSX.utils.json_to_sheet(data)
  ws['!cols'] = [{wch:50},{wch:8},{wch:10},{wch:10},{wch:10},{wch:10},{wch:12}]
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Запросы'); XLSX.writeFile(wb, `adv-queries_${props.campaignId}_${props.dateFrom}_${props.dateTo}.xlsx`)
}
</script>
