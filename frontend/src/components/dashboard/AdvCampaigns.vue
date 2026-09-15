<template>
  <div v-if="busy || hasData || isError">
    <div class="expandable-container" :class="{'is-expanded': expanded}" :style="{maxHeight: expanded ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s', border:'1px solid #e0e0e0', borderRadius:'12px', background:'#fff'}">
      <div class="card-header d-flex justify-content-between align-items-center text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); padding:10px 15px; font-size:13px; font-weight:700; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
        <span>Реклама (с {{ fmtDate(dateFrom) }})</span>
        <span style="font-weight:400; font-size:11px; opacity:.9">Показаны 1-{{ displayRows.length }} из {{ rows.length }} записи.</span>
      </div>
      <table class="table table-striped table-bordered table-hover kv-grid-table mb-0" style="font-size:12px; margin:0; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
        <thead>
          <tr style="background:#f8f7fb; font-size:12px">
            <th @click="sortBy('name')" style="padding:6px 8px; text-align:center; cursor:pointer; user-select:none; width:200px">Кампания <span v-if="sortKey==='name'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            <th @click="sortBy('status')" style="padding:6px 8px; text-align:center; cursor:pointer; width:60px">Ст <span v-if="sortKey==='status'">{{ sortDir==='asc'?'▲':'▼' }}</span><span v-else>⇅</span></th>
            <th style="padding:6px 8px; text-align:center">Показы</th>
            <th style="padding:6px 8px; text-align:center">Клики</th>
            <th style="padding:6px 8px; text-align:center">Корзины</th>
            <th style="padding:6px 8px; text-align:center">Заказы</th>
            <th style="padding:6px 8px; text-align:center">Отмена</th>
            <th style="padding:6px 8px; text-align:center">CTR, %</th>
            <th style="padding:6px 8px; text-align:center">CR, %</th>
            <th style="padding:6px 8px; text-align:center">Затраты, ₽</th>
            <th style="padding:6px 8px; text-align:center">CPM, ₽</th>
            <th style="padding:6px 8px; text-align:center">CPC, ₽</th>
            <th style="padding:6px 8px; text-align:center">CPO ₽</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in displayRows" :key="r.campaign_id" style="font-size:12px">
            <td style="padding:4px 8px; color:#7c1af8; font-weight:500; white-space:nowrap"><a :href="'/wb-adv-report/index?id='+r.campaign_id" target="_blank" style="color:#7c1af8; text-decoration:none">{{ r.name }}</a></td>
            <td style="padding:4px 8px; text-align:center"><span style="display:inline-block; padding:2px 6px; border-radius:4px; font-size:11px; background:#e8f5e9; color:#2e7d32; border:1px solid #c8e6c9">{{ statusLabel(r.status) }}</span></td>
            <td style="padding:4px 8px; text-align:right">{{ fmt(r.views) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ fmt(r.clicks) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ fmt(r.atbs) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ fmt(r.orders) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ fmt(r.canceled) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ ctr(r) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ cr(r) }}</td>
            <td style="padding:4px 8px; text-align:right; font-weight:600">{{ fmt2(r.sum) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ cpm(r) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ cpc(r) }}</td>
            <td style="padding:4px 8px; text-align:right">{{ cpo(r) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="expand-btn-wrapper" style="text-align:center; margin:10px 0 20px">
      <button class="btn btn-outline-primary btn-sm" style="font-size:12px; padding:4px 16px; border-radius:6px" @click="expanded=!expanded">{{ expanded ? 'Свернуть' : 'Увидеть больше' }}</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, inject, watchEffect } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'
const props = defineProps<{dateFrom:string, dateTo:string}>()
const auth = useAuthStore()
const report = inject<(n:string,h:boolean)=>void>('dashReport', ()=>{})
const expanded = ref(false)
const sortKey = ref<'name'|'status'|null>(null)
const sortDir = ref<'asc'|'desc'>('asc')
const { data: rows, isLoading, isFetching, isError } = useQuery({ queryKey: computed(() => ['adv', props.dateFrom, props.dateTo, auth.companyId] as const), queryFn: ()=> (dashboardApi as any).adv({dateFrom: props.dateFrom, dateTo: props.dateTo}), initialData: [] as any })
const hasData = computed(() => ((rows.value as any[]) || []).length > 0)
const busy = computed(() => isLoading.value || isFetching.value)
watchEffect(() => { if (!busy.value) report('adv', hasData.value || !!isError.value) })
const sorted = computed(()=>{
  const arr = [...(rows.value as any[])]
  if(sortKey.value==='name') { arr.sort((a,b)=> sortDir.value==='asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)); return arr }
  if(sortKey.value==='status') { arr.sort((a,b)=> sortDir.value==='asc' ? a.status-b.status : b.status-a.status); return arr }
  const prio = (s:number)=> s===9?1 : s===11?2 : s===7?4 : s===4?5 : s===-1?6 : 5
  arr.sort((a,b)=> prio(a.status)-prio(b.status) || a.name.localeCompare(b.name))
  return arr
})
const displayRows = computed(()=> expanded.value ? sorted.value : sorted.value.slice(0,10))
const sortBy = (k:'name'|'status')=>{ if(sortKey.value===k) sortDir.value = sortDir.value==='asc'?'desc':'asc'; else { sortKey.value=k; sortDir.value='asc' } }
const fmt = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(v||0))
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU', {minimumFractionDigits:2, maximumFractionDigits:2}).format(v||0)
const ctr = (r:any)=> r.views ? (r.clicks/r.views*100).toFixed(2) : '0.00'
const cr = (r:any)=> r.clicks ? (r.atbs/r.clicks*100).toFixed(2) : '0.00'
const cpm = (r:any)=> r.views ? (r.sum/r.views*1000).toFixed(2) : '0.00'
const cpc = (r:any)=> r.clicks ? (r.sum/r.clicks).toFixed(2) : '0.00'
const cpo = (r:any)=> r.orders ? (r.sum/r.orders).toFixed(2) : '0.00'
const statusMap: Record<string,string> = {'9':'Активна','7':'Завершена','11':'Пауза','8':'Отклонена','4':'Готова','-1':'Удалена'}
const statusLabel = (s:number|string)=> statusMap[String(s)] || String(s)
const fmtDate = (d:string)=> d ? new Date(d).toLocaleDateString('ru-RU',{day:'numeric', month:'short', year:'numeric'}) : ''
</script>
<style scoped>
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, white); pointer-events:none}
</style>
