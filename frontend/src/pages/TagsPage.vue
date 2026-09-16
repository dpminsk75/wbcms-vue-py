<template>
  <div class="container-xxl page-tag-index">
    <div class="page-tag-index__header">
      <h1 class="page-title page-tag-index__title">
        Теги
        <span class="page-tag-index__count">{{ items.length }}</span>
      </h1>
      <router-link to="/tags/create" class="btn btn-success">
        <i class="bi bi-plus-lg me-1"></i>Создать тег
      </router-link>
    </div>

    <div class="card page-tag-index__panel">
      <div v-if="isLoading" class="p-4 text-center text-muted">Загрузка...</div>
      <div v-else-if="error" class="p-4 text-center text-danger">Не удалось загрузить теги.</div>
      <div v-else class="wb-table-wrap page-tag-index__table-wrap">
        <table class="table table-hover mb-0 page-tag-index__table">
          <thead>
            <tr>
              <th class="page-tag-index__th--priority">Приоритет</th>
              <th>Название</th>
              <th>Группа</th>
              <th class="page-tag-index__th--count">Карточек</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in items" :key="t.id">
              <td class="text-center"><span class="page-tag-index__priority">{{ t.priority }}</span></td>
              <td><span class="page-tag-index__pill" :style="{ background: t.color }">{{ t.name }}</span></td>
              <td><span v-if="t.tag_group" class="page-tag-index__group">{{ t.tag_group }}</span><span v-else class="text-muted">—</span></td>
              <td class="text-center"><span class="page-tag-index__cards"><i class="bi bi-layers me-1"></i>{{ t.cards_count }}</span></td>
              <td class="text-end page-tag-index__actions">
                <router-link :to="`/tags/${t.id}`" class="page-tag-index__action page-tag-index__action--view" title="Аналитика"><i class="bi bi-graph-up"></i></router-link>
                <router-link :to="`/tags/${t.id}/edit`" class="page-tag-index__action page-tag-index__action--update" title="Редактировать"><i class="bi bi-pen"></i></router-link>
                <button type="button" class="page-tag-index__action page-tag-index__action--delete" title="Удалить" @click="onDelete(t)"><i class="bi bi-trash"></i></button>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="5" class="text-center text-muted p-4">Теги пока не созданы</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-index.css'
import { ref, onMounted } from 'vue'
import { tagsApi, type TagItem } from '@/api/tags'

const items = ref<TagItem[]>([])
const isLoading = ref(false)
const error = ref('')

async function fetchData() {
  isLoading.value = true
  error.value = ''
  try {
    items.value = await tagsApi.list()
  } catch {
    error.value = 'load'
  } finally {
    isLoading.value = false
  }
}

async function onDelete(t: TagItem) {
  if (!confirm('Удалить этот тег?')) return
  try {
    await tagsApi.remove(t.id)
    items.value = items.value.filter((x) => x.id !== t.id)
  } catch (e: any) {
    alert(e?.response?.data?.detail || String(e))
  }
}

onMounted(fetchData)
</script>
