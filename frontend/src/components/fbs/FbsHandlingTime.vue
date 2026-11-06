<template>
  <div class="fbs-chart-card d-flex flex-column">
    <div class="fbs-chart-card__title">Время обработки заказов
      <span class="fbs-help" title="Время сборки: от появления сборочного задания до сдачи на WB">?</span>
    </div>
    <div v-if="handling.measured" class="fbs-handling__list">
      <div v-for="(b, i) in handling.buckets" :key="b.id" class="fbs-handling__group">
        <div class="fbs-handling__top">
          <span class="fbs-handling__label">{{ bucketLabel(b.id) }}</span>
          <span class="fbs-handling__value">{{ fmtPct2(b.pct) }} · {{ fmt0(b.cnt) }} шт</span>
        </div>
        <div class="fbs-handling__bar"><span :style="{ width: b.pct + '%', background: barColor(i) }"></span></div>
      </div>
      <div class="fbs-handling__note">измерено {{ fmt0(handling.measured) }} из {{ fmt0(handling.total) }}</div>
    </div>
    <div v-else class="d-flex align-items-center justify-content-center fbs-empty">Нет данных</div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { resolveTokenColor } from '@/utils/chartTheme'
defineProps<{ handling: any }>()

const bucketLabel = (id: string) => id.startsWith('от') ? 'Сдано ' + id : 'Сдано за ' + id
const barColor = (i: number) => i < 2 ? resolveTokenColor('--fbs-bar-good') : resolveTokenColor('--fbs-bar-late')
const fmtPct2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0) + ' %'
const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
</script>
