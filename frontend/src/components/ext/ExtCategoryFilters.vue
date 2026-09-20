<template>
  <div class="ext-catfilters">
    <h3 class="ext-catfilters__title">Фильтры категорий</h3>
    <div class="text-muted small">Именованные наборы subject-id для выдачи WB. Расширение подтягивает их в дропдаун само; пока пресетов нет — там только «Без фильтра» и дефолт «Книги и журналы».</div>
    <div v-if="error" class="wb-error">{{ error }}</div>
    <div v-if="loading" class="text-muted">Загрузка…</div>
    <table v-else-if="rows.length" class="wb-admin-table ext-catfilters__table">
      <thead>
        <tr>
          <th>Название</th>
          <th>Subject id</th>
          <th class="text-center">Вкл</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>
            <span v-if="editing !== r.id">{{ r.name }}</span>
            <input v-else v-model="editForm.name" maxlength="100" class="form-control form-control-sm" />
          </td>
          <td>
            <span v-if="editing !== r.id"><code>{{ r.subjects }}</code></span>
            <input v-else v-model="editForm.subjects" placeholder="381;397;1132" class="form-control form-control-sm ext-catfilters__input" />
          </td>
          <td class="text-center">
            <input type="checkbox" :checked="!!r.is_active" @change="onToggle(r, ($event.target as HTMLInputElement).checked)" class="form-check-input" title="Показывать в расширении" />
          </td>
          <td class="ext-catfilters__actions">
            <template v-if="editing === r.id">
              <button @click="onSaveEdit(r)" class="btn btn-sm btn-outline-primary">✓</button>
              <button @click="editing = null" class="btn btn-sm btn-outline-secondary">✕</button>
            </template>
            <template v-else>
              <button @click="startEdit(r)" class="btn btn-sm btn-outline-secondary" title="Переименовать / сменить id"><i class="bi bi-pencil"></i></button>
              <button @click="onRemove(r)" class="ext-catfilters__revoke" title="Удалить пресет">Удалить</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="text-muted small">пресетов пока нет</div>
    <form @submit.prevent="onCreate" class="ext-catfilters__form">
      <input v-model="name" placeholder="Канцтовары" maxlength="100" class="form-control form-control-sm ext-catfilters__input" />
      <input v-model="subjects" placeholder="id через ; пробел ," class="form-control form-control-sm ext-catfilters__input" title="Числовые id subject, разделитель ; , или пробел" />
      <button type="submit" :disabled="creating" class="btn btn-outline-secondary btn-sm"><i class="bi bi-plus"></i> Добавить</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { extCategoryApi, type ExtCategoryFilter } from '../../api/extTokens'

const props = defineProps<{ companyId: number }>()

const rows = ref<ExtCategoryFilter[]>([])
const loading = ref(false)
const creating = ref(false)
const name = ref('')
const subjects = ref('')
const error = ref('')
const editing = ref<number | null>(null)
const editForm = reactive({ name: '', subjects: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await extCategoryApi.list(props.companyId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  creating.value = true
  error.value = ''
  try {
    await extCategoryApi.create(props.companyId, { name: name.value.trim(), subjects: subjects.value.trim() })
    name.value = ''
    subjects.value = ''
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    creating.value = false
  }
}

function startEdit(r: ExtCategoryFilter) {
  editing.value = r.id
  editForm.name = r.name
  editForm.subjects = r.subjects
}

async function onSaveEdit(r: ExtCategoryFilter) {
  error.value = ''
  try {
    const upd = await extCategoryApi.update(props.companyId, r.id, { name: editForm.name.trim(), subjects: editForm.subjects.trim() })
    Object.assign(r, upd)
    editing.value = null
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

async function onToggle(r: ExtCategoryFilter, on: boolean) {
  error.value = ''
  try {
    const upd = await extCategoryApi.update(props.companyId, r.id, { is_active: on })
    Object.assign(r, upd)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
    await load()
  }
}

async function onRemove(r: ExtCategoryFilter) {
  if (!confirm(`Удалить пресет «${r.name}»?`)) return
  error.value = ''
  try {
    await extCategoryApi.remove(props.companyId, r.id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
}

onMounted(load)
</script>

<style scoped>
.ext-catfilters { border: 1px solid #ddd; padding: 14px; border-radius: 8px; max-width: 640px; margin-top: 16px; }
.ext-catfilters__title { margin: 0 0 2px; font-size: 17px; }
.ext-catfilters__table { margin: 10px 0; }
.ext-catfilters__form { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.ext-catfilters__input { max-width: 200px; }
.ext-catfilters__actions { white-space: nowrap; }
.ext-catfilters__actions .btn { margin-right: 4px; }
.ext-catfilters__revoke { color: #c00; background: none; border: none; padding: 0; cursor: pointer; }
</style>
