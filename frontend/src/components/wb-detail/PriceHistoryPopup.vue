<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div
      ref="boxRef"
      class="wb-modal-box price-history"
      role="dialog"
      aria-modal="true"
      aria-label="История изменения цены"
      :style="boxStyle"
      data-modal-drag="own"
    >
      <div
        class="price-history__head"
        data-modal-drag-handle
        title="Потяните, чтобы переместить"
        v-on="dragHandlers"
      >
        <div class="price-history__titles">
          <span class="price-history__name">История изменения цены</span>
          <span class="price-history__sub">
            <a v-if="nmId" :href="`/wb/detail?nm_id=${nmId}`" target="_blank" class="price-history__wb">WB: {{ nmId }}</a>
            <span v-if="period"> · {{ period }}</span>
          </span>
        </div>
        <button class="btn btn-sm btn-link price-history__close" title="Закрыть" @click="$emit('close')">✕</button>
      </div>

      <div v-if="loading" class="text-center p-3"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
      <div v-else-if="!rows.length" class="price-history__empty">За период изменений цены не было</div>
      <div v-else class="price-history__scroll">
        <table class="table table-sm mb-0 price-history__table">
          <thead>
            <tr>
              <th>Дата</th>
              <th class="text-end">Цена</th>
              <th class="text-end">Скидка</th>
              <th class="text-end">Цена со ск.</th>
              <th class="text-end">Δ</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id" :class="r.is_latest ? 'price-history__row--current' : ''">
              <td class="price-history__date">{{ dmy(r.created_at) }}</td>
              <td class="text-end">{{ fmt2(r.price) }}</td>
              <td class="text-end">{{ r.discount }}%</td>
              <td class="text-end price-history__final">{{ fmt2(r.discounted_price) }}</td>
              <td class="text-end" :class="deltaClass(r)">{{ deltaText(r) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { useDraggable } from '@/composables/useDraggable'

const props = defineProps<{
  open: boolean
  nmId: string | number
  dateFrom: string
  dateTo: string
}>()
const emit = defineEmits<{ close: [] }>()

const rows = ref<any[]>([])
const loading = ref(false)

const nf2 = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmt2 = (v: any) => nf2.format(Number(v) || 0)

const dmy = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}.${m[2]}.${m[1]}` : (iso || '—')
}

const period = computed(() => `${props.dateFrom} — ${props.dateTo}`)

// Δ = изменение цены со скидкой к предыдущей записи (строки идут от новых к старым)
const deltaOf = (r: any) => {
  const i = rows.value.indexOf(r)
  if (i < 0 || i + 1 >= rows.value.length) return null
  const prev = rows.value[i + 1]
  const a = Number(r.discounted_price) || 0
  const b = Number(prev.discounted_price) || 0
  if (!b) return null
  return ((a - b) / b) * 100
}
const deltaText = (r: any) => {
  const d = deltaOf(r)
  if (d === null) return '—'
  return (d > 0 ? '+' : '') + d.toFixed(1) + '%'
}
const deltaClass = (r: any) => {
  const d = deltaOf(r)
  if (d === null) return ''
  return d < 0 ? 'price-history__delta--down' : (d > 0 ? 'price-history__delta--up' : '')
}

const fetchData = async () => {
  if (!props.nmId || !props.dateFrom || !props.dateTo) { rows.value = []; return }
  loading.value = true
  try {
    const { data: d } = await api.get(
      `/api/wb/detail/prices/history?nm_id=${props.nmId}&date_from=${props.dateFrom}&date_to=${props.dateTo}`)
    rows.value = Array.isArray(d?.rows) ? d.rows : []
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.open, props.nmId, props.dateFrom, props.dateTo], () => {
  if (props.open) fetchData()
}, { immediate: true })

const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onUnmounted(() => window.removeEventListener('keydown', onEsc))

// Перетаскивание модалки за шапку (composables/useDraggable)
const boxRef = ref<HTMLElement | null>(null)
const { boxStyle, dragHandlers } = useDraggable(boxRef)
</script>

<style scoped>
/* z-index — глобальный .wb-modal-backdrop его не имеет, попап иначе уйдёт под навбар */
.wb-modal-backdrop { z-index: 1050; }
.price-history { min-width: 460px; max-width: 640px; }
.price-history__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; cursor: move; touch-action: none; user-select: none; }
.price-history__titles { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.price-history__name { font-size: 13px; font-weight: 700; color: #111827; line-height: 1.25; }
.price-history__sub { font-size: 11px; color: #6b7280; }
.price-history__wb { color: #2980b9; text-decoration: none; }
.price-history__wb:hover { text-decoration: underline; }
.price-history__close { text-decoration: none; font-size: 14px; }
.price-history__scroll { max-height: 52vh; overflow-y: auto; }
.price-history__empty { font-size: 12px; color: #6b7280; padding: 8px 0; }
.price-history__table { font-size: 12px; }
.price-history__table thead th { font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; color: #9ca3af; border-bottom: 1px solid #e5e7eb; padding: 4px 6px; }
.price-history__table tbody td { padding: 3px 6px; vertical-align: middle; }
.price-history__date { color: #374151; white-space: nowrap; }
.price-history__final { font-weight: 700; color: #5A1C9C; white-space: nowrap; }
.price-history__row--current td { background: #eef4fb; }
.price-history__delta--down { color: #15803d; }
.price-history__delta--up { color: #b91c1c; }
</style>
