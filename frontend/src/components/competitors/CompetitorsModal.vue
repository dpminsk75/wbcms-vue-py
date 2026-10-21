<template>
  <div v-if="open" class="page-wb-detail__modal-backdrop" @click.self="$emit('close')">
    <div class="page-wb-detail__modal-box page-wb-detail__modal-box--wide">
      <div class="page-wb-detail__modal-head">
        <h5 class="page-wb-detail__modal-title">
          <i class="bi bi-people"></i> Конкуренты
          <span class="page-wb-detail__modal-count">{{ items.length }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div class="page-wb-detail__add-row">
        <input
          v-model="addInput"
          class="form-control form-control-sm"
          placeholder="nmID конкурентов через запятую: 123456, 789012"
          :disabled="busy"
          @keyup.enter="addMany"
        />
        <button class="btn btn-sm btn-outline-primary" :disabled="busy || !addInput.trim()" @click="addMany">
          <i class="bi bi-plus-lg"></i> Добавить
        </button>
      </div>
      <div class="page-wb-detail__add-row">
        <input
          v-model="fromCard"
          class="form-control form-control-sm"
          placeholder="скопировать конкурентов с нашей карточки (nmID)"
          :disabled="busy"
          @keyup.enter="copyFrom"
        />
        <button class="btn btn-sm btn-outline-secondary" :disabled="busy || !fromCard.trim()" @click="copyFrom">
          <i class="bi bi-files"></i> Из карточки
        </button>
      </div>

      <div v-if="loading" class="text-muted small mt-2">
        <span class="spinner-border spinner-border-sm"></span> Загрузка...
      </div>
      <div v-if="error" class="text-danger small mt-2">{{ error }}</div>
      <div v-if="notice" class="text-success small mt-2">{{ notice }}</div>

      <div v-if="items.length" class="page-wb-detail__comp-list">
        <div v-for="c in items" :key="c.nm_id" class="page-wb-detail__comp-row">
          <img v-if="c.photo" :src="c.photo" class="page-wb-detail__comp-photo" alt="" loading="lazy" />
          <div v-else class="page-wb-detail__comp-photo page-wb-detail__comp-photo--empty"><i class="bi bi-image"></i></div>
          <div class="page-wb-detail__comp-main">
            <div class="page-wb-detail__comp-title">
              <a :href="'https://www.wildberries.ru/catalog/' + c.nm_id + '/detail.aspx'" target="_blank" rel="noopener">
                {{ c.title || 'nmID ' + c.nm_id }}
              </a>
            </div>
            <div class="page-wb-detail__comp-meta">
              <span class="badge bg-dark">{{ c.nm_id }}</span>
              <span v-if="c.brand">{{ c.brand }}</span>
              <span v-if="c.price">цена: {{ c.price }}</span>
              <span :class="c.desc_len ? 'text-success' : 'text-danger'">описание: {{ c.desc_len }} симв.</span>
              <span :class="c.chars_cnt ? 'text-success' : 'text-danger'">характеристик: {{ c.chars_cnt }}</span>
              <span v-if="c.manual" class="badge bg-info text-dark">вручную</span>
              <span v-if="c.sources.includes('capture')" class="badge bg-secondary">собрано</span>
            </div>
            <div class="page-wb-detail__comp-meta">
              <span v-if="c.phrases" class="text-muted">найден по: {{ c.phrases }}</span>
              <span v-else class="text-muted">добавлен вручную</span>
            </div>
          </div>
          <div class="page-wb-detail__comp-actions">
            <span v-if="c.analysis_status === 'analyzed'" class="badge bg-success">разобран</span>
            <span v-else-if="analyzing === c.nm_id" class="badge bg-warning text-dark">
              <span class="spinner-border spinner-border-sm"></span> анализ
            </span>
            <button
              v-else
              class="btn btn-sm btn-outline-primary"
              :disabled="!!analyzing"
              @click="analyze(c.nm_id)"
            >
              <i class="bi bi-stars"></i> Анализ
            </button>
          </div>
        </div>
      </div>
      <div v-else-if="!loading" class="text-muted small mt-3">
        Пока нет конкурентов — добавь nmID или скопируй с другой карточки.
      </div>

      <div class="page-wb-detail__modal-foot">
        <button class="btn btn-sm btn-outline-warning" :disabled="busy || !items.length" @click="makeSummary">
          <i class="bi bi-magic"></i> Сводка title + description
        </button>
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>

      <div v-if="summary" class="page-wb-detail__summary">
        <div class="page-wb-detail__summary-title">{{ summary.title || '—' }}</div>
        <div class="page-wb-detail__summary-desc">{{ summary.description }}</div>
        <div class="page-wb-detail__modal-footnote">
          конкурентов: {{ summary.competitor_count || 0 }}
          <span v-if="summary.model"> · модель: {{ summary.model }}</span>
          <span v-if="summary.created_at"> · {{ summary.created_at }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import { aiJobsApi } from '@/api/aiJobs'
import { competitorsNewcardApi, type CompetitorRow } from '@/api/competitorsNewcard'

const props = defineProps<{ open: boolean; nmId: number | string | null | undefined }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const items = ref<CompetitorRow[]>([])
const addInput = ref('')
const fromCard = ref('')
const busy = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const analyzing = ref<number | null>(null)
const summary = ref<any>(null)

const nm = () => Number(props.nmId || 0)

async function load() {
  const id = nm()
  if (!id) return
  loading.value = true
  error.value = ''
  try {
    const d = await competitorsNewcardApi.competitors(id)
    items.value = d.items || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось загрузить конкурентов'
    items.value = []
  } finally {
    loading.value = false
  }
}

function parseIds(raw: string): number[] {
  return String(raw)
    .split(/[^0-9]+/)
    .map((x) => Number(x))
    .filter((n) => Number.isFinite(n) && n > 0)
}

async function addMany() {
  const id = nm()
  const ids = parseIds(addInput.value)
  if (!id || !ids.length || busy.value) {
    if (!ids.length) error.value = 'Нужен хотя бы один nmID'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await competitorsNewcardApi.addCompetitors(id, ids)
    notice.value = `Добавлено: ${r.added} из ${r.requested}. Сбор запустится из попапа расширения.`
    addInput.value = ''
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось добавить конкурентов'
  } finally {
    busy.value = false
  }
}

async function copyFrom() {
  const id = nm()
  const src = Number(fromCard.value || 0)
  if (!id || !src || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const r = await competitorsNewcardApi.fromCard(id, src)
    notice.value = `Скопировано: ${r.added} конкурентов с карточки ${r.source_nm_id}.`
    fromCard.value = ''
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось скопировать'
  } finally {
    busy.value = false
  }
}

async function analyze(competitorNm: number) {
  const id = nm()
  if (!id || analyzing.value) return
  analyzing.value = competitorNm
  error.value = ''
  try {
    const { data } = await api.post('/api/competitors/analyze-direct', {
      source_nm_id: id,
      competitor_nm_id: competitorNm,
    })
    await pollJob(Number(data.job_id))
    await load()
    emit('changed')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось запустить анализ'
  } finally {
    analyzing.value = null
  }
}

async function pollJob(jobId: number) {
  const finished = new Set(['done', 'error', 'interrupted'])
  for (let i = 0; i < 300; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    try {
      const j = await aiJobsApi.get(jobId)
      if (finished.has(j.status)) {
        if (j.status !== 'done') error.value = j.error || 'Анализ завершился с ошибкой'
        return
      }
    } catch {
      return
    }
  }
  error.value = 'Анализ идёт дольше 10 минут — проверьте позже'
}

async function makeSummary() {
  const id = nm()
  if (!id || busy.value) return
  busy.value = true
  error.value = ''
  try {
    // force=false: пересчёт кэша 30д — только админ (не трогаем, §2 п.8 плана)
    const { data } = await api.post(`/api/competitors/${id}/summary`, {})
    if (data && data.success === false) {
      error.value = data.error || 'Сводка недоступна'
      summary.value = null
      return
    }
    const res = (data && data.result) || {}
    summary.value = data
      ? {
          title: res.title || '',
          description: res.description || '',
          competitor_count: data.competitor_count,
          model: data.cached_model,
          created_at: data.cached_at,
        }
      : null
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Не удалось получить сводку'
  } finally {
    busy.value = false
  }
}

watch(
  () => [props.open, props.nmId] as const,
  ([isOpen]) => {
    if (!isOpen) return
    addInput.value = ''
    fromCard.value = ''
    notice.value = ''
    error.value = ''
    summary.value = null
    load()
  },
)
</script>
