<template>
  <!-- Поиск карточки WB: подсказки ищутся на бэке (/api/wb/cards?q=), а не по первым 200.
       Контракт как у WbFilterBar: v-model:nm-id — строгий nmID. -->
  <div class="wb-card-select" ref="wrapRef">
    <input
      :value="cardQuery"
      :placeholder="placeholder"
      class="form-control wb-card-select__input"
      autocomplete="off"
      @input="onInput($event)"
      @focus="showList = true"
      @keydown.esc="showList = false"
    />
    <div v-if="showList && (filtered.length || searching)" class="wb-card-select__list">
      <div v-if="searching && !filtered.length" class="wb-card-select__row text-muted">Поиск...</div>
      <div v-for="c in filtered.slice(0, 20)" :key="c.nmID" @mousedown.prevent="select(c)" class="wb-card-select__row">
        {{ c.nmID }} | {{ c.title }} | {{ c.vendorCode }}
      </div>
    </div>
    <div class="wb-card-select__status">
      <span v-if="nmId" class="wb-card-select__chosen">Выбрано: {{ nmId }}</span>
      <button v-if="nmId || cardQuery" class="btn btn-sm btn-light wb-card-select__btn" @click="clear">× Сбросить</button>
      <button v-if="showList" class="btn btn-sm btn-outline-secondary wb-card-select__btn" @click="showList = false">Закрыть Esc</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '@/api/client'

withDefaults(defineProps<{ placeholder?: string }>(), {
  placeholder: 'Выберите артикул...',
})

const nmId = defineModel<string>('nmId', { default: '' })

const cardQuery = ref(nmId.value || '')
const showList = ref(false)
const cards = ref<any[]>([])
const wrapRef = ref<HTMLDivElement | null>(null)
const titleCache = ref<Record<string, string>>({})
const searching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let reqSeq = 0

// Серверный поиск /api/wb/cards?q= (nmID/vendorCode/title по всей таблице),
// иначе старый срез 200 не находил карточки со старыми nmID.
const serverSearch = async (q: string) => {
  const my = ++reqSeq
  searching.value = true
  try {
    const { data: d } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    if (my !== reqSeq) return
    cards.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch { /* noop */ } finally {
    if (my === reqSeq) searching.value = false
  }
}

const filtered = computed(() => {
  const q = cardQuery.value.toLowerCase().trim()
  if (!q) return cards.value
  // после серверного поиска список уже отфильтрован; короткий запрос (<2) — локально
  if (q.length >= 2) return cards.value
  return cards.value.filter((c: any) =>
    String(c.nmID).includes(q) ||
    String(c.vendorCode || '').toLowerCase().includes(q) ||
    String(c.title || '').toLowerCase().includes(q))
})

const onInput = (e: Event) => {
  cardQuery.value = (e.target as HTMLInputElement).value
  showList.value = true
  if (!cardQuery.value) { nmId.value = ''; loadInitial(); return }
  if (searchTimer) clearTimeout(searchTimer)
  const q = cardQuery.value.trim()
  if (q.length >= 2) searchTimer = setTimeout(() => serverSearch(q), 300)
}

const loadInitial = async () => {
  try {
    const r = await api.get('/api/wb/cards', { params: { limit: 200 } })
    const d = r.data
    cards.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch { /* noop */ }
}

const select = (c: any) => {
  nmId.value = String(c.nmID)
  cardQuery.value = `${c.nmID} | ${c.title}`
  showList.value = false
}

const clear = () => { nmId.value = ''; cardQuery.value = ''; showList.value = false }

// синхронизация внешнего nmId -> подпись (выбор, URL, F5)
const syncLabel = async () => {
  const id = String(nmId.value || '')
  if (!id) { if (!showList.value) cardQuery.value = ''; return }
  const c = cards.value.find((x: any) => String(x.nmID) === id)
  if (c) { cardQuery.value = c.title ? `${c.nmID} | ${c.title}` : String(c.nmID); return }
  if (cardQuery.value && cardQuery.value !== id) return
  if (titleCache.value[id]) { cardQuery.value = `${id} | ${titleCache.value[id]}`; return }
  try {
    const { data: d } = await api.get(`/api/wb/card/${id}`)
    if (d?.title) { titleCache.value[id] = d.title; if (String(nmId.value) === id) cardQuery.value = `${id} | ${d.title}`; return }
  } catch { /* noop */ }
  if (!cardQuery.value) cardQuery.value = id
}
watch(() => nmId.value, syncLabel)
watch(cards, () => { if (nmId.value) syncLabel() })

// клик вне — закрытие списка
const onDocClick = (e: MouseEvent) => {
  if (!showList.value) return
  const el = wrapRef.value
  if (el && !el.contains(e.target as Node)) showList.value = false
}

onMounted(async () => {
  document.addEventListener('mousedown', onDocClick)
  await loadInitial()
  if (nmId.value) syncLabel()
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  if (searchTimer) clearTimeout(searchTimer)
  reqSeq++
})
</script>
<style scoped>
.wb-card-select { position: relative; }
.wb-card-select__input { width: 100%; }
.wb-card-select__list { position: absolute; top: 100%; left: 0; right: 0; max-height: 220px; overflow: auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; z-index: 10; box-shadow: 0 4px 12px rgba(0, 0, 0, .1); }
.wb-card-select__row { padding: 6px 10px; cursor: pointer; font-size: 12px; border-bottom: 1px solid #f1f5f9; }
.wb-card-select__status { display: flex; gap: 8px; align-items: center; margin-top: 4px; }
.wb-card-select__chosen { font-size: 11px; color: #7c1af8; }
.wb-card-select__btn { font-size: 11px; padding: 2px 8px; }
</style>
