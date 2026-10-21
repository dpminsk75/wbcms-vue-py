<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box page-captured__modal">
      <div class="page-captured__modal-head">
        <h5 class="page-captured__modal-title">
          <i class="bi bi-clock-history"></i> История контента
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="error" class="text-danger small">{{ error }}</div>
      <div v-else-if="!items.length" class="text-muted small">
        Снимков нет — история пишется при сборе, когда контент изменился.
      </div>

      <div v-else class="page-captured__hist-list">
        <div v-for="h in items" :key="h.id" class="page-captured__hist-item">
          <div class="page-captured__hist-head">
            <span class="page-captured__hist-date">{{ fmt(h.created_at) }}</span>
            <span class="badge bg-secondary">{{ h.source }}</span>
            <span class="badge bg-light text-dark" :title="`описание ${h.desc_len} симв.`">описание: {{ h.desc_len }}</span>
            <span class="badge bg-light text-dark" :title="`характеристик ${h.chars_cnt}`">хар-к: {{ h.chars_cnt }}</span>
            <span class="page-captured__hist-hash" :title="h.content_hash">{{ (h.content_hash || '').slice(0, 8) }}</span>
          </div>
          <details class="page-captured__hist-details">
            <summary>показать снимок</summary>
            <div class="page-captured__hist-title">{{ h.title || '—' }}</div>
            <div class="page-captured__hist-meta">
              <span v-if="h.brand">бренд: {{ h.brand }}</span>
              <span v-if="h.seller">продавец: {{ h.seller }}</span>
              <span v-if="h.price">цена: {{ h.price }}</span>
              <span v-if="h.old_price">было: {{ h.old_price }}</span>
            </div>
            <div v-if="h.description_preview" class="page-captured__hist-text">{{ h.description_preview }}<span v-if="h.desc_len > 300">…</span></div>
            <div v-if="h.characteristics.length" class="page-captured__hist-chars">
              <span v-for="(c, i) in h.characteristics" :key="i" class="page-captured__char">
                <b>{{ c.name }}</b>: {{ charValue(c.value) }}
              </span>
            </div>
          </details>
        </div>
      </div>

      <div class="wb-modal-actions">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { competitorsNewcardApi, type CapturedHistoryItem } from '../../api/competitorsNewcard'

const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
defineEmits<{ (e: 'close'): void }>()

const items = ref<CapturedHistoryItem[]>([])
const loading = ref(false)
const error = ref('')

function fmt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function charValue(v: any): string {
  if (Array.isArray(v)) return v.join('; ')
  return v == null ? '' : String(v)
}

async function load() {
  const id = Number(props.nmId || 0)
  if (!id) return
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.capturedHistory(id, 100)
    items.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить историю'
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.nmId] as const,
  ([isOpen]) => {
    if (isOpen) load()
  },
)
</script>
