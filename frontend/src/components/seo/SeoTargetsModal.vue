<template>
  <div v-if="open" class="page-wb-detail__modal-backdrop" @click.self="$emit('close')">
    <div class="page-wb-detail__modal-box">
      <div class="page-wb-detail__modal-head">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-bullseye"></i> Целевые запросы
          <span class="page-wb-detail__modal-count">{{ items.length }}/{{ limit }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>
      <p class="page-wb-detail__modal-hint">
        До 10, идут в system с приоритетом. Пусто = только статистика.
      </p>

      <div class="page-wb-detail__chips">
        <span v-for="t in items" :key="t.id" class="badge bg-warning text-dark page-wb-detail__chip">
          {{ t.phrase }}
          <a href="#" class="page-wb-detail__chip-x" title="Удалить" @click.prevent="remove(t.id)">×</a>
        </span>
        <span v-if="!items.length" class="text-muted small">Пока нет — добавь ниже</span>
      </div>

      <form class="d-flex gap-2 mt-3" @submit.prevent="add">
        <input
          v-model="phrase"
          class="form-control form-control-sm"
          placeholder="напр: дневник школьника 12 лет"
          maxlength="500"
          :disabled="busy"
        />
        <button type="submit" class="btn btn-sm btn-outline-warning" :disabled="busy || !phrase.trim()">
          <i class="bi bi-plus-lg"></i> Добавить
        </button>
      </form>

      <div v-if="loading" class="text-muted small mt-2"><span class="spinner-border spinner-border-sm"></span> Загрузка...</div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { seoApi, type SeoTarget } from '@/api/seo'

const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const items = ref<SeoTarget[]>([])
const limit = ref(10)
const phrase = ref('')
const busy = ref(false)
const loading = ref(false)
const error = ref('')

const nm = () => Number(props.nmId || 0)

async function load() {
  const id = nm()
  if (!id) return
  loading.value = true
  error.value = ''
  try {
    const d = await seoApi.targets(id)
    items.value = d.items || []
    limit.value = d.limit || 10
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить целевые фразы'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function add() {
  const p = phrase.value.trim()
  const id = nm()
  if (!p || !id || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await seoApi.addTarget(id, p)
    phrase.value = ''
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось добавить'
  } finally {
    busy.value = false
  }
}

async function remove(tid: number) {
  error.value = ''
  try {
    await seoApi.removeTarget(tid)
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось удалить'
  }
}

watch(
  () => [props.open, props.nmId] as const,
  ([isOpen]) => { if (isOpen) load() },
)
</script>
