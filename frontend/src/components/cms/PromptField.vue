<template>
  <div class="prompt-field">
    <div class="prompt-field__head">
      <label class="form-label mb-0">{{ label }}</label>
      <div class="prompt-field__actions">
        <button v-if="canEdit && !editing" class="btn btn-sm btn-outline-primary"
                @click="startEdit">
          <i class="bi bi-pencil"></i> Редактировать
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-muted small">Загрузка…</div>
    <div v-else-if="!prompt" class="prompt-field__empty">
      Промпт не задан. Разбор жалоб не запустится, пока промпт не заполнен.
    </div>
    <pre v-else class="prompt-field__text">{{ prompt }}</pre>

    <div v-if="editing" class="prompt-field__editor">
      <textarea v-model="draft" rows="16"
                class="form-control form-control-sm font-monospace"></textarea>
      <div class="prompt-field__row">
        <button class="btn btn-sm btn-outline-primary" :disabled="saving" @click="onSave">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          Сохранить
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="saving"
                @click="editing = false">Отмена</button>
        <span v-if="error" class="wb-error">{{ error }}</span>
      </div>
    </div>
    <div v-else-if="error" class="wb-error">{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { feedbackInsightsApi } from '@/api/feedbackInsights'
import { useAuthStore } from '@/stores/auth'

withDefaults(defineProps<{ label?: string }>(), {
  label: 'Промпт разбора жалоб',
})
const emit = defineEmits<{ (e: 'saved'): void }>()

const auth = useAuthStore()
const prompt = ref('')
const draft = ref('')
const editing = ref(false)
const saving = ref(false)
const loading = ref(false)
const error = ref('')

// global_admin или админ хотя бы одной компании (owner/admin + active)
const canEdit = computed(() => auth.isAdmin || auth.managesAny)

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!auth.memberships.length) await auth.loadMemberships().catch(() => {})
    const d = await feedbackInsightsApi.prompt()
    prompt.value = d.prompt || ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

function startEdit() {
  draft.value = prompt.value
  editing.value = true
  error.value = ''
}

async function onSave() {
  saving.value = true
  error.value = ''
  try {
    await feedbackInsightsApi.savePrompt(draft.value)
    prompt.value = draft.value
    editing.value = false
    emit('saved')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.prompt-field { margin-bottom: 12px; }
.prompt-field__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.prompt-field__empty { font-size: 12px; color: #b45309; }
.prompt-field__text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  line-height: 1.45;
  background: #f7f7fa;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  max-height: 190px;
  overflow-y: auto;
  margin: 6px 0 0;
}
.prompt-field__editor { margin-top: 6px; }
.prompt-field__editor textarea { font-size: 12px; line-height: 1.45; }
.prompt-field__row { display: flex; gap: 8px; align-items: center; margin-top: 6px; flex-wrap: wrap; }
</style>
