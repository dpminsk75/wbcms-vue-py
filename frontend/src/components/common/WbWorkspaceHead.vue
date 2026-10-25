<template>
  <!-- Шапка рабочего места: название + общее меню (справа вверху),
       ниже — подменю раздела (пилюли с активным пунктом). -->
  <div class="wb-workspace-head">
    <h2 class="wb-workspace-head__title">{{ title }}</h2>
    <WbWorkspaceTabs :active="workspaceActive" :tabs="workspaceTabs" />
  </div>
  <ul v-if="subtabs.length" class="nav nav-pills wb-sub-tabs">
    <li v-for="t in subtabs" :key="t.id" class="nav-item">
      <router-link
        class="nav-link"
        :class="{ active: isActive(t) }"
        :to="t.to"
        :title="t.title"
      >
        {{ t.label }}<span v-if="t.count !== undefined && t.count !== null" class="wb-sub-tabs__count">{{ t.count }}</span>
      </router-link>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import WbWorkspaceTabs from '@/components/common/WbWorkspaceTabs.vue'
import { WORKSPACE_TABS, type SubTab, type WorkspaceTab } from '@/components/common/workspaceTabs'

const props = withDefaults(
  defineProps<{
    /** Заголовок рабочего места, например «Конкуренты: Подбор». */
    title: string
    /** Подменю раздела под заголовком. */
    subtabs?: SubTab[]
    /** Явная активная подвкладка; иначе — по текущему роуту. */
    activeSub?: string
    /** Активный пункт общего меню рабочего места. */
    workspaceActive?: string
    /** Общее меню рабочего места (по умолчанию — WORKSPACE_TABS). */
    workspaceTabs?: WorkspaceTab[]
  }>(),
  { subtabs: () => [], activeSub: '', workspaceActive: '', workspaceTabs: () => WORKSPACE_TABS },
)

const route = useRoute()

/** Активен ли пункт подменю: сравниваем путь и (если есть) query. */
function isActive(t: SubTab): boolean {
  if (props.activeSub) return t.id === props.activeSub
  const [path, query] = t.to.split('?')
  if (route.path !== path) return false
  if (!query) return true
  return route.fullPath.includes(query)
}
</script>
