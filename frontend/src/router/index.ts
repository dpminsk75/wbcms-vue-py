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
    { path: '/wb-profit/top-products', name: 'top-products', component: () => import('../pages/TopProductsPage.vue'), meta: { title: 'ТОП товаров за период — wbcms' } },
    { path: '/wb/detail', name: 'wb-detail', component: () => import('../pages/WbDetailPage.vue'), alias: ['/wb/detail/'], meta: { title: 'Карточка: Выберите артикул — wbcms' } },
    { path: '/wb/detail/:nm_id', redirect: (to:any)=> ({ path:'/wb/detail', query:{ nm_id: to.params.nm_id, ...to.query }}) },
    { path: '/admin/quick-buttons', name: 'admin-quick-buttons', component: () => import('../pages/AdminQuickButtons.vue'), meta: { title: 'Быстрые кнопки — wbcms', needAdmin: true } },
    { path: '/admin/menu', name: 'admin-menu', component: () => import('../pages/AdminMenu.vue'), meta: { title: 'Меню — wbcms', needAdmin: true } },
    { path: '/admin/seo-models', name: 'admin-seo-models', component: () => import('../pages/AdminSeoModelsPage.vue'), meta: { title: 'SEO-модели — wbcms', needAdmin: true } },
    { path: '/tags', name: 'tags', component: () => import('../pages/TagsPage.vue'), alias: ['/tags/', '/tag', '/tag/', '/tag/index', '/tag/index/'], meta: { title: 'Теги' } },
    { path: '/tags/create', name: 'tag-create', component: () => import('../pages/TagFormPage.vue'), alias: ['/tags/create/', '/tag/create', '/tag/create/'], meta: { title: 'Новый тег' } },
    { path: '/tags/:id/edit', name: 'tag-edit', component: () => import('../pages/TagFormPage.vue'), meta: { title: 'Редактирование тега' } },
    { path: '/tags/:id', name: 'tag-view', component: () => import('../pages/TagViewPage.vue'), meta: { title: 'Теги: Заказы по тегу' } },
    { path: '/tag/orders', name: 'tag-orders', component: () => import('../pages/TagViewPage.vue'), meta: { title: 'Теги: Заказы по тегу' } },
    { path: '/tag/margin', name: 'tag-margin', component: () => import('../pages/TagMarginPage.vue'), meta: { title: 'Маржа по тегам — wbcms' } },
    { path: '/wb-search/card', name: 'wb-search-card', component: () => import('../pages/WbSearchCardPage.vue'), alias: ['/wb-search/card/'], meta: { title: 'Анализ поисковых фраз для карточки' } },
    { path: '/wb-search/phrase', name: 'wb-search-phrase', component: () => import('../pages/WbSearchPhrasePage.vue'), alias: ['/wb-search/phrase/'], meta: { title: 'Анализ фразы' } },
    { path: '/wb-search/trend', name: 'wb-search-trend', component: () => import('../pages/WbSearchTrendPage.vue'), alias: ['/wb-search/trend/'], meta: { title: 'Анализ фразы' } },
    { path: '/cost-import', name: 'cost-import', component: () => import('../pages/CostImportPage.vue'), alias: ['/cost-import/'], meta: { title: 'Загрузка себестоимости' } },
    { path: '/cost-import/list', name: 'cost-list', component: () => import('../pages/CostListPage.vue'), alias: ['/cost-import/list/'], meta: { title: 'Себестоимость: просмотр и редактирование' } },
    { path: '/cost-import/missing', name: 'cost-missing', component: () => import('../pages/CostMissingPage.vue'), alias: ['/cost-import/missing/'], meta: { title: 'Нет себестоимости — wbcms' } },
    { path: '/wb-order/index', name: 'wb-orders', component: () => import('../pages/WbOrdersPage.vue'), alias: ['/wb-order/index/'], meta: { title: 'Список заказов' } },
    { path: '/wb-sales/index', name: 'wb-sales', component: () => import('../pages/WbSalesPage.vue'), alias: ['/wb-sales/index/'], meta: { title: 'Список продаж' } },
    { path: '/wb-feedback-answers', name: 'feedback-answers', component: () => import('../pages/FeedbackAnswersPage.vue'), alias: ['/wb-feedback-answers/', '/wb-feedback-answers/index', '/wb-feedback-answers/index/'], meta: { title: 'Отзывы и ответы' } },
    { path: '/wb-feedback-tags', name: 'feedback-tags', component: () => import('../pages/FeedbackTagsPage.vue'), alias: ['/wb-feedback-tags/', '/wb-feedback-tags/index', '/wb-feedback-tags/index/'], meta: { title: 'Разметка тегов отзывов' } },
    { path: '/wb-reply-rules', name: 'reply-rules', component: () => import('../pages/ReplyRulesPage.vue'), alias: ['/wb-reply-rules/', '/wb-reply-rules/index', '/wb-reply-rules/index/'], meta: { title: 'Автоответы на отзывы' } },
    { path: '/wb-reply-rules/test-generation', name: 'reply-test', component: () => import('../pages/ReplyTestPage.vue'), alias: ['/wb-reply-rules/test-generation/'], meta: { title: 'Тестирование генерации автоответов' } },
    { path: '/wb-reply-rules/stop-words', name: 'stop-words', component: () => import('../pages/StopWordsPage.vue'), alias: ['/wb-reply-rules/stop-words/'], meta: { title: 'Стоп-слова' } },
    { path: '/wb-reply-rules/create', name: 'reply-rule-create', component: () => import('../pages/ReplyRuleFormPage.vue'), alias: ['/wb-reply-rules/create/'], meta: { title: 'Создание правила автоответа' } },
    { path: '/wb-reply-rules/:id/edit', name: 'reply-rule-edit', component: () => import('../pages/ReplyRuleFormPage.vue'), meta: { title: 'Редактирование правила' } },
    { path: '/competitor/index', name: 'competitor-index', component: () => import('../pages/CompetitorIndexPage.vue'), alias: ['/competitor/', '/competitor'], meta: { title: 'Конкуренты — анализ — wbcms' } },
    { path: '/competitor/select/:nm', name: 'competitor-select', component: () => import('../pages/CompetitorSelectPage.vue'), meta: { title: 'Конкуренты: выбор фраз — wbcms' } },
    { path: '/competitor/selected/:nm', name: 'competitor-selected', component: () => import('../pages/CompetitorSelectedPage.vue'), meta: { title: 'Конкуренты: отбор — wbcms' } },
    { path: '/competitor/results/:nm', name: 'competitor-results', component: () => import('../pages/CompetitorResultsPage.vue'), meta: { title: 'Результаты анализа конкурентов — wbcms' } },
    { path: '/seo/index', name: 'seo-index', component: () => import('../pages/SeoIndexPage.vue'), alias: ['/seo/', '/seo'], meta: { title: 'SEO рекомендации — wbcms' } },
    { path: '/seo/view/:id', name: 'seo-view', component: () => import('../pages/SeoViewPage.vue'), meta: { title: 'SEO рекомендация — wbcms' } },
    { path: '/ext/diag', name: 'ext-diag', component: () => import('../pages/ExtDiagPage.vue'), meta: { title: 'Диагностика расширения — wbcms' } },
    { path: '/ext/install', name: 'ext-install', component: () => import('../pages/ExtInstallPage.vue'), meta: { title: 'Установка расширения — wbcms' } },
    { path: '/tag/update', redirect: (to: any) => (to.query?.id ? { path: `/tags/${to.query.id}/edit` } : { path: '/tags' }) },
    { path: '/tag/view', redirect: (to: any) => {
      const q: Record<string, string> = {}
      const dr = (to.query?.date_range ?? '') as string
      if (dr.includes(' - ')) {
        const [a, b] = dr.split(' - ')
        q.date_from = a.trim()
        q.date_to = b.trim()
      } else {
        if (to.query?.date_from) q.date_from = String(to.query.date_from)
        if (to.query?.date_to) q.date_to = String(to.query.date_to)
      }
      if (to.query?.id) q.id = String(to.query.id)
      return { path: '/tag/orders', query: q }
    } },
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
