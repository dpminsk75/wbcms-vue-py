/**
 * Пользовательские настройки страницы подбора акций — в localStorage
 * (по конвенции проекта: тема и ширины колонок тоже хранятся в браузере).
 *
 * Ключ — с компанией: у пользователя бывают разные компании, настройки не
 * должны смешиваться.
 */

const KEY = 'promo-params:company:'

/** Настройки, которые помним. */
export interface PromoPrefs {
  days: number
  min_margin_pct: number
  max_drop_pp: number
  min_margin_rub: number
  min_stock_wb: number
  auto_discount: number
  include_reviews: boolean
  include_adv: boolean
  include_cashback: boolean
  include_penalties: boolean
  sort: string
  order: string
  in_action: string
  rows: number
}

/** Текущая компания (её хранит стор авторизации). */
function companyId(): string {
  try {
    return String(localStorage.getItem('wbcms_company') || '')
  } catch {
    return ''
  }
}

function key(): string {
  return KEY + (companyId() || 'default')
}

/** Прочитать сохранённые настройки (пусто — если их нет). */
export function loadPromoPrefs(): Partial<PromoPrefs> {
  try {
    const raw = localStorage.getItem(key())
    if (!raw) return {}
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj as Partial<PromoPrefs> : {}
  } catch {
    return {}
  }
}

/** Сохранить настройки. */
export function savePromoPrefs(p: Partial<PromoPrefs>): void {
  try {
    localStorage.setItem(key(), JSON.stringify(p))
  } catch {
    /* приватный режим — просто не сохраняем */
  }
}

/** Сбросить настройки (кнопка «Сбросить»). */
export function clearPromoPrefs(): void {
  try {
    localStorage.removeItem(key())
  } catch {
    /* noop */
  }
}
