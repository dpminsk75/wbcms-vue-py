<template>
  <div class="container-xxl page-stop-words">
    <WbWorkspaceHead :title="$route.meta.title || 'Стоп-слова'" :workspace-tabs="FEEDBACK_TABS" workspace-active="rules"
                  :subtabs="FEEDBACK_RULES_SUB_TABS" />

    <p class="page-stop-words__hint">
      Если слово встретится в тексте/плюсах/минусах отзыва — автоответ не отправится
      (ни в тесте, ни в cron). Слова хранятся в нижнем регистре.
    </p>

    <form class="page-stop-words__form" @submit.prevent="onAdd">
      <input v-model="newWord" class="wb-input" maxlength="100" placeholder="Новое стоп-слово или фраза..." />
      <button type="submit" class="btn btn--brand text-nowrap" :disabled="!newWord.trim() || saving">
        <i class="bi bi-plus-lg me-1"></i>Добавить
      </button>
      <router-link to="/wb-feedback-reply-rules" class="btn btn--outline text-nowrap">
        <i class="bi bi-list me-1"></i>К правилам
      </router-link>
    </form>
    <div v-if="error" class="page-stop-words__error">{{ error }}</div>

    <!-- Таблица стоп-слов — блок темы .tbl-card -->
    <div class="tbl-card page-stop-words__card">
      <div class="card__hd">
        <span>Стоп-слова</span>
        <span class="hd-badge">Всего: {{ rows.length }}</span>
      </div>

      <div v-if="isLoading" class="page-stop-words__loading">Загрузка данных…</div>
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Слово</th>
              <th class="t-left">Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in rows" :key="w.id">
              <td class="t-left page-stop-words__word">{{ w.word }}</td>
              <td class="t-left">
                <span class="badge" :class="w.is_active ? 'badge--ok' : 'badge--neutral'">{{ w.is_active ? 'Активно' : 'Выключено' }}</span>
              </td>
              <td class="t-right num">
                <button class="btn btn--outline btn-sm me-1" :title="w.is_active ? 'Выключить' : 'Включить'" @click="onToggle(w)">
                  <i class="bi" :class="w.is_active ? 'bi-toggle-on' : 'bi-toggle-off'"></i>
                </button>
                <button class="btn btn--danger btn-sm" title="Удалить" @click="onDelete(w)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!rows.length"><td colspan="3" class="t-center page-stop-words__empty">Стоп-слов пока нет</td></tr>
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
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS, FEEDBACK_RULES_SUB_TABS } from '@/components/common/workspaceTabs'

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
