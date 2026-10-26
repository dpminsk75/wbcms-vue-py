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
  { id: 'queue', label: 'Очередь', to: '/queue' },
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