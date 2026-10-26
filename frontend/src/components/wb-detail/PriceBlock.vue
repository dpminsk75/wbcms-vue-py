<template>
  <div v-if="rows.length" class="dl_item page-wb-detail__price mb-1" @click="emit('open')" title="История изменения цены">
    <dt class="card_characteristics__dt mt-2">Цена:</dt>
    <dd class="card_characteristics__dd page-wb-detail__price-line mt-1">
      <b>{{ fmt2(rows[0].price) }} ₽</b>
      <span class="page-wb-detail__price-sep mt-1">·</span>
      <span>Скидка: <b>{{ rows[0].discount }}%</b></span>
      <span class="page-wb-detail__price-sep mt-1">·</span>
      <span>Цена со ск: <b>{{ fmt2(rows[0].discounted_price) }} ₽</b></span>
      <i class="bi bi-clock-history page-wb-detail__price-hint"></i>
    </dd>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api } from '@/api/client'

const props = defineProps<{ nmId: string | number }>()
const emit = defineEmits<{ open: [] }>()

const rows = ref<any[]>([])

const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)

const fetchData = async () => {
  if (!props.nmId) { rows.value = []; return }
  try {
    const { data: d } = await api.get(`/api/wb/detail/prices?nm_id=${props.nmId}`)
    rows.value = Array.isArray(d?.rows) ? d.rows : []
  } catch {
    rows.value = []
  }
}

onMounted(fetchData)
watch(() => props.nmId, fetchData)
</script>
<style scoped>
/* Блок цены — одна строка: подпись по ширине текста, значение не переносится.
   Класс продублирован, чтобы перебить .dl_item из родителя (grid-template-columns). */
.page-wb-detail__price.page-wb-detail__price { grid-template-columns: auto 1fr; cursor: pointer; }
.page-wb-detail__price:hover dd { color: #8a2be0; }
.page-wb-detail__price-line { display: flex; flex-wrap: nowrap; align-items: baseline; gap: 4px; white-space: nowrap; }
.page-wb-detail__price-sep { color: #b8b8b8; }
.page-wb-detail__price-hint { font-size: 10px; color: #9ca3af; margin-left: 2px; }
</style>
