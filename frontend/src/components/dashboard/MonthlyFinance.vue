<template>
  <div>
    <div style="border:1px solid #e0e0e0; border-radius:12px; background:#fff; overflow:hidden">
      <div class="card-header d-flex justify-content-between align-items-center text-white bg-wb-blue-header" style="padding:10px 15px; font-size:13px; font-weight:700; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
        <span>Финансовая аналитика (с 2025 года)</span>
        <span style="font-weight:400; font-size:11px; opacity:.85">{{ rows.length }} мес.</span>
      </div>
      <div v-if="isLoading" style="padding:16px; font-size:12px; text-align:center">Загрузка...</div>
      <div v-else style="overflow-x:auto">
        <table class="table table-striped table-bordered table-hover kv-grid-table mb-0" style="font-size:11px; margin:0; white-space:nowrap; font-family:&quot;Segoe UI&quot;,Roboto,Helvetica,Arial,sans-serif">
          <thead>
            <tr style="background:#f8f7fb">
              <th style="padding:5px 6px; text-align:center; min-width:80px">Месяц</th>
              <th style="padding:5px 6px; text-align:center">Кол-во</th>
              <th style="padding:5px 6px; text-align:center; font-weight:700">Продажи</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Ком. WB</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Эквайринг</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Приёмка</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b; font-weight:500">Логистика</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Хранение</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Штрафы</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Удержан.</th>
              <th style="padding:5px 6px; text-align:center; color:#16a085">Отзывы</th>
              <th style="padding:5px 6px; text-align:center; color:#2980b9">Реклама</th>
              <th style="padding:5px 6px; text-align:center; color:#c0392b">Кэшбек</th>
              <th style="padding:5px 6px; text-align:center; background:#e8f8f5; font-weight:700">Общий итог</th>
              <th style="padding:5px 6px; text-align:center">НДС</th>
              <th style="padding:5px 6px; text-align:center">Себ-ть</th>
              <th style="padding:5px 6px; text-align:center; background:#fcf3cf; font-weight:700">Прибыль</th>
              <th style="padding:5px 6px; text-align:center; color:#d35400">Налог 7%</th>
              <th style="padding:5px 6px; text-align:center; background:#d4efdf; font-weight:700">Маржа</th>
            </tr>
          </thead>
          <tbody>
            <!-- pageSummary Итого -->
            <tr class="table-warning" style="font-weight:700; background:#fff3cd">
              <td style="padding:5px 6px; text-align:center">Итого</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(totals.qnt) }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(totals.amount) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.commission) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_acquiring_fee) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_acceptance) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_delivery) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_storage_fee) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_penalty) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_deduction) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#16a085">{{ fmt0(totals.f_otziv) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#2980b9">{{ fmt0(totals.f_adv) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(totals.f_cashback) }}</td>
              <td style="padding:5px 6px; text-align:right; background:#f4fbf7; color:#27ae60">{{ fmt0(totals.net_profit) }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(totals.total_nds) }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(totals.total_cost) }}</td>
              <td style="padding:5px 6px; text-align:right; background:#fefde7">{{ fmt0(totals.profit_before_tax) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#e67e22">{{ fmt0(totals.tax_amount) }}</td>
              <td style="padding:5px 6px; text-align:right; background:#eaf2f8; color:#196f3d">{{ fmt0(totals.clean_margin) }}</td>
            </tr>
            <tr v-for="r in rows" :key="r.month" style="font-size:11px">
              <td style="padding:5px 6px; text-align:center; font-weight:700; color:#2c3e50">{{ r.month }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(r.qnt) }}</td>
              <td style="padding:5px 6px; text-align:right; font-weight:700">{{ fmt0(r.amount) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.commission) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_acquiring_fee) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_acceptance) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b; font-weight:500">{{ fmt0(r.f_delivery) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_storage_fee) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_penalty) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_deduction) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#16a085; font-weight:600">{{ fmt0(r.f_otziv) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#2980b9">{{ fmt0(r.f_adv) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#c0392b">{{ fmt0(r.f_cashback) }}</td>
              <td style="padding:5px 6px; text-align:right; font-weight:700; color:#27ae60; background:#f4fbf7">{{ fmt0(r.net_profit) }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(r.total_nds) }}</td>
              <td style="padding:5px 6px; text-align:right">{{ fmt0(r.total_cost) }}</td>
              <td style="padding:5px 6px; text-align:right; font-weight:700; background:#fefde7">{{ fmt0(r.profit_before_tax) }}</td>
              <td style="padding:5px 6px; text-align:right; color:#e67e22">{{ fmt0(r.tax_amount) }}</td>
              <td style="padding:5px 6px; text-align:right; font-weight:700; color:#196f3d; background:#eaf2f8">{{ fmt0(r.clean_margin) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
const { data: rowsRaw, isLoading } = useQuery({ queryKey:['monthly-finance'], queryFn: ()=> (dashboardApi as any).monthly(), initialData: [] as any })
const rows = computed(()=> (rowsRaw.value as any[]) ?? [])
const totals = computed(()=>{
  const sum = (k:string)=> rows.value.reduce((s:number,r:any)=> s + (Number(r[k])||0), 0)
  return {
    qnt: sum('qnt'), amount: sum('amount'), commission: sum('commission'),
    f_acquiring_fee: sum('f_acquiring_fee'), f_acceptance: sum('f_acceptance'),
    f_delivery: sum('f_delivery'), f_storage_fee: sum('f_storage_fee'),
    f_penalty: sum('f_penalty'), f_deduction: sum('f_deduction'),
    f_otziv: sum('f_otziv'), f_adv: sum('f_adv'), f_cashback: sum('f_cashback'),
    net_profit: sum('net_profit'), total_nds: sum('total_nds'), total_cost: sum('total_cost'),
    profit_before_tax: sum('profit_before_tax'), tax_amount: sum('tax_amount'), clean_margin: sum('clean_margin'),
  }
})
const fmt0 = (v:any)=> new Intl.NumberFormat('ru-RU').format(Math.round(Number(v)||0))
</script>
