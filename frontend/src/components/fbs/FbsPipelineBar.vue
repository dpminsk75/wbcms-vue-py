<template>
  <div class="fbs-chart-card">
    <div class="fbs-chart-card__title">Где сейчас задания периода</div>
    <div v-if="total" class="fbs-pipeline__bar">
      <div v-for="s in segments" :key="s.key" v-show="s.cnt > 0"
        :style="{ width: pct(s.cnt) + '%', background: s.color }"
        :title="s.label + ': ' + fmt0(s.cnt)"></div>
    </div>
    <div v-else class="fbs-empty">Нет данных</div>
    <div class="fbs-pipeline__grid">
      <div v-for="s in segments" :key="s.key" class="fbs-pipeline__item" :style="{ borderLeftColor: s.color }">
        <span class="fbs-pipeline__label">{{ s.label }}</span>
        <b class="fbs-pipeline__value">{{ fmt0(s.cnt) }}</b>
      </div>
    </div>
    <div v-if="pipeline.unknown" class="fbs-pipeline__unknown">
      Не распознано статусов: {{ fmt0(pipeline.unknown) }} (новый wb_status — сообщить разработчику)
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { computed } from 'vue'
import { resolveTokenColor } from '@/utils/chartTheme'

const props = defineProps<{ pipeline: any }>()

// Цвета статусов — токены темы (theme/tokens.css, --fbs-1…9).
// echarts/канвас не понимает var(), поэтому резолвим через color пробного элемента.
const segments = computed(() => [
  { key: 'new', label: 'Новый', cnt: props.pipeline?.new || 0, color: resolveTokenColor('--fbs-1') },
  { key: 'assembling', label: 'В сборке', cnt: props.pipeline?.assembling || 0, color: resolveTokenColor('--fbs-2') },
  { key: 'handed', label: 'Передан WB', cnt: props.pipeline?.handed || 0, color: resolveTokenColor('--fbs-3') },
  { key: 'transit', label: 'В пути', cnt: props.pipeline?.transit || 0, color: resolveTokenColor('--fbs-4') },
  { key: 'pickup', label: 'Ждёт в ПВЗ', cnt: props.pipeline?.pickup || 0, color: resolveTokenColor('--fbs-5') },
  { key: 'sold', label: 'Выкуплено', cnt: props.pipeline?.sold || 0, color: resolveTokenColor('--fbs-6') },
  { key: 'declined', label: 'Отказ на выдаче', cnt: props.pipeline?.declined || 0, color: resolveTokenColor('--fbs-7') },
  { key: 'buyer_cancel', label: 'Отменил покупатель', cnt: props.pipeline?.buyer_cancel || 0, color: resolveTokenColor('--fbs-8') },
  { key: 'seller_cancel', label: 'Отменил продавец', cnt: props.pipeline?.seller_cancel || 0, color: resolveTokenColor('--fbs-9') },
])

const total = computed(() => segments.value.reduce((a, s) => a + s.cnt, 0) + (props.pipeline?.unknown || 0))
const pct = (v: number) => total.value ? Math.max(v / total.value * 100, v > 0 ? 0.6 : 0) : 0
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
</script>
