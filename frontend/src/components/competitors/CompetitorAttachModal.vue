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
        <div class="page-captured__attach-label">Новая привязка</div>
        <div class="page-captured__attach-form">
          <select v-model="picked" class="form-select form-select-sm" :disabled="busy">
            <option value="">— выберите новую карточку —</option>
            <option v-for="c in cards" :key="c.nmID" :value="String(c.nmID)">
              {{ c.nmID }} — {{ c.title || 'без названия' }}
            </option>
          </select>
          <button class="btn btn-sm btn-primary" :disabled="busy || !picked" @click="attach(Number(picked))">
            <i class="bi bi-link-45deg"></i> Привязать
          </button>
        </div>
        <div class="page-captured__attach-form mt-2">
          <input
            v-model="manualNm"
            class="form-control form-control-sm"
            placeholder="или любой наш nmID"
            :disabled="busy"
            @keyup.enter="attach(Number(manualNm))"
          />
          <button class="btn btn-sm btn-outline-primary" :disabled="busy || !Number(manualNm)" @click="attach(Number(manualNm))">
            Привязать
          </button>
        </div>
        <div class="page-captured__hint">
          Привязка добавляет конкурента в нашу карточку (`source='capture'`). Контент и история не меняются.
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
import { ref, watch } from 'vue'
import {
  competitorsNewcardApi,
  type CapturedAttachedCard,
  type NewCardRow,
} from '../../api/competitorsNewcard'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  title?: string | null
  attached: CapturedAttachedCard[]
}>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const cards = ref<NewCardRow[]>([])
const picked = ref('')
const manualNm = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')

async function loadCards() {
  try {
    const d = await competitorsNewcardApi.list('', 300)
    cards.value = d.items || []
  } catch {
    cards.value = []
  }
}

async function attach(sourceNm: number) {
  const nm = Number(props.nmId || 0)
  if (!nm || !sourceNm || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await competitorsNewcardApi.attachCaptured(nm, sourceNm)
    notice.value = r.exists ? `Уже привязано к ${sourceNm}` : `Привязано к ${sourceNm}`
    picked.value = ''
    manualNm.value = ''
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось привязать'
  } finally {
    busy.value = false
  }
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
    picked.value = ''
    manualNm.value = ''
    error.value = ''
    notice.value = ''
    if (!cards.value.length) loadCards()
  },
)
</script>
