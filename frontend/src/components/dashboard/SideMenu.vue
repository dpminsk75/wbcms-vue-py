<template>
  <div class="list-group side-menu-list" style="font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; font-size:13px">
    <template v-if="menu.length">
      <div v-for="section in menu" :key="section.label" style="margin-bottom:12px">
        <div style="font-weight:700; color:#1D1B2A; padding:6px 8px; display:flex; align-items:center; gap:6px">
          <span class="wb-icon"><i :class="sectionIconClass(section)"></i></span>
          {{ section.label }}
        </div>
        <template v-for="(it, idx) in section.items" :key="(it?.label || 'div') + idx">
          <div v-if="it?.divider" style="width:70px; margin:5px 0; border-top:1px solid #e0e0e0"></div>
          <a v-else-if="it?.label" :href="it.url || '#'" style="display:block; padding:4px 8px 4px 28px; color:#4A3A8C; text-decoration:none; font-size:12px">{{ it.label }}</a>
        </template>
      </div>
    </template>
    <div v-else style="padding:8px; font-size:12px; color:#6E6A80">
      {{ isError ? 'Меню недоступно — обновите страницу' : 'Загрузка меню…' }}
    </div>
    <div style="padding:8px; font-size:12px; color:#6E6A80">Выйти (demo)</div>
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
