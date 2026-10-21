<template>
  <div v-if="open" class="wb-modal-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box page-captured__modal">
      <div class="page-captured__modal-head">
        <h5 class="page-captured__modal-title">
          <i class="bi bi-link-45deg"></i> Привязка
          <span class="badge bg-dark">{{ nmId }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="page-captured__attach-sub">{{ title || '—' }}</div>

      <div class="page-captured__attach-block">
        <div class="page-captured__attach-label">Привязан к нашим карточкам</div>
        <div v-if="!attached.length" class="text-muted small">Пока не привязан.</div>
        <div v-else class="page-captured__attach-list">
          <div v-for="a in attached" :key="a.nm_id" class="page-captured__attach-row">
            <a :href="`/wb/detail?nm_id=${a.nm_id}`" target="_blank">{{ a.nm_id }}</a>
            <span class="page-captured__attach-title">{{ a.title || '—' }}</span>
            <button class="btn btn-sm btn-outline-danger" :disabled="busy" @click="detach(a.nm_id)">
              <i class="bi bi-x-lg"></i> Отвязать
            </button>
          </div>
        </div>
      </div>

      <div class="page-captured__attach-block">
        <div class="page-captured__attach-label">Привязать к нашим карточкам</div>

        <div class="page-captured__card-search">
          <i class="bi bi-search page-captured__card-search-icon"></i>
          <input
            v-model="search"
            class="form-control form-control-sm"
            placeholder="nmID, артикул WB или название"
            :disabled="busy"
            autocomplete="off"
          />
          <span v-if="searching" class="spinner-border spinner-border-sm text-secondary"></span>
          <button
            v-if="search"
            type="button"
            class="btn btn-sm btn-outline-secondary"
            title="Очистить"
            :disabled="busy"
            @click="search = ''"
          >
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <div v-if="selected.length" class="page-captured__picked">
          <span class="page-captured__attach-label">Выбрано: {{ selected.length }}</span>
          <button
            v-for="c in selected"
            :key="c.nmID"
            type="button"
            class="page-captured__picked-chip"
            :disabled="busy"
            :title="c.title || ''"
            @click="toggle(c)"
          >
            {{ c.nmID }} <i class="bi bi-x"></i>
          </button>
        </div>

        <div class="page-captured__pick-list">
          <div v-if="!options.length && !searching" class="text-muted small page-captured__pick-empty">
            {{ search.trim().length === 1 ? 'Введите минимум 2 символа.' : 'Ничего не найдено.' }}
          </div>
          <label
            v-for="c in options"
            :key="c.nmID"
            class="page-captured__pick"
            :class="{ 'is-picked': isSelected(c.nmID), 'is-attached': isAttached(c.nmID) }"
          >
            <input
              type="checkbox"
              :checked="isSelected(c.nmID)"
              :disabled="busy || isAttached(c.nmID)"
              @change="toggle(c)"
            />
            <span class="page-captured__pick-nm">{{ c.nmID }}</span>
            <span class="page-captured__pick-vendor">{{ c.vendorCode || '—' }}</span>
            <span class="page-captured__pick-title" :title="c.title || ''">{{ c.title || 'без названия' }}</span>
            <span v-if="isAttached(c.nmID)" class="badge bg-success">привязана</span>
          </label>
        </div>

        <div class="page-captured__attach-form mt-2">
          <button
            class="btn btn-sm btn-primary"
            :disabled="busy || !selected.length"
            @click="attachSelected"
          >
            <span v-if="busy" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-link-45deg"></i>
            Привязать выбранные{{ selected.length ? ` (${selected.length})` : '' }}
          </button>
          <button
            v-if="selected.length"
            class="btn btn-sm btn-outline-secondary"
            :disabled="busy"
            @click="selected = []"
          >
            Снять выбор
          </button>
          <span v-if="progress" class="text-muted small">{{ progress }}</span>
        </div>

        <div class="page-captured__hint">
          Привязка добавляет конкурента в нашу карточку (`source='capture'`). Контент и история не меняются.
          Поиск идёт по всем карточкам компании: nmID, артикул WB, название.
        </div>
      </div>

      <div v-if="error" class="text-danger small">{{ error }}</div>
      <div v-if="notice" class="text-success small">{{ notice }}</div>

      <div class="wb-modal-actions">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  competitorsNewcardApi,
  type CapturedAttachedCard,
  type WbCardOption,
} from '../../api/competitorsNewcard'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  title?: string | null
  attached: CapturedAttachedCard[]
}>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const options = ref<WbCardOption[]>([])
const selected = ref<WbCardOption[]>([])
const search = ref('')
const searching = ref(false)
const busy = ref(false)
const progress = ref('')
const error = ref('')
const notice = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
let reqSeq = 0

function isSelected(nm: number): boolean {
  return selected.value.some((c) => c.nmID === nm)
}

function isAttached(nm: number): boolean {
  return (props.attached || []).some((a) => Number(a.nm_id) === nm)
}

function toggle(c: WbCardOption) {
  if (busy.value || isAttached(c.nmID)) return
  const i = selected.value.findIndex((x) => x.nmID === c.nmID)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(c)
}

async function loadOptions(q: string) {
  const my = ++reqSeq
  searching.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.searchCards(q, 30)
    if (my !== reqSeq) return
    options.value = d
  } catch (e: any) {
    if (my !== reqSeq) return
    options.value = []
    error.value = e?.response?.data?.detail || 'Не удалось загрузить карточки'
  } finally {
    if (my === reqSeq) searching.value = false
  }
}

watch(search, (v) => {
  if (!props.open) return
  if (searchTimer) clearTimeout(searchTimer)
  const q = String(v || '').trim()
  if (q && q.length < 2) {
    reqSeq++
    options.value = []
    searching.value = false
    return
  }
  searchTimer = setTimeout(() => loadOptions(q), 300)
})

async function attachSelected() {
  const nm = Number(props.nmId || 0)
  if (!nm || !selected.value.length || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  let added = 0
  let exists = 0
  let failed = 0
  let lastError = ''
  const total = selected.value.length
  for (let i = 0; i < total; i++) {
    const sourceNm = selected.value[i].nmID
    progress.value = `${i + 1} из ${total}…`
    try {
      const r = await competitorsNewcardApi.attachCaptured(nm, sourceNm)
      if (r.exists) exists++
      else added++
    } catch (e: any) {
      failed++
      lastError = e?.response?.data?.detail || String(e)
    }
  }
  const parts: string[] = []
  if (added) parts.push(`привязано: ${added}`)
  if (exists) parts.push(`уже было: ${exists}`)
  if (failed) parts.push(`ошибок: ${failed}`)
  notice.value = parts.join(', ') || 'Готово'
  if (failed && !added && !exists) error.value = lastError || 'Не удалось привязать'
  selected.value = []
  progress.value = ''
  busy.value = false
  emit('changed')
}

async function detach(sourceNm: number) {
  const nm = Number(props.nmId || 0)
  if (!nm || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await competitorsNewcardApi.detachCaptured(nm, sourceNm)
    notice.value = `Отвязано от ${sourceNm}`
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось отвязать'
  } finally {
    busy.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    search.value = ''
    selected.value = []
    options.value = []
    progress.value = ''
    error.value = ''
    notice.value = ''
    loadOptions('')
  },
)

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  reqSeq++
})
</script>
