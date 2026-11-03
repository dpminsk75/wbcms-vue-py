/**
 * Заголовки страниц: заголовок вкладки браузера и заголовок на странице (h1).
 *
 * Разделение:
 *   - `route.meta.title` — ЧИСТОЕ имя (без бренда). Роутер дописывает `— SelBI`.
 *   - `route.meta.h1`    — заголовок на странице; если нет — title без суффикса.
 *
 * Title и h1 могут различаться: вкладка «Отчеты склада — SelBI»,
 * на странице «Остатки на складе».
 */

/** Бренд в заголовке вкладки. */
export const APP_SUFFIX = '— SelBI'

/** Заголовок вкладки: 'Лента заказов' → 'Лента заказов — SelBI'. */
export function docTitle(title: string): string {
  return `${title} ${APP_SUFFIX}`
}

/** Убрать бренд из заголовка: 'Лента заказов — SelBI' → 'Лента заказов'. */
export function stripSuffix(title?: string | null): string {
  return String(title ?? '').replace(/\s*—\s*SelBI\s*$/, '').trim()
}
