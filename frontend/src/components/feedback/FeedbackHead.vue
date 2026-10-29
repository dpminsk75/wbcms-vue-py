<template>
  <!-- Шапка блока «Отзывы»: заголовок (H1) + меню раздела справа в углу,
       ниже — подменю раздела пилюлями (как /seo/index). -->
  <div class="wb-workspace-head">
    <h1 class="page-title">{{ title }}</h1>
    <WbWorkspaceTabs :active="active" :tabs="FEEDBACK_TABS" />
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
import { FEEDBACK_TABS, type SubTab } from '@/components/common/workspaceTabs'

withDefaults(defineProps<{
  /** Заголовок страницы (H1). */
  title: string
  /** Активный пункт меню раздела (id из FEEDBACK_TABS). */
  active?: string
  /** Подменю раздела (пилюли под заголовком). */
  subtabs?: SubTab[]
}>(), { active: '', subtabs: () => [] })

const route = useRoute()

/** Активен ли пункт подменю: сравниваем путь и (если есть) query. */
function isActive(t: SubTab): boolean {
  const [path, query] = t.to.split('?')
  if (route.path !== path) return false
  if (!query) return true
  return route.fullPath.includes(query)
}
</script>
