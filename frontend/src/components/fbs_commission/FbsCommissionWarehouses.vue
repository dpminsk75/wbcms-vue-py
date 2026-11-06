<template>
  <div class="tbl-card fbs-tbl__card">
    <div class="card__hd">
      <span>По складам продавца ({{ items.length }})</span>
    </div>
    <div class="tbl-wrap">
      <table class="tbl fbs-tbl">
        <thead>
          <tr>
            <th class="t-left fbs-tbl__first">Склад</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('tasks_cnt')">Заданий {{ mark('tasks_cnt') }}</th>
            <th class="t-right">До сдачи</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('p90_h')">9 из 10 быстрее {{ mark('p90_h') }}</th>
            <th class="t-left">Зоны</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('earned')">Заработано {{ mark('earned') }}</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('lost')">Потеряно {{ mark('lost') }}</th>
            <th class="t-right fbs-tbl__sort" @click="sortBy('potential')">Можно ещё {{ mark('potential') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!sorted.length"><td colspan="8" class="fbs-tbl__empty">Нет данных</td></tr>
          <tr v-for="w in sorted" :key="String(w.warehouse_id)">
            <td class="t-left">{{ w.warehouse_name }}{{ w.warehouse_id ? ' ' + w.warehouse_id : '' }}</td>
            <td class="t-right num">{{ fmt0(w.tasks_cnt) }}</td>
            <td class="t-right num">{{ fmtDur(w.avg_h) }} · {{ fmt0(w.measured_cnt) }}</td>
            <td class="t-right num">{{ fmtDur(w.p90_h) }}</td>
            <td class="t-left"><span class="fbs-tbl__zones"><span v-for="(z, i) in w.zones" :key="i" :style="{ width: z + '%', background: zoneColor(i) }" :title="zoneName(i) + ': ' + fmtPct1(z)"></span></span></td>
            <td class="t-right num">{{ fmtMoney(w.earned) }}</td>
            <td class="t-right num fbs-tbl__num--red">{{ fmtMoney(w.lost) }}</td>
            <td class="t-right num">{{ fmtMoney(w.potential) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, computed } from 'vue'
import { resolveTokenColor } from '@/utils/chartTheme'
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
// Число зон не зашито: зоны = «корзины сетки + без сдачи» (labels из API).
// i < labels.length → цвет --fbs-speed-(i+1) (7-я и далее — в --fbs-speed-6), последняя — --fbs-speed-none.
const zoneColor = (i: number) => {
  const n = (props.labels || []).length
  if (i >= n) return resolveTokenColor('--fbs-speed-none')
  return resolveTokenColor(`--fbs-speed-${Math.min(i + 1, 6)}`)
}
const zoneName = (i: number) => [...(props.labels || []), 'без сдачи'][i] || ''
</script>
