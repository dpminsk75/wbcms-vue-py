<template>
  <!-- Меню рабочих мест — пилюли темы (.mn), по умолчанию справа в углу.
       Активная вкладка: prop `active` (id), иначе сравнивается с текущим route.path. -->
  <nav class="wb-workspace-tabs wsp__menu">
    <template v-for="t in tabs" :key="t.id">
      <router-link
        v-if="t.to && !t.disabled"
        class="mn"
        :class="{ 'mn--on': t.id === current }"
        :to="t.to"
        :title="t.title || t.label"
      >
        <i v-if="t.icon" class="bi" :class="t.icon"></i> {{ t.label }}
      </router-link>
      <span
        v-else
        class="mn mn--off"
        :title="t.title || 'Скоро'"
      >
        <i v-if="t.icon" class="bi" :class="t.icon"></i> {{ t.label }}
      </span>
    </template>
  </nav>
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
/* Оформление меню — класс темы (.mn): размер, цвет, скругления, переносы.
   Своих правил раскладки здесь нет — блок .wsp__menu в theme/nav.css:
   меню прижато вправо, переносы — внутри блока, под заголовок не падает. */
</style>
