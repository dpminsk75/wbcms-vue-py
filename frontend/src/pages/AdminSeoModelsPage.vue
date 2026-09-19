<template>
  <div class="container-xxl page-admin-seo-models">
    <h2 class="page-admin-seo-models__title">SEO-модели</h2>
    <p class="text-muted">Ротация AI-моделей: воркеры берут по приоритету среди активных без кулдауна, итоги пишут сами. Ручки тут — поверх авто-приоритетов bench.</p>

    <div v-if="error" class="wb-error">{{ error }}</div>

    <div class="page-admin-seo-models__apply">
      <strong>Применить ко всем компаниям:</strong>
      <input v-model="applyModel" placeholder="vendor/model:free" class="form-control form-control-sm page-admin-seo-models__apply-input" />
      <button @click="onApply(true)" :disabled="applying" class="btn btn-sm btn-outline-secondary" title="Показать, что изменится, без записи">Предпросмотр</button>
      <button @click="onApply(false)" :disabled="applying" class="btn btn-sm btn-outline-primary" title="Заменить дохлые части companies.seo_model">Применить</button>
      <span v-if="applyResult" class="page-admin-seo-models__apply-result">заменено компаний: {{ applyResult.replaced }}</span>
    </div>
    <div v-if="preview.length" class="wb-table-wrap">
      <table class="wb-admin-table page-admin-seo-models__preview">
        <thead><tr><th>Компания</th><th>Было</th><th>Станет</th></tr></thead>
        <tbody>
          <tr v-for="p in preview" :key="p.company_id">
            <td>{{ p.company_id }}</td>
            <td><code>{{ p.old }}</code></td>
            <td><code>{{ p.new }}</code></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="text-muted">Загрузка…</div>
    <div v-else-if="!rows.length" class="alert alert-info">Моделей нет — прогоните bench (<code>backend/scripts/bench_models.py</code>).</div>
    <div v-else class="wb-table-wrap">
      <table class="wb-admin-table page-admin-seo-models__grid">
        <thead>
          <tr>
            <th>Модель</th>
            <th class="text-center">Вкл</th>
            <th>Приоритет</th>
            <th class="text-center" title="Успешных / ошибок / подряд ошибок">Усп / Ош / Подряд</th>
            <th>Кулдаун</th>
            <th>Последняя ошибка</th>
            <th>Успех</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.model_id" :class="{ 'page-admin-seo-models__row--off': !r.is_active }">
            <td>
              <div class="page-admin-seo-models__model" :title="r.model_id">{{ r.model_id }}</div>
              <div v-if="r.title && r.title !== r.model_id" class="text-muted small">{{ r.title }}</div>
              <div v-if="r.ctx" class="text-muted small">ctx {{ r.ctx }}</div>
            </td>
            <td class="text-center">
              <input type="checkbox" :checked="r.is_active" @change="onToggle(r, ($event.target as HTMLInputElement).checked)" class="form-check-input" :title="r.is_active ? 'Выключить' : 'Включить'" />
            </td>
            <td>
              <div class="page-admin-seo-models__prio">
                <input v-model.number="prioEdits[r.model_id]" type="number" min="1" max="200" :placeholder="String(r.priority ?? '')" class="form-control form-control-sm page-admin-seo-models__prio-input" />
                <button @click="onPrio(r)" class="btn btn-sm btn-outline-secondary" title="Сохранить приоритет">✓</button>
              </div>
            </td>
            <td class="text-center">{{ r.success_count ?? 0 }} / {{ r.error_count ?? 0 }} / {{ r.consecutive_errors ?? 0 }}</td>
            <td>
              <span v-if="r.cooldown_until">{{ fmtDT(r.cooldown_until) }}</span>
              <span v-else class="text-muted">—</span>
              <button v-if="r.cooldown_until || (r.consecutive_errors ?? 0) > 0" @click="onReset(r)" class="btn btn-sm btn-link page-admin-seo-models__reset" title="Сбросить кулдаун и счётчик">сброс</button>
            </td>
            <td class="page-admin-seo-models__err" :title="r.last_error || ''">{{ r.last_error ? shortErr(r.last_error) : '—' }}</td>
            <td class="small">{{ r.last_success_at ? fmtDT(r.last_success_at) : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="text-muted small mt-2">Бенч: <code>.venv/bin/python backend/scripts/bench_models.py --limit 6</code> (404 — выключить, 429 — кулдаун, ок — приоритет).</div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-admin-seo-models.css'
import { ref, reactive, onMounted } from 'vue'
import { seoModelsApi, type SeoModelRow } from '../api/seoModels'

const rows = ref<SeoModelRow[]>([])
const loading = ref(false)
const error = ref('')
const prioEdits = reactive<Record<string, number | undefined>>({})
const applyModel = ref('')
const applying = ref(false)
const applyResult = ref<{ replaced: number } | null>(null)
const preview = ref<Array<{ company_id: number; old: string; new: string }>>([])

const fmtDT = (v: any) => v ? new Date(String(v).replace(' ', 'T')).toLocaleString('ru-RU') : '—'
const shortErr = (e: string) => e.length > 80 ? e.slice(0, 80) + '…' : e

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await seoModelsApi.list()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function onToggle(r: SeoModelRow, on: boolean) {
  error.value = ''
  try {
    const upd = await seoModelsApi.patch(r.model_id, { is_active: on })
    Object.assign(r, upd)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    await load()
  }
}

async function onPrio(r: SeoModelRow) {
  const p = prioEdits[r.model_id]
  if (p == null) return
  error.value = ''
  try {
    const upd = await seoModelsApi.patch(r.model_id, { priority: p })
    Object.assign(r, upd)
    prioEdits[r.model_id] = undefined
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

async function onReset(r: SeoModelRow) {
  error.value = ''
  try {
    await seoModelsApi.resetCooldown(r.model_id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

async function onApply(dryRun: boolean) {
  if (!applyModel.value.trim()) { error.value = 'Укажите model_id'; return }
  applying.value = true
  error.value = ''
  applyResult.value = null
  preview.value = []
  try {
    const out = await seoModelsApi.apply(applyModel.value.trim(), dryRun)
    applyResult.value = { replaced: out.replaced }
    if (dryRun) preview.value = out.companies as Array<{ company_id: number; old: string; new: string }>
    else if (out.replaced) await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    applying.value = false
  }
}

onMounted(load)
</script>
