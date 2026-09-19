<template>
  <div class="container-xxl page-stop-words">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="page-title mb-0">{{ $route.meta.title || 'Стоп-слова' }}</h1>
      <router-link to="/wb-reply-rules" class="btn btn-outline-secondary">
        <i class="bi bi-list me-1"></i>К правилам
      </router-link>
    </div>

    <p class="text-muted small">Если слово встретится в тексте/плюсах/минусах отзыва — автоответ не отправится (ни в тесте, ни в cron). Слова хранятся в нижнем регистре.</p>

    <form class="d-flex gap-2 mb-3 page-stop-words__form" @submit.prevent="onAdd">
      <input v-model="newWord" class="form-control" maxlength="100" placeholder="Новое стоп-слово или фраза..." />
      <button type="submit" class="btn btn-success text-nowrap" :disabled="!newWord.trim() || saving">
        <i class="bi bi-plus-lg me-1"></i>Добавить
      </button>
    </form>
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

    <div v-if="isLoading" class="text-center p-5">
      <div class="spinner-border text-primary" role="status"></div>
      <div class="mt-2 text-muted">Загрузка данных...</div>
    </div>
    <div v-else class="card">
      <div class="wb-table-wrap">
        <table class="table table-striped table-bordered align-middle mb-0">
          <thead>
            <tr>
              <th>Слово</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in rows" :key="w.id">
              <td class="page-stop-words__word">{{ w.word }}</td>
              <td>
                <span class="badge" :class="w.is_active ? 'bg-success' : 'bg-secondary'">{{ w.is_active ? 'Активно' : 'Выключено' }}</span>
              </td>
              <td class="text-nowrap text-end">
                <button class="btn btn-sm btn-light me-1" :title="w.is_active ? 'Выключить' : 'Включить'" @click="onToggle(w)">
                  <i class="bi" :class="w.is_active ? 'bi-toggle-on' : 'bi-toggle-off'"></i>
                </button>
                <button class="btn btn-sm btn-light" title="Удалить" @click="onDelete(w)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!rows.length"><td colspan="3" class="text-center text-muted p-4">Стоп-слов пока нет</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-stop-words.css'
import { ref, onMounted } from 'vue'
import { replyRulesApi, type StopWord } from '@/api/replyRules'

const rows = ref<StopWord[]>([])
const newWord = ref('')
const saving = ref(false)
const error = ref('')
const isLoading = ref(false)

async function fetchData() {
  isLoading.value = true
  try {
    rows.value = await replyRulesApi.stopWords()
  } catch {
    rows.value = []
  } finally {
    isLoading.value = false
  }
}
async function onAdd() {
  saving.value = true
  error.value = ''
  try {
    await replyRulesApi.addStopWord(newWord.value.trim())
    newWord.value = ''
    await fetchData()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}
async function onToggle(w: StopWord) {
  const prev = !!w.is_active
  w.is_active = prev ? 0 : 1
  try {
    const res = await replyRulesApi.toggleStopWord(w.id)
    w.is_active = res.is_active ? 1 : 0
  } catch (e: any) {
    w.is_active = prev ? 1 : 0
    alert(e?.response?.data?.detail || 'Не удалось переключить')
  }
}
async function onDelete(w: StopWord) {
  if (!confirm(`Удалить стоп-слово «${w.word}»?`)) return
  try {
    await replyRulesApi.removeStopWord(w.id)
    rows.value = rows.value.filter((x) => x.id !== w.id)
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  }
}

onMounted(fetchData)
</script>
