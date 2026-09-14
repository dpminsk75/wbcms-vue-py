<template>
  <div class="div_bordered" style="padding:0; overflow:hidden">
    <div class="card-header text-white" style="background: linear-gradient(97.26deg,#002fa7 .49%,#0046c7 14.88%,#005ce6 29.27%,#0072ff 43.14%,#008cff 57.02%,#00a4ff 70.89%,#00bcff 84.76%,#00d2ff 99.15%); padding:10px 15px; font-size:12px; font-weight:700; border-radius:12px 12px 0 0; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
      Сумма заказов за последние 30 дней
    </div>
    <div v-if="isLoading" class="p-3 text-center text-muted" style="font-size:12px">Загрузка...</div>
    <table v-else class="table table-striped table-bordered table-hover kv-grid-table mb-0" style="font-size:12px; margin:0; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
      <thead>
        <tr style="background:#f8f7fb; font-size:12px">
          <th style="padding:6px 8px; text-align:left; font-weight:600; width:180px">Показатель</th>
          <th style="padding:6px 8px; text-align:right; width:110px">Вчера</th>
          <th style="padding:6px 8px; text-align:right; width:110px">Позавчера</th>
          <th style="padding:6px 8px; text-align:right; width:130px">Прошедшие 7 дней</th>
          <th style="padding:6px 8px; text-align:right; width:130px">Предыдущая неделя</th>
          <th style="padding:6px 8px; text-align:right; width:130px">Прошедшие 30 дней</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.price_type" style="font-size:12px">
          <td style="padding:6px 8px; font-weight:500">{{ r.price_type }}</td>
          <td style="padding:6px 8px; text-align:right">{{ fmt2(r.ieri) }}</td>
          <td style="padding:6px 8px; text-align:right">{{ fmt2(r.pazyera) }}</td>
          <td style="padding:6px 8px; text-align:right">{{ fmt2(r.past_7_days) }}</td>
          <td style="padding:6px 8px; text-align:right; color:#64748b">{{ fmt2(r.week_before) }}</td>
          <td style="padding:6px 8px; text-align:right; font-weight:600">{{ fmt2(r.past_30_days) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
const { data: rows, isLoading } = useQuery({ queryKey:['orders-summary'], queryFn: dashboardApi.ordersSummary as any })
const fmt2 = (v:any)=> new Intl.NumberFormat('ru-RU', {minimumFractionDigits:2, maximumFractionDigits:2}).format(v||0)
</script>
