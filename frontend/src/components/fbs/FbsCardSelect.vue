<template>
  <div class="fbs-select__wrap" ref="cardWrapRef">
    <input :value="cardQuery" @input="onInput($event)" placeholder="nm_id, артикул или название..." class="wb-input"
      @focus="showList = true" @keydown.esc="showList = false" />
    <div v-if="showList && (filtered.length || searching)" class="fbs-select__list">
      <div v-if="searching && !filtered.length" class="fbs-select__item text-muted">Поиск...</div>
      <div v-for="c in filtered.slice(0, 20)" :key="c.nmID" @mousedown.prevent="select(c)" class="fbs-select__item">
        {{ c.nmID }} | {{ c.title }} | {{ c.vendorCode }}
      </div>
    </div>
    <div v-if="nmId || cardQuery" class="fbs-select__clear">
      <span v-if="nmId" class="fbs-select__chosen">Выбрано: {{ nmId }}</span>
      <button class="btn btn--outline btn-sm fbs-select__clear-btn" @click="clear">× Сбросить</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import '@/assets/css/components/fbs.css'
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '@/api/client'

// Поведение 1в1 с поиском карточки из WbFilterBar (без квик-кнопок): поиск по nmID/vendorCode/title.
const nmId = defineModel<string>('nmId', { default: '' })

const cardQuery = ref(nmId.value || '')
const showList = ref(false)
const cards = ref<any[]>([])
const cardWrapRef = ref<HTMLDivElement | null>(null)
const titleCache = ref<Record<string, string>>({})
const searching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let reqSeq = 0

// Серверный поиск /api/wb/cards?q= (nmID/vendorCode/title, WbCardService.list_cards),
// иначе ищем только среди первых 200 — vendorCode может не найтись.
const serverSearch = async (q: string) => {
  const my = ++reqSeq
  searching.value = true
  try {
    const { data: d } = await api.get('/api/wb/cards', { params: { q, limit: 20 } })
    if (my !== reqSeq) return
    const arr = Array.isArray(d) ? d : (d?.items ?? [])
    cards.value = arr
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

const onDocClick = (e: MouseEvent) => {
  if (!showList.value) return
  const el = cardWrapRef.value
  if (el && !el.contains(e.target as Node)) showList.value = false
}

onMounted(async () => {
  document.addEventListener('mousedown', onDocClick)
  await loadInitial()
  if (!cards.value.length) {
    try {
      const r2 = await api.get('/api/dashboard/new-cards?dateFrom=2025-01-01&dateTo=2026-12-31')
      const d = r2.data
      cards.value = Array.isArray(d) ? d : (d?.items ?? [])
    } catch { /* noop */ }
  }
  if (nmId.value) syncLabel()
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  if (searchTimer) clearTimeout(searchTimer)
  reqSeq++
})
</script>
