<template>
  <div class="page-fbs-report__pipeline-card">
    <div class="page-fbs-report__section-title">Где сейчас задания периода</div>
    <div v-if="total" class="page-fbs-report__pipeline-bar">
      <div v-for="s in segments" :key="s.key" v-show="s.cnt > 0"
        :style="{ width: pct(s.cnt) + '%', background: s.color }"
        :title="s.label + ': ' + fmt0(s.cnt)"></div>
    </div>
    <div v-else class="text-muted page-fbs-report__empty">Нет данных</div>
    <div class="page-fbs-report__pipeline-grid">
      <div v-for="s in segments" :key="s.key" class="page-fbs-report__pipeline-item" :style="{ borderLeftColor: s.color }">
        <span class="page-fbs-report__pipeline-label">{{ s.label }}</span>
        <b class="page-fbs-report__pipeline-value">{{ fmt0(s.cnt) }}</b>
      </div>
    </div>
    <div v-if="pipeline.unknown" class="page-fbs-report__unknown">
      Не распознано статусов: {{ fmt0(pipeline.unknown) }} (новый wb_status — сообщить разработчику)
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ pipeline: any }>()

const segments = computed(() => [
  { key: 'new', label: 'Новый', cnt: props.pipeline?.new || 0, color: '#c4b5fd' },
  { key: 'assembling', label: 'В сборке', cnt: props.pipeline?.assembling || 0, color: '#a78bfa' },
  { key: 'handed', label: 'Передан WB', cnt: props.pipeline?.handed || 0, color: '#7c3aed' },
  { key: 'transit', label: 'В пути', cnt: props.pipeline?.transit || 0, color: '#22c55e' },
  { key: 'pickup', label: 'Ждёт в ПВЗ', cnt: props.pipeline?.pickup || 0, color: '#4ade80' },
  { key: 'sold', label: 'Выкуплено', cnt: props.pipeline?.sold || 0, color: '#16a34a' },
  { key: 'declined', label: 'Отказ на выдаче', cnt: props.pipeline?.declined || 0, color: '#fb7185' },
  { key: 'buyer_cancel', label: 'Отменил покупатель', cnt: props.pipeline?.buyer_cancel || 0, color: '#ef4444' },
  { key: 'seller_cancel', label: 'Отменил продавец', cnt: props.pipeline?.seller_cancel || 0, color: '#991b1b' },
])

const total = computed(() => segments.value.reduce((a, s) => a + s.cnt, 0) + (props.pipeline?.unknown || 0))
const pct = (v: number) => total.value ? Math.max(v / total.value * 100, v > 0 ? 0.6 : 0) : 0
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
</script>
<style scoped>
.page-fbs-report__pipeline-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 18px; margin-bottom:16px; }
.page-fbs-report__section-title { font-size:13px; font-weight:600; color:#111827; margin-bottom:10px; }
.page-fbs-report__pipeline-bar { display:flex; height:20px; border-radius:10px; overflow:hidden; background:#f1f5f9; margin-bottom:12px; }
.page-fbs-report__pipeline-bar > div { height:100%; }
.page-fbs-report__pipeline-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }
.page-fbs-report__pipeline-item { display:flex; align-items:center; justify-content:space-between; gap:8px; background:#fff; border:1px solid #e5e7eb; border-left:10px solid #c4b5fd; border-radius:8px; padding:10px 12px; font-size:12px; }
.page-fbs-report__pipeline-label { color:#6b7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.page-fbs-report__pipeline-value { color:#111827; font-size:15px; }
@media (max-width: 991px) {
  .page-fbs-report__pipeline-grid { grid-template-columns:repeat(2, 1fr); }
}
.page-fbs-report__empty { font-size:12px; }
.page-fbs-report__unknown { margin-top:8px; font-size:11px; color:#b45309; }
</style>
