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