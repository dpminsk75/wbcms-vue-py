<template>
  <!-- Общее таб-меню рабочих мест ( FBS-модель, plan 2026-10-23 §Шаг 4).
       Активная вкладка: prop `active` (id), иначе сравнивается с текущим route.path. -->
  <ul class="nav nav-pills wb-workspace-tabs">
    <li v-for="t in tabs" :key="t.id" class="nav-item wb-workspace-tabs__item">
      <router-link
        v-if="t.to && !t.disabled"
        class="nav-link wb-workspace-tabs__tab"
        :class="{ 'wb-workspace-tabs__tab--active': t.id === current }"
        :to="t.to"
        :title="t.title || t.label"
      >
        <i v-if="t.icon" class="bi" :class="t.icon"></i> {{ t.label }}
      </router-link>
      <span
        v-else
        class="nav-link disabled wb-workspace-tabs__tab wb-workspace-tabs__tab--off"
        :title="t.title || 'Скоро'"
      >
        <i v-if="t.icon" class="bi" :class="t.icon"></i> {{ t.label }}
      </span>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { WorkspaceTab } from './workspaceTabs'

const props = withDefaults(
  defineProps<{ tabs: WorkspaceTab[]; active?: string }>(),
  { active: '' },
)

const route = useRoute()

const current = computed(() => {
  if (props.active) return props.active
  const hit = props.tabs.find((t) => t.to && t.to === route.path)
  return hit ? hit.id : ''
})
</script>

<style scoped>
/* Форма как page-fbs__tabs (FbsTabs.vue), но переиспользуемая на всех рабочих местах. */
.wb-workspace-tabs {
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0;
}
.wb-workspace-tabs__tab {
  font-size: 12px;
}
.wb-workspace-tabs__tab--active {
  font-weight: 600;
}
.wb-workspace-tabs__tab--off {
  color: #9ca3af;
}
</style>