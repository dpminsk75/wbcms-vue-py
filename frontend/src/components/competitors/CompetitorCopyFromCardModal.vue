<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box page-captured__modal page-pick__bulk-modal">
      <div class="page-captured__modal-head">
        <h5 class="page-captured__modal-title">
          <i class="bi bi-files"></i> Конкуренты с нашей карточки
          <span class="badge bg-dark">{{ targetNm }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="page-pick__bulk-body">
        <p class="text-muted small mb-2">
          Выберите другую нашу карточку: её конкуренты скопируются сюда и попадут в очередь
          на сбор описаний. Уже привязанные не дублируются.
        </p>

        <div class="page-pick__toolbar">
          <div class="page-pick__search">
            <i class="bi bi-search"></i>
            <input
              v-model="q"
              class="form-control form-control-sm"
              placeholder="nmID, артикул WB или название"
              autocomplete="off"
              @keyup.enter="load"
            />
            <span v-if="loading" class="spinner-border spinner-border-sm text-secondary"></span>
          </div>
          <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load">Найти</button>
        </div>

        <div class="page-pick__target-list">
          <div v-if="loading && !options.length" class="text-muted small p-2">
            <span class="spinner-border spinner-border-sm"></span> Загрузка…
          </div>
          <div v-else-if="!options.length" class="text-muted small p-2">Ничего не найдено.</div>
          <label
            v-for="c in options"
            :key="c.nmID"
            class="page-pick__target"
            :class="{ 'is-picked': source?.nmID === c.nmID }"
          >
            <input
              type="radio"
              name="copy-source-card"
              :checked="source?.nmID === c.nmID"
              @change="source = c"
            />
            <span class="page-pick__target-nm">{{ c.nmID }}</span>
            <span class="page-pick__target-vendor">{{ c.vendor_code || '—' }}</span>
            <span class="page-pick__target-title" :title="c.title || ''">{{ c.title || 'без названия' }}</span>
            <span class="badge bg-light text-dark">конкуренты: {{ c.competitors_cnt }}</span>
          </label>
        </div>

        <div v-if="error" class="wb-error mt-2">{{ error }}</div>
      </div>

      <div class="page-pick__bulk-footer">
        <button type="button" class="btn btn-sm btn-outline-secondary" :disabled="saving" @click="$emit('close')">
          Отмена
        </button>
        <button
          type="button"
          class="btn btn-sm btn-success"
          :disabled="saving || !source"
          @click="copy"
        >
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-files"></i>
          Скопировать
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor-pick.css'
import { ref, watch } from 'vue'
import { competitorsNewcardApi, type PickCard } from '../../api/competitorsNewcard'

const props = defineProps<{
  open: boolean
  targetNm?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done', result: { added: number; source_nm_id: number }): void
}>()

const q = ref('')
const options = ref<PickCard[]>([])
const source = ref<PickCard | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | null = null
let seq = 0

async function load() {
  const my = ++seq
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.pickCards(q.value.trim(), 50)
    if (my !== seq) return
    options.value = (d.items || []).filter((c) => Number(c.nmID) !== Number(props.targetNm || 0))
  } catch (e: any) {
    if (my !== seq) return
    options.value = []
    error.value = e?.response?.data?.detail || 'Не удалось загрузить наши карточки'
  } finally {
    if (my === seq) loading.value = false
  }
}

async function copy() {
  if (!source.value || !props.targetNm) return
  saving.value = true
  error.value = ''
  try {
    const res = await competitorsNewcardApi.fromCard(props.targetNm, source.value.nmID)
    emit('done', res)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось скопировать конкурентов'
  } finally {
    saving.value = false
  }
}

watch(() => props.open, (open) => {
  if (!open) {
    if (timer) clearTimeout(timer)
    seq++
    return
  }
  q.value = ''
  options.value = []
  source.value = null
  error.value = ''
  load()
})

watch(q, (v) => {
  if (timer) clearTimeout(timer)
  const value = String(v || '').trim()
  if (value.length === 1) return
  timer = setTimeout(load, 300)
})
</script>
