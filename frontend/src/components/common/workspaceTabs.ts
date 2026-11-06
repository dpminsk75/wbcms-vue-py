/** Описание вкладки рабочего места (общий таб-каркас, FBS-модель). */
export interface WorkspaceTab {
  id: string
  label: string
  /** Роут вкладки; пусто или disabled=true — вкладка-заглушка «Скоро». */
  to?: string
  icon?: string
  title?: string
  disabled?: boolean
}

/**
 * Верхнее меню рабочих мест (FBS-модель) — один список на все страницы,
 * чтобы «Сводка / Поисковые запросы / …» выглядело одинаково и стояло
 * прижатым к правому верхнему углу (см. WbWorkspaceTabs, margin-left:auto).
 */
export const WORKSPACE_TABS: WorkspaceTab[] = [
  { id: 'summary', label: 'Сводка', to: '/seo-watch' },
  { id: 'positions', label: 'Поисковые запросы', to: '/competitor/positions' },
  { id: 'captured', label: 'Собранные карточки', to: '/competitor/captured' },
  { id: 'seo', label: 'SEO рекомендации', to: '/seo/index' },
  { id: 'competitors', label: 'Конкуренты', to: '/competitor/new-cards' },
  { id: 'queue', label: 'Очередь', to: '/competitor/queue' },
]

/** Меню раздела «Отзывы» — одинаковое на всех страницах блока. */
export const FEEDBACK_TABS: WorkspaceTab[] = [
  { id: 'dashboard', label: 'Обзор', to: '/wb-feedback' },
  { id: 'answers', label: 'Отзывы и ответы', to: '/wb-feedback-answers/index' },
  { id: 'analysis', label: 'Разбор', to: '/wb-feedback-analysis' },
  { id: 'insights', label: 'Инсайты', to: '/wb-feedback-insights' },
  { id: 'review', label: 'Разбор отзывов', to: '/wb-feedback-review' },
  { id: 'rules', label: 'Правила ответов', to: '/wb-feedback-reply-rules/index' },
  { id: 'tags', label: 'Теги', to: '/wb-feedback-tags/index' },
]

/** Подменю раздела «Правила ответов» — на всех его страницах (как /seo/index). */
export const FEEDBACK_RULES_SUB_TABS: SubTab[] = [
  { id: 'rules', label: 'Правила', to: '/wb-feedback-reply-rules/index',
    title: 'Список правил автоответа' },
  { id: 'stop-words', label: 'Стоп-слова', to: '/wb-feedback-reply-rules/stop-words',
    title: 'Слова, при которых автоответ не отправляется' },
  { id: 'test', label: 'Тест генерации', to: '/wb-feedback-reply-rules/test-generation',
    title: 'Пробная сборка ответов по последним отзывам' },
]

/** Подменю раздела (строка пилюль под заголовком рабочего места). */
export interface SubTab {
  id: string
  label: string
  /** Роут с query — как в ссылке '/seo/index?status=all'. */
  to: string
  title?: string
  /** Счётчик в бейдже рядом с названием. */
  count?: number | null
}

/** Подменю раздела «Конкуренты» — одинаковое на всех его страницах. */
export const COMPETITOR_SUB_TABS: SubTab[] = [
  { id: 'manual', label: 'Ручная привязка', to: '/competitor/new-cards',
    title: 'Наши карточки в работе: привязка конкурентов вручную' },
  { id: 'pick', label: 'Подбор', to: '/competitor/pick',
    title: 'Подбор конкурентов: собрать пул кандидатов и привязать к нашим карточкам' },
  { id: 'refresh', label: 'Обновление', to: '/competitor/refresh',
    title: 'Обновить контент собранных конкурентов (очередь enrich)' },
  { id: 'analysis', label: 'Анализ', to: '/competitor/index',
    title: 'Анализ конкурентов по нашим товарам' },
]

/** Меню рабочего места «Теги» — одинаковое на всех его страницах (справа в углу). */
export const TAGS_WORKSPACE_TABS: WorkspaceTab[] = [
  { id: 'orders', label: 'Заказы', to: '/tag/orders', title: 'Заказы по тегу' },
  { id: 'margin', label: 'Маржа', to: '/tag/margin', title: 'Маржа по тегу' },
  { id: 'list', label: 'Список', to: '/tags', title: 'Список тегов' },
]

/** Блок «Акции WB» — календарь, подбор товаров по марже, загрузка файла из ЛК. */
export const PROMOTIONS_TABS: WorkspaceTab[] = [
  { id: 'overview', label: 'Обзор', to: '/wb-promotions', title: 'Календарь акций и список' },
  { id: 'selection', label: 'Подбор товаров', to: '/wb-promotions/selection', title: 'Подбор товаров по марже' },
  { id: 'import', label: 'Загрузка из Excel', to: '', title: 'Скоро: файл из ЛК WB для автоакций' },
]

/* ============================================================
   Раздел «Склад» — 4 блока, у каждого СВОЁ правое меню
   (theme.md §5.7.10). Общего меню у раздела нет: наборы ниже
   подставляются в WbWorkspaceHead через :workspace-tabs.
   ============================================================ */

/** Блок «FBS» — как двигаются отгруженные по FBS заказы. */
export const STOCK_FBS_TABS: WorkspaceTab[] = [
  { id: 'summary', label: 'Сводка', to: '/fbs-report', title: 'FBS — продажа со своего склада' },
  { id: 'orders', label: 'Заказы', to: '/fbs-orders', title: 'FBS — заказы' },
  { id: 'cancels', label: 'Отмены', to: '/fbs-cancels', title: 'FBS — отмены' },
  { id: 'commission', label: 'Комиссия', to: '/fbs-commission', title: 'FBS — комиссия' },
  { id: 'pvz', label: 'Путь до ПВЗ', to: '/fbs-pvz', title: 'FBS — путь до ПВЗ' },
]

/** Блок «Отчёты» — контроль остатков (наши склады: our_warehouse + ledger). */
export const STOCK_REPORTS_TABS: WorkspaceTab[] = [
  { id: 'balance', label: 'Наличие', to: '/wb-stock-reports/balance', title: 'Остатки по складам' },
  { id: 'turnover', label: 'Оборотная ведомость', to: '/wb-stock-reports/turnover', title: 'Движения по складам' },
  { id: 'card', label: 'Карточка товара', to: '/wb-stock-reports/card', title: 'Движения по карточке товара' },
  { id: 'nonliquid', label: 'Неликвиды', to: '/wb-stock-reports/nonliquid', title: 'Залежавшиеся остатки' },
]

/** Блок «Документы» — мини-складской учёт внутри нашей системы. */
export const STOCK_DOCS_TABS: WorkspaceTab[] = [
  { id: 'docs', label: 'Документы', to: '/wb-doc', title: 'Документы склада' },
  { id: 'virtual', label: 'Виртуальные склады', to: '/wb-fbs-virtual', title: 'FBS остатки: центр + виртуальные' },
  { id: 'warehouses', label: 'Свои склады', to: '/wb-warehouses', title: 'Свои склады' },
]

/** Блок «Производство» — помощь закупщику. «Смоленск» — легаси-страница. */
export const STOCK_PRODUCTION_TABS: WorkspaceTab[] = [
  { id: 'plan', label: 'Производственный план', to: '/wb-production', title: 'Производственный план' },
  { id: 'smolensk', label: 'Смоленск', to: '/wb-production/smolensk', title: 'Смоленск — остатки и движения' },
]
