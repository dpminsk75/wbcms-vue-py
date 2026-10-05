<template>
  <div class="page-fbs-report__chart-card page-fbs-report__handling-card">
    <div class="page-fbs-report__section-title">Время обработки заказов
      <span class="page-fbs-report__help" title="Время сборки: от появления сборочного задания до сдачи на WB">?</span>
    </div>
    <div v-if="handling.measured" class="page-fbs-report__handling-list">
      <div v-for="(b, i) in handling.buckets" :key="b.id" class="page-fbs-report__handling-group">
        <div class="page-fbs-report__handling-top">
          <span class="page-fbs-report__handling-label">{{ bucketLabel(b.id) }}</span>
          <span class="page-fbs-report__handling-value">{{ fmtPct2(b.pct) }} · {{ fmt0(b.cnt) }} шт</span>
        </div>
        <div class="page-fbs-report__handling-bar"><span :style="{ width: b.pct + '%', background: barColor(i) }"></span></div>
      </div>
      <div class="page-fbs-report__handling-note">измерено {{ fmt0(handling.measured) }} из {{ fmt0(handling.total) }}</div>
    </div>
    <div v-else class="d-flex align-items-center justify-content-center text-muted page-fbs-report__empty">Нет данных</div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ handling: any }>()

const bucketLabel = (id: string) => id.startsWith('от') ? 'Сдано ' + id : 'Сдано за ' + id
const barColor = (i: number) => i < 2 ? '#22c55e' : '#a78bfa'
const fmtPct2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0) + ' %'
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
</script>
<style scoped>
.page-fbs-report__chart-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 18px; margin-bottom:16px; height:100%; }
.page-fbs-report__handling-card { display:flex; flex-direction:column; }
.page-fbs-report__section-title { font-size:13px; font-weight:600; color:#111827; margin-bottom:10px; }
.page-fbs-report__help { display:inline-block; width:16px; height:16px; line-height:14px; text-align:center; font-size:11px; color:#9ca3af; border:1px solid #d1d5db; border-radius:50%; cursor:help; margin-left:4px; }
.page-fbs-report__handling-list { display:flex; flex-direction:column; justify-content:space-evenly; flex:1; }
.page-fbs-report__handling-group { margin-bottom:6px; }
.page-fbs-report__handling-top { display:flex; align-items:baseline; justify-content:space-between; gap:8px; font-size:12px; margin-bottom:4px; }
.page-fbs-report__handling-label { color:#374151; white-space:nowrap; }
.page-fbs-report__handling-value { font-weight:700; color:#111827; white-space:nowrap; }
.page-fbs-report__handling-bar { height:6px; border-radius:3px; background:#f1f5f9; overflow:hidden; }
.page-fbs-report__handling-bar > span { display:block; height:100%; border-radius:3px; }
.page-fbs-report__handling-note { font-size:11px; color:#9ca3af; margin-top:8px; }
.page-fbs-report__empty { font-size:12px; min-height:120px; }
</style>
