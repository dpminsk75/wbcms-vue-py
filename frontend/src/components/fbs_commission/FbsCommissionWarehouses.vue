<template>
  <div class="card wb-grid-card page-fbs-commission__table-card">
    <div class="page-fbs-commission__table-head">По складам продавца ({{ items.length }})</div>
    <div class="wb-table-wrap">
      <table class="table table-bordered table-striped table-hover kv-grid-table mb-0">
        <thead>
          <tr>
            <th class="page-fbs-commission__first">Склад</th>
            <th @click="sortBy('tasks_cnt')" class="page-fbs-commission__sort">Заданий {{ mark('tasks_cnt') }}</th>
            <th>До сдачи</th>
            <th @click="sortBy('p90_h')" class="page-fbs-commission__sort">9 из 10 быстрее {{ mark('p90_h') }}</th>
            <th>Зоны</th>
            <th @click="sortBy('earned')" class="page-fbs-commission__sort">Заработано {{ mark('earned') }}</th>
            <th @click="sortBy('lost')" class="page-fbs-commission__sort">Потеряно {{ mark('lost') }}</th>
            <th @click="sortBy('potential')" class="page-fbs-commission__sort">Можно ещё {{ mark('potential') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td colspan="8" class="text-center text-muted">Нет данных</td></tr>
          <tr v-for="w in sorted" :key="String(w.warehouse_id)">
            <td>{{ w.warehouse_name }}{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }}</td>
            <td class="page-fbs-commission__num">{{ fmt0(w.tasks_cnt) }}</td>
            <td class="page-fbs-commission__num">{{ fmtDur(w.avg_h) }} · {{ fmt0(w.measured_cnt) }}</td>
            <td class="page-fbs-commission__num">{{ fmtDur(w.p90_h) }}</td>
            <td><span class="page-fbs-commission__zones"><span v-for="(z, i) in w.zones" :key="i" :style="{ width: z + '%', background: zoneColor(i) }" :title="zoneName(i) + ': ' + fmtPct1(z)"></span></span></td>
            <td class="page-fbs-commission__num">{{ fmtMoney(w.earned) }}</td>
            <td class="page-fbs-commission__num page-fbs-commission__num--red">{{ fmtMoney(w.lost) }}</td>
            <td class="page-fbs-commission__num">{{ fmtMoney(w.potential) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
const props = defineProps<{ items: any[], labels: string[] }>()
const sortKey = ref('earned')
const sortDir = ref(-1)
const sortBy = (k: string) => {
  if (sortKey.value === k) sortDir.value = -sortDir.value
  else { sortKey.value = k; sortDir.value = -1 }
}
const mark = (k: string) => sortKey.value === k ? (sortDir.value > 0 ? '▲' : '▼') : '⇅'
const sorted = computed(() => {
  const arr = [...(props.items || [])]
  const k = sortKey.value, d = sortDir.value
  arr.sort((a: any, b: any) => ((Number(a[k]) || 0) - (Number(b[k]) || 0)) * d)
  return arr
})
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
const fmtMoney = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(v) || 0) + ' ₽'
const fmtPct1 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0) + ' %'
const fmtDur = (v: any) => {
  if (v == null) return '—'
  const h = Number(v)
  if (h >= 24) return Math.floor(h / 24) + ' дн ' + Math.round(h % 24) + ' ч'
  if (h >= 1) return Math.floor(h) + ' ч ' + Math.round((h % 1) * 60) + ' м'
  return Math.round(h * 60) + ' м'
}
const zoneColor = (i: number) => ['#16a34a', '#22c55e', '#9AA0A8', '#fb7185', '#ef4444', '#991b1b', '#cbd5e1'][i] || '#9AA0A8'
const zoneName = (i: number) => [...(props.labels || []), 'без сдачи'][i] || ''
</script>
<style scoped>
.page-fbs-commission__table-card { margin-bottom: 16px; border-color: #d5dae1; box-shadow: 0 1px 3px rgba(16,24,40,.08); }
.page-fbs-commission__table-head { font-size: 13px; font-weight: 700; color: #111827; padding: 12px 18px; background: #fff; border-bottom: 1px solid #e5e7eb; border-radius: 10px 10px 0 0; }
.page-fbs-commission__first { text-align: center; min-width: 200px; }
.page-fbs-commission__sort { text-align: center; cursor: pointer; white-space: nowrap; }
.page-fbs-commission__num { text-align: right; white-space: nowrap; }
.page-fbs-commission__table-card table tbody td { font-size: 14px; }
.page-fbs-commission__num--red { color: #b91c1c; }
.page-fbs-commission__zones { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #f1f5f9; min-width: 90px; }
.page-fbs-commission__zones > span { height: 100%; }
</style>
