<template>
  <div v-if="busy || hasData || isError">
    <div class="expandable-container" :class="{'is-expanded': expanded}" :style="{maxHeight: expanded ? '20000px' : '250px', overflow:'hidden', position:'relative', transition:'max-height .5s', border:'1px solid #e0e0e0', borderRadius:'12px', background:'#fff'}">
      <div class="card-header d-flex justify-content-between align-items-center text-white" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); padding:10px 15px; font-size:13px; font-weight:700; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
        <span>
          <router-link :to="`/feed?date_from=${dateFrom}&date_to=${dateTo}`" class="text-white" style="text-decoration:none">Заказы (с {{ fmtDate(dateFrom) }}) <i class="bi bi-eye-fill ms-1" style="font-size:11px"></i></router-link>
          <a :href="`/wb-order/feed-aggregated?DPFilterForm%5Bdate_from%5D=${dateFrom}&DPFilterForm%5Bdate_to%5D=${dateTo}`" target="_blank" class="text-white ms-2" style="text-decoration:underline; font-weight:500; font-size:11px"><i class="bi bi-graph-up me-1"></i>Топ</a>
        </span>
        <span style="font-weight:400; font-size:11px; opacity:.9">Показаны 1-{{ displayRows.length }} из {{ totalItems }} записи.</span>
      </div>
      <table class="table table-striped table-bordered table-hover kv-grid-table mb-0" style="font-size:12px; margin:0; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
        <thead>
          <tr style="background:#f8f7fb; font-size:12px">
            <th style="padding:6px 8px; text-align:left; width:420px">Товар / Артикул</th>
            <th style="padding:6px 8px; text-align:center; width:90px">Кол-во</th>
            <th style="padding:6px 8px; text-align:right; width:90px">Σ в РЦ</th>
            <th style="padding:6px 8px; text-align:right; width:90px">Σ к опл</th>
            <th style="padding:6px 8px; text-align:right; width:70px">Цена</th>
            <th style="padding:6px 8px; text-align:right; width:60px">СПП, %</th>
            <th style="padding:6px 8px; text-align:right; width:80px">Цена пр.</th>
          </tr>
        </thead>
        <tbody>
          <tr class="table-warning kv-page-summary w0" style="font-weight:700; font-size:13px; text-align:right">
            <td style="padding:6px 8px; color:#7c1af8">Итого {{ totalCnt }} зак | Сумма в РЦ: {{ fmt1(totalPwd) }} | Заказы: {{ fmt1(totalFp) }}</td>
            <td style="padding:6px 8px; text-align:center; color:#7c1af8">{{ totalCnt }}</td>
            <td style="padding:6px 8px; text-align:right">{{ fmt1(totalPwd) }}</td>
            <td style="padding:6px 8px; text-align:right">{{ fmt0(totalFp) }}</td>
            <td style="padding:6px 8px"></td>
            <td style="padding:6px 8px"></td>
            <td style="padding:6px 8px"></td>
          </tr>
          <tr v-for="r in displayRows" :key="r.nm_id" style="font-size:12px">
            <td style="padding:5px 8px">
              <div style="color:#1D1B2A; font-weight:500; line-height:13px">{{ r.title }}</div>
              <div style="color:#6E6A80; font-size:10px; margin-top:2px">Артикул: {{ r.vendorCode }} &nbsp; Арт WB: <span style="color:#7c1af8">{{ r.nm_id }}</span></div>
            </td>
            <td style="padding:5px 8px; text-align:center; color:#7c1af8; font-weight:700">{{ r.cnt }}<br><small style="color:#6E6A80; font-weight:400; font-size:10px">{{ r.cnt_3 }} | {{ r.cnt_2 }} | {{ r.cnt_1 }} | {{ r.cnt_0 }}</small></td>
            <td style="padding:5px 8px; text-align:right">{{ fmt1(r.pwd) }}</td>
            <td style="padding:5px 8px; text-align:right">{{ fmt0(r.fp) }}</td>
            <td style="padding:5px 8px; text-align:right">{{ Math.round(r.apwd||0).toLocaleString('ru-RU') }}</td>
            <td style="padding:5px 8px; text-align:right">{{ (r.aspp||0).toFixed(1) }}</td>
            <td style="padding:5px 8px; text-align:right; font-weight:700">{{ Math.round(r.afp||0).toLocaleString('ru-RU') }}</td>
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
const { data: raw, isLoading, isFetching, isError } = useQuery({
  queryKey: computed(() => ['last-orders', props.dateFrom, props.dateTo, auth.companyId] as const),
  queryFn: ()=> (dashboardApi as any).lastOrders({dateFrom: props.dateFrom, dateTo: props.dateTo}),
  initialData: {items:[], totals:{cnt:0,pwd:0,fp:0}} as any
})
const busy = computed(() => isLoading.value || isFetching.value)
// бэкенд возвращает {items, totals}; legacy — массив
const items = computed(()=> Array.isArray(raw.value) ? raw.value as any[] : (raw.value?.items as any[] ?? []))
const totals = computed(()=> Array.isArray(raw.value) ? null : (raw.value?.totals as any ?? null))
const displayRows = computed(()=> items.value.slice(0,20))
// итоги по всем заказам за даты (отдельный agg), fallback — reduce по items для legacy
const totalCnt = computed(()=> totals.value ? totals.value.cnt : items.value.reduce((s:number,r:any)=>s+(r.cnt||0),0))
const totalPwd = computed(()=> totals.value ? totals.value.pwd : items.value.reduce((s:number,r:any)=>s+(r.pwd||0),0))
const totalFp = computed(()=> totals.value ? totals.value.fp : items.value.reduce((s:number,r:any)=>s+(r.fp||0),0))
const totalItems = computed(()=> items.value.length)
const hasData = computed(()=> items.value.length > 0 || (totals.value?.cnt || 0) > 0)
watchEffect(() => { if (!busy.value) report('last-orders', hasData.value || !!isError.value) })
const fmt1 = (v:any)=> new Intl.NumberFormat('ru-RU', {minimumFractionDigits:1, maximumFractionDigits:1}).format(v||0)
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(v||0))
const fmtDate = (d:string)=> d ? new Date(d).toLocaleDateString('ru-RU',{day:'numeric', month:'short', year:'numeric'}) : ''
</script>
<style scoped>
.expandable-container:not(.is-expanded)::after{content:""; position:absolute; bottom:0; left:0; width:100%; height:50px; background:linear-gradient(transparent, white); pointer-events:none}
</style>
