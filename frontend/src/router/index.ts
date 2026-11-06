import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../pages/Dashboard.vue'
import { docTitle } from '../utils/pageTitle'

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
    { path: '/login', name: 'login', component: () => import('../pages/Login.vue'), meta: { title: 'Вход', public: true } },
    { path: '/reset-password', name: 'reset-password', component: () => import('../pages/ResetPasswordPage.vue'), meta: { title: 'Смена пароля', public: true } },
    { path: '/register', name: 'register', component: () => import('../pages/RegisterPage.vue'), meta: { title: 'Регистрация', public: true } },
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: 'Управление товарами и карточками', h1: 'Дашборд' } },
    { path: '/settings/password', name: 'settings-password', component: () => import('../pages/ChangePasswordPage.vue'), meta: { title: 'Сменить пароль' } },
    { path: '/settings/appearance', name: 'settings-appearance', component: () => import('../pages/SettingsAppearancePage.vue'), meta: { title: 'Настройки стилей' } },
    { path: '/companies', name: 'companies', component: () => import('../pages/CompaniesPage.vue'), meta: { title: 'Компании' } },
    { path: '/companies/:id', name: 'company-detail', component: () => import('../pages/CompanyDetailPage.vue'), meta: { title: 'Компания' } },
    { path: '/admin/users', name: 'admin-users', component: () => import('../pages/AdminUsersPage.vue'), meta: { title: 'Пользователи', needAdmin: true } },
    { path: '/admin/invites', name: 'admin-invites', component: () => import('../pages/AdminInvitesPage.vue'), meta: { title: 'Инвайты', needAdmin: true } },
    { path: '/admin/companies', name: 'admin-companies', component: () => import('../pages/AdminCompaniesPage.vue'), meta: { title: 'Компании (админ)', needAdmin: true } },
    { path: '/site/new-cards', name: 'new-cards', component: () => import('../pages/NewCardsPage.vue'), meta: { title: 'Новые карточки' } },
    { path: '/wb-sales-analysis', name: 'sales-analysis', component: () => import('../pages/SalesAnalysisPage.vue'), alias: '/wb-sales-analysis/', meta: { title: 'ТОП Продаж WB' } },
    { path: '/wb-get-sales-funnel/wbcard', name: 'sales-funnel-wb-card', component: () => import('../pages/SalesFunnelWbCard.vue'), alias: '/wb-get-sales-funnel/wbcard/', meta: { title: 'Воронка продаж: Карточка WB' } },
    { path: '/news', name: 'news', component: () => import('../pages/NewsListPage.vue'), meta: { title: 'Новости WB' } },
    { path: '/feed', name: 'feed', component: () => import('../pages/OrdersFeed.vue'), meta: { title: 'Лента заказов' } },
    { path: '/unclaimed-orders', name: 'unclaimed-orders', component: () => import('../pages/UnclaimedOrdersPage.vue'), alias: '/unclaimed-orders/', meta: { title: 'Возвраты' } },
    { path: '/wb-order/feed', redirect: feedRedirect },
    { path: '/wb-order/feed/', redirect: feedRedirect },
    { path: '/wb-order/feed-aggregated', name: 'feed-aggregated', component: () => import('../pages/OrdersFeedAggregated.vue'), meta: { title: 'Сводка по товарам (заказы)' } },
    { path: '/wb-order/heatmap', name: 'heatmap', component: () => import('../pages/OrdersHeatmap.vue'), meta: { title: 'Тепловая карта заказов 7×24' } },
    { path: '/wb-penalty/logistics', name: 'penalty-logistics', component: () => import('../pages/PenaltyLogisticsPage.vue'), meta: { title: 'Штрафы и потери на доставке' } },
    { path: '/wb-penalty/detail', name: 'penalty-detail', component: () => import('../pages/PenaltyDetailPage.vue'), meta: { title: 'Детализация потерь на доставке' } },
    { path: '/geo/sales-map', name: 'geo-sales-map', component: () => import('../pages/GeoSalesMapPage.vue'), meta: { title: 'Продажи на карте' } },
    { path: '/fbs-report', name: 'fbs-report', component: () => import('../pages/FbsReportPage.vue'), meta: { title: 'FBS — продажа со своего склада' } },
    { path: '/fbs-orders', name: 'fbs-orders', component: () => import('../pages/FbsOrdersPage.vue'), meta: { title: 'FBS Заказы' } },
    { path: '/fbs-cancels', name: 'fbs-cancels', component: () => import('../pages/FbsCancelsPage.vue'), meta: { title: 'FBS Отмены' } },
    { path: '/fbs-commission', name: 'fbs-commission', component: () => import('../pages/FbsCommissionPage.vue'), meta: { title: 'FBS Комиссия' } },
    { path: '/fbs-pvz', name: 'fbs-pvz', component: () => import('../pages/FbsPvzPage.vue'), meta: { title: 'FBS Путь до ПВЗ' } },
    { path: '/wb-adv-report', name: 'adv-report', component: () => import('../pages/AdvReportPage.vue'), alias: ['/wb-adv-report/'], meta: { title: 'Аналитика рекламы WB' } },
    { path: '/wb-promotions', name: 'wb-promotions', component: () => import('../pages/WbPromotionsPage.vue'), alias: ['/wb-promotions/'], meta: { title: 'Акции WB', needPerm: 'viewFinance' } },
    // Налоговые настройки — в меню «Админка → Налоги».
    { path: '/wb-tax-settings', name: 'wb-tax-settings', component: () => import('../pages/TaxSettingsPage.vue'), meta: { title: 'Налоги', needPerm: 'viewFinance' } },
    { path: '/wb-marketing-expenses', name: 'wb-marketing-expenses', component: () => import('../pages/MarketingExpensesPage.vue'), meta: { title: 'Внешняя реклама', needPerm: 'viewFinance' } },
    { path: '/wb-promotions/selection', name: 'wb-promotions-selection', component: () => import('../pages/WbPromotionsSelectionPage.vue'), meta: { title: 'Акции WB — подбор товаров', needPerm: 'viewFinance' } },
    { path: '/wb-profit/top-products', name: 'top-products', component: () => import('../pages/TopProductsPage.vue'), meta: { title: 'ТОП товаров за период' } },
    { path: '/wb-profit/products', name: 'profit-products', component: () => import('../pages/ProfitProductsPage.vue'), meta: { title: 'Маржа по продуктам' } },
    { path: '/wb-warehouses', name: 'warehouses', component: () => import('../pages/WarehousesPage.vue'), meta: { title: 'Склады' } },
    { path: '/wb-fbs-virtual', name: 'fbs-virtual', component: () => import('../pages/FbsVirtualPage.vue'), meta: { title: 'FBS остатки' } },
    { path: '/wb-stock-reports/:tab(balance|turnover|card|nonliquid)', name: 'stock-reports', component: () => import('../pages/StockReportsPage.vue'), meta: { title: 'Отчеты склада' } },
    { path: '/wb-stock', name: 'stock-wb', component: () => import('../pages/StockWbPage.vue'), meta: { title: 'Анализ остатков', needPerm: 'viewOrders' } },
    // Старые URL из Yii2 (три отдельных экрана) → одна страница с вкладками
    { path: '/wb-stock/analytics', redirect: { path: '/wb-stock', query: { tab: 'turnover' } } },
    { path: '/wb-stock/top-warehouse-report', redirect: { path: '/wb-stock', query: { tab: 'sklads' } } },
    { path: '/wb-stock/warehouse-analytics', redirect: { path: '/wb-stock', query: { tab: 'sklads' } } },
    { path: '/wb-production', name: 'production', component: () => import('../pages/ProductionReportPage.vue'), meta: { title: 'Производственный план' } },
    { path: '/wb-production/smolensk', name: 'production-smolensk', component: () => import('../pages/ProductionSmolenskPage.vue'), meta: { title: 'Смоленск — остатки и движения' } },
    { path: '/product-catalog', name: 'product-catalog', component: () => import('../pages/ProductCatalogPage.vue'), meta: { title: 'Линейки товаров' } },
    { path: '/wb/cards', name: 'wb-cards', component: () => import('../pages/WbCardsPage.vue'), alias: ['/wb/cards/', '/wb-cards'], meta: { title: 'Карточки WB' } },
    { path: '/wb-doc', name: 'stock-docs', component: () => import('../pages/StockDocListPage.vue'), meta: { title: 'Документы склада' } },    { path: '/wb-doc/create', name: 'stock-doc-create', component: () => import('../pages/StockDocFormPage.vue'), meta: { title: 'Новый документ' } },
    { path: '/wb-doc/:id/edit', name: 'stock-doc-edit', component: () => import('../pages/StockDocFormPage.vue'), meta: { title: 'Документ: правка' } },
    { path: '/wb-doc/:id', name: 'stock-doc-view', component: () => import('../pages/StockDocViewPage.vue'), meta: { title: 'Документ склада' } },
    { path: '/wb-profit', name: 'wb-profit', component: () => import('../pages/ProfitIndexPage.vue'), alias: ['/wb-profit/', '/wb-profit/index'], meta: { title: 'Маржинальный учёт' } },
    { path: '/wb/detail', name: 'wb-detail', component: () => import('../pages/WbDetailPage.vue'), alias: ['/wb/detail/'], meta: { title: 'Карточка: Выберите артикул' } },
    { path: '/wb/detail/:nm_id', redirect: (to:any)=> ({ path:'/wb/detail', query:{ nm_id: to.params.nm_id, ...to.query }}) },
    { path: '/admin/quick-buttons', name: 'admin-quick-buttons', component: () => import('../pages/AdminQuickButtons.vue'), meta: { title: 'Быстрые кнопки', needAdmin: true } },
    { path: '/admin/menu', name: 'admin-menu', component: () => import('../pages/AdminMenu.vue'), meta: { title: 'Меню', needAdmin: true } },
    { path: '/admin/roles', name: 'admin-roles', component: () => import('../pages/AdminRolesPage.vue'), meta: { title: 'Роли и права', needAdmin: true, needPerm: 'manageUsers' } },
    // legacy yii2-адрес: /admin/assignment переименовали в v3 (/admin/roles)
    { path: '/admin/assignment', redirect: '/admin/roles' },
    { path: '/admin/seo-models', name: 'admin-seo-models', component: () => import('../pages/AdminSeoModelsPage.vue'), meta: { title: 'SEO-модели', needAdmin: true } },
    { path: '/admin/fbs-tariffs', name: 'admin-fbs-tariffs', component: () => import('../pages/AdminFbsTariffsPage.vue'), meta: { title: 'Тарифы сборки FBS', needAdmin: true } },
    { path: '/admin/timers', name: 'admin-timers', component: () => import('../pages/AdminTimersPage.vue'), meta: { title: 'Таймеры', needAdmin: true } },
    { path: '/tags', name: 'tags', component: () => import('../pages/TagsPage.vue'), alias: ['/tags/', '/tag', '/tag/', '/tag/index', '/tag/index/'], meta: { title: 'Теги' } },
    { path: '/tags/create', name: 'tag-create', component: () => import('../pages/TagFormPage.vue'), alias: ['/tags/create/', '/tag/create', '/tag/create/'], meta: { title: 'Новый тег' } },
    { path: '/tags/:id/edit', name: 'tag-edit', component: () => import('../pages/TagFormPage.vue'), meta: { title: 'Редактирование тега' } },
    { path: '/tags/:id', name: 'tag-view', component: () => import('../pages/TagViewPage.vue'), meta: { title: 'Теги: Заказы по тегу' } },
    { path: '/tag/orders', name: 'tag-orders', component: () => import('../pages/TagViewPage.vue'), meta: { title: 'Теги: Заказы по тегу' } },
    { path: '/tag/margin', name: 'tag-margin', component: () => import('../pages/TagMarginPage.vue'), meta: { title: 'Маржа по тегам' } },
    { path: '/wb-search/card', name: 'wb-search-card', component: () => import('../pages/WbSearchCardPage.vue'), alias: ['/wb-search/card/'], meta: { title: 'Анализ поисковых фраз для карточки' } },
    { path: '/wb-search/phrase', name: 'wb-search-phrase', component: () => import('../pages/WbSearchPhrasePage.vue'), alias: ['/wb-search/phrase/'], meta: { title: 'Анализ фразы' } },
    { path: '/wb-search/trend', name: 'wb-search-trend', component: () => import('../pages/WbSearchTrendPage.vue'), alias: ['/wb-search/trend/'], meta: { title: 'Анализ фразы' } },
    { path: '/wb-search/analytics', name: 'wb-search-analytics', component: () => import('../pages/WbSearchAnalyticsPage.vue'), alias: ['/wb-search/analytics/'], meta: { title: 'Частотность поисковых запросов' } },
    { path: '/wb-search/cannibalization', name: 'wb-search-cannibalization', component: () => import('../pages/WbSearchCannibalizationPage.vue'), alias: ['/wb-search/cannibalization/'], meta: { title: 'Каннибализация запросов', needPerm: 'viewSeo' } },
    { path: '/wb-reports/year-compare', name: 'year-compare', component: () => import('../pages/YearComparePage.vue'), meta: { title: 'Сравнение по годам', needPerm: 'viewOrders' } },
    // Старые адреса Yii2 — редиректы на новый экран (закладки «Заказы» / «Продажи»).
    { path: '/agg-orders-report/compare', redirect: { path: '/wb-reports/year-compare', query: { tab: 'orders' } } },
    { path: '/agg-sales-report/compare', redirect: { path: '/wb-reports/year-compare', query: { tab: 'sales' } } },
    { path: '/cost-import', name: 'cost-import', component: () => import('../pages/CostImportPage.vue'), alias: ['/cost-import/'], meta: { title: 'Загрузка себестоимости' } },
    { path: '/cost-import/list', name: 'cost-list', component: () => import('../pages/CostListPage.vue'), alias: ['/cost-import/list/'], meta: { title: 'Себестоимость: просмотр и редактирование' } },
    { path: '/cost-import/missing', name: 'cost-missing', component: () => import('../pages/CostMissingPage.vue'), alias: ['/cost-import/missing/'], meta: { title: 'Нет себестоимости' } },
    { path: '/wb-order/index', name: 'wb-orders', component: () => import('../pages/WbOrdersPage.vue'), alias: ['/wb-order/index/'], meta: { title: 'Список заказов' } },
    { path: '/wb-sales/index', name: 'wb-sales', component: () => import('../pages/WbSalesPage.vue'), alias: ['/wb-sales/index/'], meta: { title: 'Список продаж' } },
    { path: '/wb-feedback-answers', name: 'feedback-answers', component: () => import('../pages/FeedbackAnswersPage.vue'), alias: ['/wb-feedback-answers/', '/wb-feedback-answers/index', '/wb-feedback-answers/index/'], meta: { title: 'Отзывы и ответы' } },
    { path: '/wb-questions', name: 'questions', component: () => import('../pages/QuestionsPage.vue'), alias: ['/wb-questions/', '/wb-questions/index', '/wb-questions/index/'], meta: { title: 'Вопросы покупателей' } },
    { path: '/wb-feedback-tags', name: 'feedback-tags', component: () => import('../pages/FeedbackTagsPage.vue'), alias: ['/wb-feedback-tags/', '/wb-feedback-tags/index', '/wb-feedback-tags/index/'], meta: { title: 'Разметка тегов отзывов' } },
    { path: '/wb-feedback-reply-rules', name: 'reply-rules', component: () => import('../pages/ReplyRulesPage.vue'), alias: ['/wb-feedback-reply-rules/', '/wb-feedback-reply-rules/index', '/wb-feedback-reply-rules/index/'], meta: { title: 'Автоответы на отзывы' } },
    { path: '/wb-feedback-analysis', name: 'feedback-analysis', component: () => import('../pages/FeedbackAnalysisPage.vue'), alias: ['/wb-feedback-analysis/', '/wb-feedback-analysis/index', '/wb-feedback-analysis/index/'], meta: { title: 'Разбор' } },
    { path: '/wb-feedback-insights', name: 'feedback-insights', component: () => import('../pages/FeedbackInsightsPage.vue'), alias: ['/wb-feedback-insights/', '/wb-feedback-insights/index', '/wb-feedback-insights/index/'], meta: { title: 'Инсайты' } },
    { path: '/wb-feedback', name: 'feedback-dashboard', component: () => import('../pages/FeedbackDashboardPage.vue'), alias: ['/wb-feedback/', '/wb-feedback/index', '/wb-feedback/index/'], meta: { title: 'Отзывы: Обзор' } },
    { path: '/wb-feedback-review', name: 'feedback-review', component: () => import('../pages/FeedbackReviewPage.vue'), alias: ['/wb-feedback-review/', '/wb-feedback-review/index', '/wb-feedback-review/index/'], meta: { title: 'Разбор отзывов (фон)' } },
    { path: '/wb-feedback-reply-rules/test-generation', name: 'reply-test', component: () => import('../pages/ReplyTestPage.vue'), alias: ['/wb-feedback-reply-rules/test-generation/'], meta: { title: 'Тестирование генерации автоответов' } },
    { path: '/wb-feedback-reply-rules/stop-words', name: 'stop-words', component: () => import('../pages/StopWordsPage.vue'), alias: ['/wb-feedback-reply-rules/stop-words/'], meta: { title: 'Стоп-слова' } },
    { path: '/wb-feedback-reply-rules/create', name: 'reply-rule-create', component: () => import('../pages/ReplyRuleFormPage.vue'), alias: ['/wb-feedback-reply-rules/create/'], meta: { title: 'Создание правила автоответа' } },
    { path: '/wb-feedback-reply-rules/:id/edit', name: 'reply-rule-edit', component: () => import('../pages/ReplyRuleFormPage.vue'), meta: { title: 'Редактирование правила' } },
    { path: '/competitor/new-cards', name: 'competitor-new-cards', component: () => import('../pages/CompetitorNewCardsPage.vue'), meta: { title: 'Конкуренты: ручная привязка' } },
    { path: '/competitor/new-cards/:nm', name: 'competitor-card-workspace', component: () => import('../pages/CompetitorCardWorkspacePage.vue'), meta: { title: 'Карточка конкурента' } },
    { path: '/competitor/captured', name: 'competitor-captured', component: () => import('../pages/CompetitorCapturedPage.vue'), meta: { title: 'Собранные карточки' } },
    { path: '/competitor/positions', name: 'competitor-positions', component: () => import('../pages/CompetitorPositionsPage.vue'), meta: { title: 'Поисковые запросы' } },
    { path: '/seo-watch', name: 'seo-watch', component: () => import('../pages/SeoWatchPage.vue'), meta: { title: 'SEO-мониторинг' } },
    { path: '/competitor/queue', name: 'competitor-queue', component: () => import('../pages/QueuePage.vue'), meta: { title: 'Очередь' } },
    // старый путь — редирект, чтобы старые ссылки и закладки не 404
    { path: '/queue', redirect: '/competitor/queue' },
    { path: '/competitor/pick', name: 'competitor-pick', component: () => import('../pages/CompetitorPickPage.vue'), meta: { title: 'Конкуренты: подбор' } },
    { path: '/competitor/refresh', name: 'competitor-refresh', component: () => import('../pages/CompetitorRefreshPage.vue'), meta: { title: 'Конкуренты: обновление' } },
    { path: '/competitor/phrase-miner', name: 'competitor-phrase-miner', component: () => import('../pages/PhraseMinerPage.vue'), meta: { title: 'Разбор фраз (фон)' } },
    { path: '/competitor/images', name: 'competitor-images', component: () => import('../pages/CompetitorImagesPage.vue'), meta: { title: 'Фото карточек (фон)', needPerm: 'viewSeo' } },
    { path: '/competitor/index', name: 'competitor-index', component: () => import('../pages/CompetitorIndexPage.vue'), alias: ['/competitor/', '/competitor'], meta: { title: 'Конкуренты: анализ' } },
    { path: '/competitor/select/:nm', name: 'competitor-select', component: () => import('../pages/CompetitorSelectPage.vue'), meta: { title: 'Конкуренты: выбор фраз' } },
    { path: '/competitor/selected/:nm', name: 'competitor-selected', component: () => import('../pages/CompetitorSelectedPage.vue'), meta: { title: 'Конкуренты: отбор' } },
    { path: '/competitor/results/:nm', name: 'competitor-results', component: () => import('../pages/CompetitorResultsPage.vue'), meta: { title: 'Результаты анализа конкурентов' } },
    { path: '/seo/index', name: 'seo-index', component: () => import('../pages/SeoIndexPage.vue'), alias: ['/seo/', '/seo'], meta: { title: 'SEO рекомендации' } },
    { path: '/seo/ai-usage', name: 'seo-ai-usage', component: () => import('../pages/AiUsagePage.vue'), meta: { title: 'Затраты ИИ' } },
    { path: '/seo/view/:id', name: 'seo-view', component: () => import('../pages/SeoViewPage.vue'), meta: { title: 'SEO рекомендация' } },
    { path: '/ext/diag', name: 'ext-diag', component: () => import('../pages/ExtDiagPage.vue'), meta: { title: 'Диагностика расширения' } },
    { path: '/ext/install', name: 'ext-install', component: () => import('../pages/ExtInstallPage.vue'), meta: { title: 'Установка расширения' } },
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

// Заголовок вкладки: meta.title (чистое имя) + бренд «— SelBI» из константы.
router.afterEach((to) => {
  const t = to.meta?.title as string | undefined
  if (t) document.title = docTitle(t)
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
  // Гейт по доменному перму (v3). В старом режиме (AUTH_V3=0) маршрут открыт всем.
  const needPerm = (to.meta as any)?.needPerm as string | undefined
  if (needPerm && auth.authV3 && !auth.can(needPerm)) return { path: '/' }
  return true
})

export default router
