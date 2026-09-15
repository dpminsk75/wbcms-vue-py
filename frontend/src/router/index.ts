import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../pages/Dashboard.vue'

function feedRedirect(to: any) {
  const q: Record<string, string> = {}
  const src: Record<string, any> = to.query || {}
  const pick = (...keys: string[]) => {
    for (const k of keys) if (src[k]) return String(src[k])
    return undefined
  }
  const df = pick('date_from', 'DPFilterForm[date_from]', 'DPFilterForm%5Bdate_from%5D')
  const dt = pick('date_to', 'DPFilterForm[date_to]', 'DPFilterForm%5Bdate_to%5D')
  const nm = pick('nm_id', 'DPFilterForm[nm_id]', 'nmID')
  if (df) q.date_from = df
  if (dt) q.date_to = dt
  if (nm) q.nm_id = nm
  // пробрасываем остальные если уже в новом формате
  if (src.status) q.status = String(src.status)
  if (src.warehouse_name) q.warehouse_name = String(src.warehouse_name)
  if (src.region_name) q.region_name = String(src.region_name)
  if (src.page) q.page = String(src.page)
  return { path: '/feed', query: q }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../pages/Login.vue'), meta: { title: 'Вход — wbcms', public: true } },
    { path: '/register', name: 'register', component: () => import('../pages/RegisterPage.vue'), meta: { title: 'Регистрация — wbcms', public: true } },
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: 'Управление товарами и карточками — wbcms' } },
    { path: '/companies', name: 'companies', component: () => import('../pages/CompaniesPage.vue'), meta: { title: 'Компании — wbcms' } },
    { path: '/companies/:id', name: 'company-detail', component: () => import('../pages/CompanyDetailPage.vue'), meta: { title: 'Компания — wbcms' } },
    { path: '/admin/users', name: 'admin-users', component: () => import('../pages/AdminUsersPage.vue'), meta: { title: 'Пользователи — wbcms', needAdmin: true } },
    { path: '/admin/invites', name: 'admin-invites', component: () => import('../pages/AdminInvitesPage.vue'), meta: { title: 'Инвайты — wbcms', needAdmin: true } },
    { path: '/admin/companies', name: 'admin-companies', component: () => import('../pages/AdminCompaniesPage.vue'), meta: { title: 'Компании (админ) — wbcms', needAdmin: true } },
    { path: '/site/new-cards', name: 'new-cards', component: () => import('../pages/NewCardsPage.vue'), meta: { title: 'Новые карточки — wbcms' } },
    { path: '/wb-sales-analysis', name: 'sales-analysis', component: () => import('../pages/SalesAnalysisPage.vue'), alias: '/wb-sales-analysis/', meta: { title: 'ТОП Продаж WB — wbcms' } },
    { path: '/wb-get-sales-funnel/wbcard', name: 'sales-funnel-wb-card', component: () => import('../pages/SalesFunnelWbCard.vue'), alias: '/wb-get-sales-funnel/wbcard/', meta: { title: 'Воронка продаж: Карточка WB — wbcms' } },
    { path: '/feed', name: 'feed', component: () => import('../pages/OrdersFeed.vue'), meta: { title: 'Лента заказов — wbcms' } },
    { path: '/unclaimed-orders', name: 'unclaimed-orders', component: () => import('../pages/UnclaimedOrdersPage.vue'), alias: '/unclaimed-orders/', meta: { title: 'Невыкупленные товары (Unclaimed)' } },
    { path: '/wb-order/feed', redirect: feedRedirect },
    { path: '/wb-order/feed/', redirect: feedRedirect },
    { path: '/wb-order/feed-aggregated', name: 'feed-aggregated', component: () => import('../pages/OrdersFeedAggregated.vue'), meta: { title: 'Сводка по товарам (заказы) — wbcms' } },
    { path: '/wb-order/heatmap', name: 'heatmap', component: () => import('../pages/OrdersHeatmap.vue'), meta: { title: 'Тепловая карта заказов 7×24 — wbcms' } },
    { path: '/wb-adv-report', name: 'adv-report', component: () => import('../pages/AdvReportPage.vue'), alias: ['/wb-adv-report/'], meta: { title: 'Аналитика рекламы WB — wbcms' } },
    { path: '/wb/detail', name: 'wb-detail', component: () => import('../pages/WbDetailPage.vue'), alias: ['/wb/detail/'], meta: { title: 'Карточка: Выберите артикул — wbcms' } },
    { path: '/wb/detail/:nm_id', redirect: (to:any)=> ({ path:'/wb/detail', query:{ nm_id: to.params.nm_id, ...to.query }}) },
    { path: '/admin/quick-buttons', name: 'admin-quick-buttons', component: () => import('../pages/AdminQuickButtons.vue'), meta: { title: 'Быстрые кнопки — wbcms', needAdmin: true } },
    { path: '/admin/menu', name: 'admin-menu', component: () => import('../pages/AdminMenu.vue'), meta: { title: 'Меню — wbcms', needAdmin: true } },
  ]
})

// Вариант 1: единый title из yii2 ($this->title) → route.meta.title
router.afterEach((to) => {
  const t = to.meta?.title as string | undefined
  if (t) document.title = t
})

router.beforeEach(async (to) => {
  if ((to.meta as any)?.public) return true
  const { useAuthStore } = await import('../stores/auth')
  const auth = useAuthStore()
  if (!auth.isAuth) {
    const ok = await auth.loadMe()
    if (!ok) return { path: '/login', query: { back: to.fullPath } }
  }
  if ((to.meta as any)?.needAdmin && !auth.isAdmin) {
    // /admin/* пускает и админов компаний (скоуп своих — уже на бэке); членства подгружаем лениво
    if (auth.token && !auth.memberships.length) {
      try { await auth.loadMemberships() } catch { /* noop */ }
    }
    if (!auth.managesAny) return { path: '/' }
  }
  return true
})

export default router
