<template>
  <div class="container-xxl page-tag-index">
    <WbWorkspaceHead title="Список тегов" :workspace-tabs="TAGS_WORKSPACE_TABS" workspace-active="list" />

    <div class="wb-panel page-tag-index__panel">
      <div class="card__hd">
        <span>Список тегов</span>
        <span class="spacer"></span>
        <span class="hd-badge">Тегов: {{ items.length }}</span>
        <router-link to="/tags/create" class="hd-btn">
          <i class="bi bi-plus-lg"></i>Создать тег
        </router-link>
      </div>

      <div v-if="isLoading" class="wb-panel__bd page-tag-index__state">Загрузка…</div>
      <div v-else-if="error" class="wb-panel__bd page-tag-index__state page-tag-index__state--bad">
        {{ error }}
      </div>
      <div v-else class="tbl-wrap">
        <table class="tbl page-tag-index__table">
          <thead>
            <tr>
              <th class="t-center page-tag-index__th--priority">Приоритет</th>
              <th class="t-left">Название</th>
              <th class="t-left">Группа</th>
              <th class="t-center page-tag-index__th--count">Карточек</th>
              <th class="t-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in items" :key="t.id">
              <td class="t-center"><span class="page-tag-index__priority">{{ t.priority }}</span></td>
              <td class="t-left">
                <span class="page-tag-index__pill" :style="{ background: t.color }">{{ t.name }}</span>
              </td>
              <td class="t-left">
                <span v-if="t.tag_group" class="page-tag-index__group">{{ t.tag_group }}</span>
                <span v-else class="page-tag-index__muted">—</span>
              </td>
              <td class="t-center">
                <span class="badge badge--neutral"><i class="bi bi-layers"></i> {{ t.cards_count }}</span>
              </td>
              <td class="t-right page-tag-index__actions">
                <router-link :to="`/tags/${t.id}`" class="page-tag-index__action" title="Аналитика">
                  <i class="bi bi-graph-up"></i>
                </router-link>
                <router-link :to="`/tags/${t.id}/edit`" class="page-tag-index__action" title="Редактировать">
                  <i class="bi bi-pen"></i>
                </router-link>
                <button
                  type="button"
                  class="page-tag-index__action page-tag-index__action--delete"
                  title="Удалить"
                  @click="askDelete(t)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="5" class="t-center page-tag-index__muted page-tag-index__empty">Теги пока не созданы</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Подтверждение удаления — общий диалог темы (не confirm(): он блокирует поток страницы) -->
    <WbConfirmDialog
      :open="!!deleteTarget"
      text="Удалить этот тег?"
      :hint="deleteTarget ? `«${deleteTarget.name}» — связи с карточками тоже будут сняты.` : ''"
      confirm-text="Удалить"
      danger
      :busy="deleting"
      @confirm="doDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-index.css'
import { ref, onMounted } from 'vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import WbConfirmDialog from '@/components/common/WbConfirmDialog.vue'
import { TAGS_WORKSPACE_TABS } from '@/components/common/workspaceTabs'
import { tagsApi, type TagItem } from '@/api/tags'

const items = ref<TagItem[]>([])
const isLoading = ref(false)
const error = ref('')
/** Тег, который пользователь собирается удалить (null — диалог закрыт). */
const deleteTarget = ref<TagItem | null>(null)
const deleting = ref(false)

async function fetchData() {
  isLoading.value = true
  error.value = ''
  try {
    items.value = await tagsApi.list()
  } catch {
    error.value = 'Не удалось загрузить теги.'
  } finally {
    isLoading.value = false
  }
}

function askDelete(t: TagItem) {
  deleteTarget.value = t
}

async function doDelete() {
  const t = deleteTarget.value
  if (!t || deleting.value) return
  deleting.value = true
  try {
    await tagsApi.remove(t.id)
    items.value = items.value.filter((x) => x.id !== t.id)
    deleteTarget.value = null
    error.value = ''
  } catch (e: any) {
    error.value = `Не удалось удалить тег: ${e?.response?.data?.detail || String(e)}`
    deleteTarget.value = null
  } finally {
    deleting.value = false
  }
}

onMounted(fetchData)
</script>
