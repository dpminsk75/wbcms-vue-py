<template>
  <header id="header">
    <!-- мобильная панель -->
    <div class="mobile-topbar d-md-none" style="background: linear-gradient(97.26deg,#ed3cca .49%,#df34d2 14.88%,#d02bd9 29.27%,#bf22e1 43.14%,#ae1ae8 57.02%,#9a10f0 70.89%,#8306f7 84.76%,#7c1af8 99.15%); padding:8px 12px; display:flex; align-items:center; gap:8px">
      <button type="button" class="mobile-menu-toggle" @click="mobileOpen=!mobileOpen" style="background:transparent; border:none; display:flex; flex-direction:column; gap:4px">
        <span style="display:block; width:20px; height:2px; background:#fff"></span><span style="display:block; width:20px; height:2px; background:#fff"></span><span style="display:block; width:20px; height:2px; background:#fff"></span>
      </button>
      <span class="mobile-topbar-brand" style="color:#fff; font-weight:700">Аналитика WB</span>
    </div>
    <div v-if="mobileOpen" class="mobile-menu-overlay d-md-none" @click="mobileOpen=false" style="position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:1040"></div>
    <div class="mobile-nav-drawer d-md-none" :style="{display: mobileOpen ? 'block' : 'none', position:'fixed', top:0, left:0, width:'260px', height:'100vh', background:'#fff', zIndex:1050, overflowY:'auto', padding:'16px'}" @click="mobileOpen=false">
      <div style="margin-bottom:12px">
        <div style="font-weight:700; padding:6px 0">{{ companyLabel }}</div>
        <a href="#" @click.prevent="pickCompany('all')" style="display:block; padding:4px 0; font-size:13px; color:#4A3A8C; text-decoration:none">Все компании</a>
        <a v-for="c in auth.companies" :key="c.id" href="#" @click.prevent="pickCompany(c.id)" style="display:block; padding:4px 0; font-size:13px; color:#4A3A8C; text-decoration:none">{{ c.name }}</a>
        <a href="#" @click.prevent="doLogout" style="display:block; padding:8px 0; font-size:13px; color:#c00; text-decoration:none">Выйти ({{ auth.user?.username || '...' }})</a>
      </div>
      <div v-for="s in menu" :key="s.label" style="margin-bottom:12px">
        <div style="font-weight:700; padding:6px 0">{{ s.label }}</div>
        <template v-for="(it, idx) in s.items" :key="(it?.label || 'div') + idx">
          <a v-if="it?.label && !it.divider" href="#" @click.prevent style="display:block; padding:4px 0; font-size:13px; color:#4A3A8C; text-decoration:none">{{ it.label }}</a>
        </template>
      </div>
    </div>

    <!-- десктоп -->
    <div class="d-none d-md-block">
      <nav class="navbar navbar-expand-md bg-wb w-100" style="padding:10px 12px">
        <a class="navbar-brand d-flex align-items-center" href="/" style="color:#fff; font-weight:700; font-size:26px">
          <span style="height:50px; margin-right:10px; display:flex; align-items:center; font-size:32px">◈</span> Аналитика WB
        </a>
        <ul class="navbar-nav wb-menu__list w-100" style="flex-wrap:nowrap">
          <li v-for="section in menu" :key="section.label" class="nav-item wb-menu__item dropdown">
            <a class="nav-link dropdown-toggle" href="#" @click.prevent>
              <span class="wb-icon"><i :class="sectionIconClass(section)"></i></span>
              <span class="wb-text">{{ section.label }}</span>
            </a>
            <ul class="dropdown-menu">
              <template v-for="(it, idx) in section.items" :key="(it?.label || 'div') + idx">
                <li v-if="it?.divider" class="dropdown-divider"></li>
                <li v-else-if="it?.label">
                  <router-link v-if="isSpa(it.url)" class="dropdown-item" :to="toSpa(it.url)!">{{ it.label }}</router-link>
                  <a v-else class="dropdown-item" :href="it.url || '#'">{{ it.label }}</a>
                </li>
              </template>
            </ul>
          </li>
          <!-- компания + выход — flex справа, без absolute (фикс наслоения) -->
          <li class="nav-item wb-menu__item dropdown ms-auto">
            <a class="nav-link dropdown-toggle" href="#" @click.prevent>
              <span class="wb-icon"><i class="bi bi-building"></i></span>
              <span class="wb-text">{{ companyLabel }}</span>
            </a>
            <ul class="dropdown-menu">
              <li>
                <a class="dropdown-item" :class="{ active: auth.companyId === 'all' }" href="#" @click.prevent="pickCompany('all')">Все компании</a>
              </li>
              <li class="dropdown-divider"></li>
              <li v-for="c in auth.companies" :key="c.id">
                <a class="dropdown-item" :class="{ active: auth.companyId === c.id }" href="#" @click.prevent="pickCompany(c.id)">{{ c.name }}</a>
              </li>
            </ul>
          </li>
          <li class="nav-item ms-2" style="position:static !important; right:auto !important">
            <button class="wb-logout-btn" @click="doLogout">
              <i class="bi bi-box-arrow-right wb-icon"></i>
              <span class="wb-text">Выйти ({{ auth.user?.username || '...' }})</span>
            </button>
          </li>
        </ul>
      </nav>
    </div>
  </header>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { dashboardApi } from '../../api/dashboard'
import { useAuthStore } from '../../stores/auth'

const mobileOpen = ref(false)
const router = useRouter()
const auth = useAuthStore()
const qc = useQueryClient()

onMounted(() => {
  if (!auth.user) auth.loadMe().then((ok) => { if (ok) auth.loadCompanies() })
  else if (!auth.companies.length) auth.loadCompanies()
})

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

const fallbackMenu = [
  { label:'Отчеты', icon:'reports', iconClass:'bi bi-bar-chart', items:[ {label:'ТОП продаж', url:'/wb-sales-analysis/'},{label:'Карточка WB', url:'/wb/detail/'},{label:'Заказы', url:'/wb-order/feed-aggregated'},{label:'Тепловая карта', url:'#'},{label:'', divider:true},{label:'Реклама', url:'/wb-adv-report/'},{label:'По ГЕО', url:'#'},{label:'Возвраты', url:'#'},{label:'Воронка продаж', url:'#'},{label:'', divider:true},{label:'ТОП товары', url:'/wb-profit/top-products'},{label:'Маржа', url:'/wb-profit'},{label:'', divider:true},{label:'Товары по складам', url:'/wb-stock/top-warehouse-report'},{label:'Критичные остатки', url:'/wb-stock/warehouse-analytics'},{label:'Оборачиваемость', url:'/wb-stock/analytics'},{label:'Детализация', url:'/wb-detail-by-period/weekly-report-nmid'} ] },
  { label:'По фразам', icon:'by_search', iconClass:'bi bi-search', items:[ {label:'Карточка -> фразы', url:'/wb-search/card'},{label:'Фраза -> карточки', url:'/wb-search/phrase'},{label:'Анализ фраз', url:'/wb-search/trend'},{label:'', divider:true},{label:'SEO рекомендации', url:'/seo/index'},{label:'SEO просмотренные', url:'/seo/index'},{label:'', divider:true},{label:'Конкуренты (анализ)', url:'/competitor/index'} ] },
  { label:'По тегам', icon:'tag', iconClass:'bi bi-tag', items:[ {label:'Заказы', url:'/tag/view'},{label:'', divider:true},{label:'Список тегов', url:'/tag/index'} ] },
  { label:'По товарам', icon:'product', iconClass:'bi bi-box', items:[ {label:'Детализация', url:'/wb-detail-by-period/weekly-report'} ] },
  { label:'Отзывы', icon:'chat', iconClass:'bi bi-chat', items:[ {label:'Отзывы и ответы', url:'/wb-feedback-answers/index'},{label:'', divider:true},{label:'Правила', url:'/wb-reply-rules/index'},{label:'Тэги', url:'/wb-feedback-tags/index'} ] },
  { label:'Данные', icon:'data', iconClass:'bi bi-pie-chart', items:[ {label:'Лента заказов', url:'/wb-order/feed'},{label:'', divider:true},{label:'Заказы', url:'/wb-order/index'},{label:'Продажи', url:'/wb-sales/index'},{label:'', divider:true},{label:'Себестоимость', url:'/cost-import/list'} ] },
  { label:'Склад', icon:'warehouse', iconClass:'bi bi-box-seam', items:[ {label:'Управление остатками', url:'/wb-fbs-virtual/index'},{label:'Документы', url:'/wb-doc/index'},{label:'', divider:true},{label:'Наличие', url:'/wb-doc-report/balance'},{label:'Оборотная ведомость', url:'/wb-doc-report/turnover'},{label:'Карточка товара', url:'/wb-doc-report/card'},{label:'Неликвиды', url:'/wb-doc-report/nonliquid'} ] },
  { label:'Справочники', icon:'book', iconClass:'bi bi-book', items:[ {label:'Карточки WB', url:'/wb/cards'},{label:'Склады', url:'/our-warehouse/index'},{label:'Виртуальные склады', url:'/wb-fbs-virtual/warehouse-list'},{label:'', divider:true},{label:'Теги', url:'/tag/index'},{label:'Товары', url:'/product/index'},{label:'Составные товары', url:'/product-wb-card/index'} ] },
  { label:'Админка', icon:'gear', iconClass:'bi bi-gear', items:[ {label:'Пользователи', url:'/user/admin/index'},{label:'Роли', url:'/admin/assignment'},{label:'Компании', url:'/company/index'},{label:'', divider:true},{label:'Быстрые кнопки', url:'/admin/quick-buttons'},{label:'Меню', url:'/admin/menu'},{label:'Настройки профиля', url:'/user/profile'} ] },
]

const { data: menuRaw, isError } = useQuery({ queryKey: ['menu','top', computed(() => auth.user?.username || 'guest')], queryFn: ()=> (dashboardApi as any).menu('top'), initialData: fallbackMenu as any })
const menu = computed(() => isError.value ? fallbackMenu : (Array.isArray(menuRaw.value) ? menuRaw.value : fallbackMenu))

const companyLabel = computed(() => {
  if (auth.companyId === 'all') return 'Все компании'
  return auth.companies.find((c) => c.id === auth.companyId)?.name || 'Кабинет'
})

function pickCompany(v: number | 'all') {
  auth.setCompany(v)
  qc.invalidateQueries({ queryKey: ['menu'] })
}
function doLogout() {
  auth.logout()
  router.push('/login')
}

const sectionIconClass = (section:any): string => {
  const value = section?.iconClass || section?.icon || ''
  if(!value) return 'bi bi-journal-text'
  if(/^(bi(?:\s|$)|(?:fas|fa)\s)/.test(value)) return value
  return iconClassMap[value] || value
}

const spaMap: Record<string,string> = { '/wb-order/feed': '/feed', '/wb-sales-analysis': '/wb-sales-analysis', '/wb-sales-analysis/': '/wb-sales-analysis', '/wb/detail': '/wb/detail', '/wb/detail/': '/wb/detail', '/admin/quick-buttons': '/admin/quick-buttons', '/admin/menu': '/admin/menu' }
const toSpa = (url?: string): string | null => {
  if (!url || url==='#') return null
  if (spaMap[url]) return spaMap[url]
  const base = url.split('?')[0].replace(/\/$/, '')
  if (spaMap[base]) return spaMap[base]
  if (spaMap[base+'/']) return spaMap[base+'/']
  return null
}
const isSpa = (url?: string) => !!toSpa(url)
</script>
