/**
 * Форматирование чисел — единое для всех страниц.
 *
 * Раньше каждый компонент определял свои fmt0/fmt1/fmt2/fmtVal (49 файлов),
 * причём с разным числом знаков: например, fmt1 в SalesAnalysisPage печатал
 * два знака — визуально не отличить от fmt2.
 *
 * Использование:
 *   const { fmt0, fmt1, fmt2, fmtVal, fmtMoney, fmtPct } = useNumFmt()
 */
export function useNumFmt() {
  /** Целое число: 1 234 */
  const fmt0 = (v: any): string =>
    new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))

  /** Один знак после запятой: 12,3 */
  const fmt1 = (v: any): string =>
    new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(v) || 0)

  /** Два знака после запятой: 12,34 */
  const fmt2 = (v: any): string =>
    new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)

  /** Значение с заданной точностью; пустое — тире: «—» */
  const fmtVal = (v: any, dec = 2): string => {
    if (v === null || v === '' || v === undefined) return '—'
    return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(Number(v))
  }

  /** Деньги без копеек: «1 284 300 ₽» */
  const fmtMoney = (v: any): string => fmt0(v) + ' ₽'

  /** Процент: «12,34 %» */
  const fmtPct = (v: any, dec = 2): string =>
    new Intl.NumberFormat('ru-RU', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(Number(v) || 0) + ' %'

  return { fmt0, fmt1, fmt2, fmtVal, fmtMoney, fmtPct }
}
