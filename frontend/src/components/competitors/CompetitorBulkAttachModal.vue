<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box page-captured__modal page-pick__bulk-modal">
      <div class="page-captured__modal-head">
        <h5 class="page-captured__modal-title">
          <i class="bi bi-link-45deg"></i> Массовая привязка
          <span class="badge bg-dark">{{ candidates.length }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="page-pick__bulk-body">
        <div class="page-pick__bulk-section">
          <div class="page-pick__bulk-label">Выбранные конкуренты</div>
          <div class="page-pick__chips">
            <span
              v-for="c in candidates.slice(0, 16)"
              :key="c.nm_id"
              class="page-pick__chip"
              :title="c.title || ''"
            >{{ c.nm_id }}</span>
            <span v-if="candidates.length > 16" class="page-pick__muted">+{{ candidates.length - 16 }}</span>
          </div>
          <div v-if="candidates.some((c) => c.is_hidden || c.is_own)" class="page-pick__bulk-warn">
            Скрытые и наши собственные карточки будут пропущены.
          </div>
        </div>

        <div class="page-pick__bulk-section">
          <div class="page-pick__bulk-label">Куда привязать</div>
          <div class="page-pick__toolbar">
            <div class="page-pick__search">
              <i class="bi bi-search"></i>
              <input
                v-model="q"
                class="form-control form-control-sm"
                placeholder="nmID, артикул WB или название"
                autocomplete="off"
                @keyup.enter="loadCards"
              />
              <span v-if="loading" class="spinner-border spinner-border-sm text-secondary"></span>
            </div>
            <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="loadCards">Найти</button>
          </div>

          <div v-if="selectedTargets.length" class="page-pick__chips">
            <span class="page-pick__chips-label">Цели:</span>
            <button
              v-for="c in selectedTargets"
              :key="c.nmID"
              type="button"
              class="page-pick__chip page-pick__chip--target"
              :title="c.title || ''"
              @click="removeTarget(c)"
            >
              {{ c.nmID }} <i class="bi bi-x"></i>
            </button>
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
              :class="{ 'is-picked': isTarget(c.nmID) }"
            >
              <input type="checkbox" :checked="isTarget(c.nmID)" @change="toggleTarget(c)" />
              <span class="page-pick__target-nm">{{ c.nmID }}</span>
              <span class="page-pick__target-vendor">{{ c.vendor_code || '—' }}</span>
              <span class="page-pick__target-title" :title="c.title || ''">{{ c.title || 'без названия' }}</span>
              <span class="badge bg-light text-dark">конкуренты: {{ c.competitors_cnt }}</span>
            </label>
          </div>
        </div>

        <div class="page-pick__bulk-preview">
          Привязок: <b>{{ selectedTargets.length ? preview.added + preview.exists + preview.skipped : 0 }}</b>
          · добавится: <b>{{ preview.added }}</b>
          · уже есть: <b>{{ preview.exists }}</b>
          · пропущено: <b>{{ preview.skipped }}</b>
        </div>

        <div v-if="error" class="wb-error">{{ error }}</div>
      </div>

      <div class="page-pick__bulk-footer">
        <button type="button" class="btn btn-sm btn-outline-secondary" :disabled="saving" @click="$emit('close')">
          Отмена
        </button>
        <button
          type="button"
          class="btn btn-sm btn-success"
          :disabled="saving || !selectedTargets.length || !preview.added"
          @click="attach"
        >
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-link-45deg"></i>
          Привязать
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor-pick.css'
import { computed, ref, watch } from 'vue'
import { competitorsNewcardApi, type PickAttachResult, type PickCard } from '../../api/competitorsNewcard'

interface BulkCandidate {
  nm_id: number
  title?: string | null
  is_hidden?: boolean
  is_own?: boolean
  attached?: Array<{ nm_id: number; title?: string | null }>
}

const props = defineProps<{
  open: boolean
  candidates: BulkCandidate[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'changed', result: PickAttachResult): void
}>()

const q = ref('')
const options = ref<PickCard[]>([])
const selectedTargets = ref<PickCard[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | null = null
let seq = 0

const preview = computed(() => {
  let added = 0
  let exists = 0
  let skipped = 0
  for (const c of props.candidates) {
    for (const t of selectedTargets.value) {
      if ((c.attached || []).some((a) => Number(a.nm_id) === t.nmID)) {
        exists++
      } else if (c.is_hidden || c.is_own) {
        skipped++
      } else {
        added++
      }
    }
  }
  return { added, exists, skipped }
})

function isTarget(nm: number): boolean {
  return selectedTargets.value.some((c) => c.nmID === nm)
}

function toggleTarget(c: PickCard) {
  const i = selectedTargets.value.findIndex((x) => x.nmID === c.nmID)
  if (i >= 0) selectedTargets.value.splice(i, 1)
  else selectedTargets.value.push(c)
}

function removeTarget(c: PickCard) {
  selectedTargets.value = selectedTargets.value.filter((x) => x.nmID !== c.nmID)
}

async function loadCards() {
  const my = ++seq
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.pickCards(q.value.trim(), 50)
    if (my !== seq) return
    options.value = d.items || []
  } catch (e: any) {
    if (my !== seq) return
    options.value = []
    error.value = e?.response?.data?.detail || 'Не удалось загрузить наши карточки'
  } finally {
    if (my === seq) loading.value = false
  }
}

async function attach() {
  if (saving.value || !selectedTargets.value.length) return
  saving.value = true
  error.value = ''
  try {
    const res = await competitorsNewcardApi.pickAttach({
      nm_ids: props.candidates.map((c) => c.nm_id),
      target_nm_ids: selectedTargets.value.map((c) => c.nmID),
      mode: 'captured',
    })
    emit('changed', res)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось привязать конкурентов'
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
  selectedTargets.value = []
  options.value = []
  error.value = ''
  loadCards()
})

watch(q, (v) => {
  if (timer) clearTimeout(timer)
  const value = String(v || '').trim()
  if (value.length === 1) return
  timer = setTimeout(loadCards, 300)
})
</script>
