<template>
  <div class="cms-block">
    <div v-if="error" class="wb-error">{{ error }}</div>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-html="html"></div>
    <div v-if="isGlobal" class="cms-block__admin">
      <button v-if="!editing" @click="startEdit" class="btn btn-sm btn-outline-primary cms-block__edit" title="Править текст (Markdown)"><i class="bi bi-pencil"></i> Редактировать</button>
      <template v-else>
        <div class="cms-block__tabs">
          <button @click="previewOn = false" :class="['btn btn-sm', previewOn ? 'btn-outline-secondary' : 'btn-secondary']">Текст</button>
          <button @click="previewOn = true" :class="['btn btn-sm', previewOn ? 'btn-secondary' : 'btn-outline-secondary']">Превью</button>
        </div>
        <textarea v-if="!previewOn" v-model="draft" rows="8" class="form-control form-control-sm" placeholder="Markdown: **жирный**, - список, [текст](/url), `код`"></textarea>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-else v-html="draftHtml" class="cms-block__preview"></div>
        <div class="cms-block__row">
          <button @click="onSave" :disabled="saving" class="btn btn-sm btn-outline-primary">Сохранить</button>
          <button @click="editing = false" class="btn btn-sm btn-outline-secondary">Отмена</button>
          <span class="text-muted small">Markdown, сырой HTML запрещён</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import { cmsApi } from '../../api/cms'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ blockKey: string; fallbackMd: string }>()

// html:false — сырой HTML из базы режется (без DOMPurify и лишних deps), ссылки кликабельны.
const md = new MarkdownIt({ html: false, linkify: true })
const auth = useAuthStore()
const isGlobal = computed(() => auth.perms.includes('global_admin') || auth.roles.includes('global_admin'))

const body = ref('')
const error = ref('')
const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const previewOn = ref(false)
const html = computed(() => md.render(body.value || props.fallbackMd))
const draftHtml = computed(() => md.render(draft.value))

async function load() {
  try {
    const b = await cmsApi.get(props.blockKey)
    body.value = b.body_md || ''
  } catch {
    body.value = '' // нет строки/нет миграции — вшитый fallback
  }
}

function startEdit() {
  draft.value = body.value || props.fallbackMd
  editing.value = true
}

async function onSave() {
  saving.value = true
  error.value = ''
  try {
    const b = await cmsApi.put(props.blockKey, { body_md: draft.value })
    body.value = b.body_md || ''
    editing.value = false
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.cms-block__admin { margin-top: 6px; }
.cms-block__edit { padding: 0; font-size: 12px; }
.cms-block__row { display: flex; gap: 8px; align-items: center; margin-top: 6px; flex-wrap: wrap; }
.cms-block textarea { font-family: monospace; font-size: 12px; }
.cms-block__tabs { display: flex; gap: 4px; margin-bottom: 6px; }
.cms-block__preview { border: 1px dashed #ccc; border-radius: 6px; padding: 8px 10px; }
</style>
