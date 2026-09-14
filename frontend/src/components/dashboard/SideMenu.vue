<template>
  <div class="list-group side-menu-list" style="font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; font-size:13px">
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

const fallback = [
  { label:'Отчеты', icon:'reports', iconClass:'bi bi-bar-chart', items:[ {label:'ТОП продаж'},{label:'Карточка WB'},{label:'Заказы'},{label:'Тепловая карта'},{label:'', divider:true},{label:'Реклама'},{label:'По ГЕО'},{label:'Возвраты'},{label:'Воронка продаж'},{label:'', divider:true},{label:'ТОП товары'},{label:'Маржа'},{label:'', divider:true},{label:'Товары по складам'},{label:'Критичные остатки'},{label:'Оборачиваемость'},{label:'Детализация'} ] },
  { label:'По фразам', icon:'by_search', iconClass:'bi bi-search', items:[ {label:'Карточка -> фразы'},{label:'Фраза -> карточки'},{label:'Анализ фраз'},{label:'', divider:true},{label:'SEO рекомендации'},{label:'SEO просмотренные'},{label:'', divider:true},{label:'Конкуренты (анализ)'} ] },
  { label:'По тегам', icon:'tag', iconClass:'bi bi-tag', items:[ {label:'Заказы'},{label:'', divider:true},{label:'Список тегов', url:'/tag/index'} ] },
  { label:'По товарам', icon:'product', iconClass:'bi bi-box', items:[ {label:'Детализация', url:'/wb-detail-by-period/weekly-report'} ] },
  { label:'Отзывы', icon:'chat', iconClass:'bi bi-chat', items:[ {label:'Отзывы и ответы'},{label:'', divider:true},{label:'Правила'},{label:'Тэги'} ] },
  { label:'Данные', icon:'data', iconClass:'bi bi-pie-chart', items:[ {label:'Лента заказов'},{label:'', divider:true},{label:'Заказы'},{label:'Продажи'},{label:'', divider:true},{label:'Себестоимость'} ] },
  { label:'Склад', icon:'warehouse', iconClass:'bi bi-box-seam', items:[ {label:'Управление остатками'},{label:'Документы'},{label:'', divider:true},{label:'Наличие'},{label:'Оборотная ведомость'},{label:'Карточка товара'},{label:'Неликвиды'} ] },
  { label:'Справочники', icon:'book', iconClass:'bi bi-book', items:[ {label:'Карточки WB'},{label:'Склады'},{label:'Виртуальные склады'},{label:'', divider:true},{label:'Теги'},{label:'Товары'},{label:'Составные товары'} ] },
  { label:'Админка', icon:'gear', iconClass:'bi bi-gear', items:[ {label:'Пользователи'},{label:'Роли'},{label:'Компании'},{label:'', divider:true},{label:'Настройки профиля'} ] },
]

const { data: raw, isError } = useQuery({ queryKey:['menu','side'], queryFn: ()=> (dashboardApi as any).menu('side'), initialData: fallback as any })
const menu = computed(() => isError.value ? fallback : (Array.isArray(raw.value) ? raw.value : fallback))

const sectionIconClass = (section:any): string => {
  const value = section?.iconClass || section?.icon || ''
  if(!value) return 'bi bi-journal-text'
  if(/^(bi(?:\s|$)|(?:fas|fa)\s)/.test(value)) return value
  return iconClassMap[value] || value
}
</script>
