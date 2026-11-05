<template>
  <!-- Боковое меню рабочих мест. Размеры и цвета — из темы (.side-menu-*, theme/nav.css):
       инлайнов нет, поэтому кегль едет вместе с настройкой размера шрифта. -->
  <div class="list-group side-menu-list">
    <template v-if="menu.length">
      <div v-for="section in menu" :key="section.label" class="side-menu__sec">
        <div class="side-menu__head">
          <span class="wb-icon"><i :class="sectionIconClass(section)"></i></span>
          {{ section.label }}
        </div>
        <template v-for="(it, idx) in section.items" :key="(it?.label || 'div') + idx">
          <div v-if="it?.divider" class="side-menu__div"></div>
          <a v-else-if="it?.label" class="side-menu__item" :href="it.url || '#'">{{ it.label }}</a>
        </template>
      </div>
    </template>
    <div v-else class="side-menu__note">
      {{ isError ? 'Меню недоступно — обновите страницу' : 'Загрузка меню…' }}
    </div>
    <div class="side-menu__note">Выйти (demo)</div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'

const iconClassMap: Record<string,string> = {
  reports: 'bi bi-bar-chart',
  by_search: 'bi bi-search',
  tag: 'bi bi-tag',
  product: 'bi bi-box',
  chat: 'bi bi-chat',
  data: 'bi bi-pie-chart',
  warehouse: 'bi bi-box-seam',
  book: 'bi bi-book',
  gear: 'bi bi-gear'
}

// Меню берётся только из /api/menu (backend/config/menu.json) — захардкоженной
// копии нет намеренно: устаревшая копия показывала старые пункты меню.
const { data: raw, isError } = useQuery({
  queryKey:['menu','side'],
  queryFn: ()=> dashboardApi.menu('side'),
  retry: 2,
})
const menu = computed<any[]>(() => Array.isArray(raw.value) ? raw.value : [])

const sectionIconClass = (section:any): string => {
  const value = section?.iconClass || section?.icon || ''
  if(!value) return 'bi bi-journal-text'
  if(/^(bi(?:\s|$)|(?:fas|fa)\s)/.test(value)) return value
  return iconClassMap[value] || value
}
</script>
